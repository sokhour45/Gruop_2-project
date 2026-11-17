import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from warehouse.db import WarehouseDB, _Connection


class _RecordingConnection:
    def __init__(self):
        self.statement = None
        self.parameters = None
        self.recording_cursor = _RecordingCursor()

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        return self

    def cursor(self):
        return self.recording_cursor


class _RecordingCursor:
    def __init__(self):
        self.statement = None
        self.parameters = None

    def executemany(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        return self


class WarehouseDatabaseTests(unittest.TestCase):
    def make_app(self, directory, database):
        import_database = Path(directory) / "app-import.db"
        import_url = f"sqlite:///{import_database.as_posix()}"
        with patch.dict(os.environ, {"WAREHOUSE_DATABASE_URL": import_url}):
            from warehouse.web_app import create_app

        app = create_app(database)
        app.config.update(TESTING=True)
        return app

    def test_postgres_connection_translates_sqlite_placeholders_and_locks(self):
        raw_connection = _RecordingConnection()
        connection = _Connection(raw_connection, postgres=True)

        connection.execute(
            "BEGIN IMMEDIATE; SELECT * FROM users WHERE username = ? COLLATE NOCASE",
            ("operator",),
        )

        self.assertEqual(raw_connection.statement, "BEGIN; SELECT * FROM users WHERE username = %s")
        self.assertEqual(raw_connection.parameters, ("operator",))

    def test_postgres_executemany_uses_a_cursor(self):
        raw_connection = _RecordingConnection()
        connection = _Connection(raw_connection, postgres=True)
        rows = [("SKU-1",), ("SKU-2",)]

        connection.executemany("INSERT INTO products (sku) VALUES (?)", rows)

        self.assertEqual(
            raw_connection.recording_cursor.statement,
            "INSERT INTO products (sku) VALUES (%s)",
        )
        self.assertEqual(raw_connection.recording_cursor.parameters, rows)

    def test_account_creation_and_login_use_configured_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            app = self.make_app(directory, database)
            client = app.test_client()

            response = client.post(
                "/login",
                data={
                    "username": "warehouse-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/dashboard")
            user = database.authenticate_user("WAREHOUSE-ADMIN", "secure-test-password")
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "admin")

            employee_response = client.post(
                "/login?register=1",
                data={
                    "username": "warehouse-operator",
                    "password": "another-test-password",
                    "confirm_password": "another-test-password",
                },
            )
            self.assertEqual(employee_response.status_code, 302)
            employee = database.authenticate_user("warehouse-operator", "another-test-password")
            self.assertIsNotNone(employee)
            self.assertEqual(employee.role, "employee")

    def test_dashboard_summarizes_inventory_and_recent_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            database.record_movement(1, "IN", 1, "Dashboard test receipt")
            client = self.make_app(directory, database).test_client()

            client.post(
                "/login",
                data={
                    "username": "dashboard-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )
            response = client.get("/dashboard")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Units on hand", response.data)
            self.assertIn(b"35", response.data)
            self.assertIn(b"Stock health", response.data)
            self.assertIn(b"Stock in", response.data)
            self.assertIn(b"Ballpoint Pens", response.data)

    def test_dashboard_renders_empty_inventory_without_dividing_by_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.create_user("empty-dashboard-admin", "secure-test-password", "admin")
            client = self.make_app(directory, database).test_client()

            client.post(
                "/login",
                data={
                    "username": "empty-dashboard-admin",
                    "password": "secure-test-password",
                },
            )
            response = client.get("/dashboard")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"No products yet", response.data)
            self.assertIn(b"Stock levels look good", response.data)

    def test_out_of_stock_filter_shows_only_zero_quantity_products(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            database.record_movement(1, "OUT", 12, "Test depletion")
            database.create_user("stock-filter-admin", "secure-test-password", "admin")
            client = self.make_app(directory, database).test_client()

            client.post(
                "/login",
                data={
                    "username": "stock-filter-admin",
                    "password": "secure-test-password",
                },
            )
            response = client.get("/products?out_of_stock=1&search=A1-01")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Ballpoint Pens", response.data)
            self.assertNotIn(b"Shipping Carton", response.data)
            self.assertIn(b"Out of stock", response.data)
            self.assertIn(b"Total SKUs", response.data)
            self.assertIn(b"of 3 products shown", response.data)
            self.assertIn(b"Clear filters", response.data)

    def test_stock_movement_pages_show_product_stock_context(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            database.record_movement(1, "OUT", 12, "Test depletion")
            client = self.make_app(directory, database).test_client()

            client.post(
                "/login",
                data={
                    "username": "movement-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )
            stock_in_response = client.get("/stock-in")
            stock_out_response = client.get("/stock-out")

            self.assertEqual(stock_in_response.status_code, 200)
            self.assertIn(b"Receive inventory", stock_in_response.data)
            self.assertIn(b"Product choices", stock_in_response.data)
            self.assertIn(b"Recent receipts", stock_in_response.data)
            self.assertEqual(stock_out_response.status_code, 200)
            self.assertIn(b"Issue inventory", stock_out_response.data)
            self.assertIn(b"SKUs available to issue", stock_out_response.data)
            self.assertIn(b"value=\"1\"", stock_out_response.data)
            self.assertIn(b'data-quantity="0"', stock_out_response.data)
            self.assertIn(b"disabled", stock_out_response.data)

    def test_stock_out_rejects_quantity_above_available_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            client = self.make_app(directory, database).test_client()
            client.post(
                "/login",
                data={
                    "username": "movement-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )

            response = client.post(
                "/stock-out",
                data={"product_id": "1", "quantity": "15", "note": "Order 103"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Only 12 available", response.data)
            self.assertIn(b'value="15"', response.data)
            self.assertIn(b'value="Order 103"', response.data)
            self.assertEqual(database.get_product(1).quantity, 12)

    def test_stock_in_and_stock_out_post_movements_and_new_balances(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            client = self.make_app(directory, database).test_client()
            client.post(
                "/login",
                data={
                    "username": "movement-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )

            receive_response = client.post(
                "/stock-in",
                data={"product_id": "1", "quantity": "3", "note": "PO 204"},
            )
            issue_response = client.post(
                "/stock-out",
                data={"product_id": "1", "quantity": "2", "note": "Order 103"},
            )

            self.assertEqual(receive_response.status_code, 302)
            self.assertEqual(issue_response.status_code, 302)
            self.assertEqual(database.get_product(1).quantity, 13)
            transactions = database.list_transactions(limit=2)
            self.assertEqual([transaction.type for transaction in transactions], ["OUT", "IN"])
            self.assertEqual(transactions[0].balance, 13)
            self.assertEqual(transactions[1].balance, 15)
            inbound = database.list_transactions(limit=1, movement_type="IN")
            self.assertEqual(len(inbound), 1)
            self.assertEqual(inbound[0].balance, 15)

    def test_history_filters_and_paginates_matching_movements(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            for index in range(51):
                database.record_movement(1, "IN", 1, f"PO-BATCH-{index}")
            database.record_movement(1, "OUT", 1, "Order 884")
            client = self.make_app(directory, database).test_client()
            client.post(
                "/login",
                data={
                    "username": "history-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )
            transaction_date = database.list_transactions(limit=1)[0].timestamp.date().isoformat()
            filters = {
                "movement_type": "IN",
                "search": "PO-BATCH",
                "from_date": transaction_date,
                "to_date": transaction_date,
            }

            first_page = client.get("/history", query_string=filters)
            second_page = client.get(
                "/history", query_string={**filters, "page": "2"}
            )

            self.assertEqual(first_page.status_code, 200)
            self.assertIn(b"Page 1 of 2", first_page.data)
            self.assertNotIn(b"Order 884", first_page.data)
            self.assertEqual(second_page.status_code, 200)
            self.assertIn(b"Page 2 of 2", second_page.data)
            self.assertIn(b"PO-BATCH-0", second_page.data)

    def test_reports_summarize_stock_and_recent_movements(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()
            database.record_movement(1, "IN", 2, "PO 554")
            database.record_movement(1, "OUT", 1, "Order 884")
            client = self.make_app(directory, database).test_client()
            client.post(
                "/login",
                data={
                    "username": "reports-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )

            response = client.get("/reports")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Inventory value", response.data)
            self.assertIn(b"Movement in the last 30 days", response.data)
            self.assertIn(b"+2", response.data)
            self.assertIn(b"1", response.data)
            self.assertIn(b"Stock by category", response.data)
            self.assertIn(b"Export inventory CSV", response.data)

    def test_users_page_safeguards_roles_and_refreshes_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            app = self.make_app(directory, database)
            admin_client = app.test_client()
            admin_client.post(
                "/login",
                data={
                    "username": "accounts-admin",
                    "password": "secure-test-password",
                    "confirm_password": "secure-test-password",
                },
            )
            database.create_user("warehouse-manager", "manager-test-password", "manager")
            admin = next(user for user in database.list_users() if user.username == "accounts-admin")
            manager = next(user for user in database.list_users() if user.username == "warehouse-manager")
            manager_client = app.test_client()
            manager_client.post(
                "/login",
                data={
                    "username": "warehouse-manager",
                    "password": "manager-test-password",
                },
            )

            users_response = admin_client.get("/users")
            self_change_response = admin_client.post(
                f"/users/{admin.id}/role", data={"role": "employee"}
            )
            manager_change_response = admin_client.post(
                f"/users/{manager.id}/role", data={"role": "employee"}
            )
            protected_response = manager_client.get("/products/1/edit")

            self.assertEqual(users_response.status_code, 200)
            self.assertIn(b"Your own role cannot be changed here", users_response.data)
            self.assertIn(b"Administrators", users_response.data)
            self.assertEqual(self_change_response.status_code, 302)
            self.assertEqual(database.get_user(admin.id).role, "admin")
            self.assertEqual(manager_change_response.status_code, 302)
            self.assertEqual(database.get_user(manager.id).role, "employee")
            self.assertEqual(protected_response.status_code, 302)
            self.assertEqual(protected_response.headers["Location"], "/dashboard")

    def test_sqlite_database_keeps_product_and_movement_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            database.seed_sample_data()

            self.assertFalse(database.postgres)
            product = database.list_products(search="pen")[0]
            self.assertEqual(product.sku, "PEN001")
            balance = database.record_movement(product.id, "IN", 2, "Test receipt")
            self.assertEqual(balance, 14)
            self.assertEqual(database.list_transactions(limit=1)[0].balance, 14)

    def test_vercel_requires_a_postgres_database_url(self):
        variables = {
            "VERCEL": "1",
            "WAREHOUSE_DATABASE_URL": "",
            "POSTGRES_URL_NON_POOLING": "",
            "POSTGRES_URL": "",
            "DATABASE_URL": "",
        }
        with patch.dict(os.environ, variables):
            with self.assertRaisesRegex(RuntimeError, "persistent PostgreSQL"):
                WarehouseDB()

    def test_sqlite_url_resolves_to_its_database_file(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "warehouse-test.db"
            database_url = f"sqlite:///{database_path.as_posix()}"
            with patch.dict(os.environ, {"WAREHOUSE_DATABASE_URL": database_url}):
                database = WarehouseDB()

            self.assertEqual(database.path.resolve(), database_path.resolve())


if __name__ == "__main__":
    unittest.main()
