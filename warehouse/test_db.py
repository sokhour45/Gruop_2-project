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
            response = client.get("/products?out_of_stock=1")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Ballpoint Pens", response.data)
            self.assertNotIn(b"Shipping Carton", response.data)
            self.assertIn(b"Out of stock only", response.data)

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
