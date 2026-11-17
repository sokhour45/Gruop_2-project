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

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        return self


class WarehouseDatabaseTests(unittest.TestCase):
    def test_postgres_connection_translates_sqlite_placeholders_and_locks(self):
        raw_connection = _RecordingConnection()
        connection = _Connection(raw_connection, postgres=True)

        connection.execute(
            "BEGIN IMMEDIATE; SELECT * FROM users WHERE username = ? COLLATE NOCASE",
            ("operator",),
        )

        self.assertEqual(raw_connection.statement, "BEGIN; SELECT * FROM users WHERE username = %s")
        self.assertEqual(raw_connection.parameters, ("operator",))

    def test_account_creation_and_login_use_configured_database(self):
        with tempfile.TemporaryDirectory() as directory:
            import_database = Path(directory) / "app-import.db"
            import_url = f"sqlite:///{import_database.as_posix()}"
            with patch.dict(os.environ, {"WAREHOUSE_DATABASE_URL": import_url}):
                from warehouse.web_app import create_app

            database = WarehouseDB(Path(directory) / "warehouse-test.db")
            app = create_app(database)
            app.config.update(TESTING=True)
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
