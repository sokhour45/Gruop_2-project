"""SQLite persistence and transactional warehouse operations."""

import sqlite3
import hashlib
import hmac
import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import unquote, urlparse

import psycopg
from psycopg.rows import dict_row

from warehouse.models import Product, Transaction, User


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "warehouse.db"


class _Connection:
    def __init__(self, connection: Any, *, postgres: bool):
        self._connection = connection
        self._postgres = postgres

    def _sql(self, statement: str) -> str:
        if not self._postgres:
            return statement
        return (
            statement.replace("BEGIN IMMEDIATE", "BEGIN")
            .replace(" COLLATE NOCASE", "")
            .replace("?", "%s")
        )

    def execute(self, statement: str, parameters: Iterable[object] = ()):
        return self._connection.execute(self._sql(statement), tuple(parameters))

    def executemany(self, statement: str, parameters: Iterable[Iterable[object]]):
        statement = self._sql(statement)
        if self._postgres:
            return self._connection.cursor().executemany(statement, parameters)
        return self._connection.executemany(statement, parameters)

    def executescript(self, script: str):
        if self._postgres:
            raise RuntimeError("PostgreSQL schemas must be initialized statement by statement.")
        return self._connection.executescript(script)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._connection.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class WarehouseDB:
    def __init__(self, path: str | Path | None = None):
        self.database_url = ""
        url_sqlite_path = None
        if path is None:
            self.database_url = (
                os.environ.get("WAREHOUSE_DATABASE_URL")
                or os.environ.get("POSTGRES_URL_NON_POOLING")
                or os.environ.get("POSTGRES_URL")
                or os.environ.get("DATABASE_URL")
                or ""
            )
        self.postgres = self.database_url.startswith(("postgres://", "postgresql://"))
        if self.database_url.startswith("sqlite:///"):
            sqlite_path = unquote(urlparse(self.database_url).path)
            is_windows_drive = (
                os.name == "nt"
                and len(sqlite_path) > 2
                and sqlite_path[0] == "/"
                and sqlite_path[2] == ":"
            )
            if is_windows_drive:
                sqlite_path = sqlite_path[1:]
            elif sqlite_path.startswith("//"):
                sqlite_path = sqlite_path[1:]
            else:
                sqlite_path = sqlite_path.lstrip("/")
            url_sqlite_path = Path(sqlite_path)
        elif self.database_url and not self.postgres:
            raise ValueError("Warehouse database URL must use PostgreSQL or SQLite.")
        if os.environ.get("VERCEL") and not self.postgres:
            raise RuntimeError(
                "Configure WAREHOUSE_DATABASE_URL or POSTGRES_URL with a persistent PostgreSQL database on Vercel."
            )
        self.path = Path(path) if path is not None else url_sqlite_path or DEFAULT_DB_PATH
        if not self.postgres:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> _Connection:
        if self.postgres:
            return _Connection(
                psycopg.connect(self.database_url, row_factory=dict_row),
                postgres=True,
            )
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return _Connection(connection, postgres=False)

    @contextmanager
    def _connection(self) -> Iterator[_Connection]:
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        if self.postgres:
            self._initialize_postgres()
            return
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'employee'
                        CHECK (role IN ('admin', 'manager', 'employee')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    unit_price REAL NOT NULL CHECK (unit_price >= 0),
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0),
                    supplier TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    sku TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('IN', 'OUT')),
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    note TEXT NOT NULL DEFAULT '',
                    balance INTEGER NOT NULL CHECK (balance >= 0),
                    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "role" not in columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'employee'"
                )
            if connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone() is None:
                connection.execute(
                    "UPDATE users SET role = 'admin' WHERE id = "
                    "(SELECT id FROM users ORDER BY id LIMIT 1)"
                )

    def _initialize_postgres(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee'
                    CHECK (role IN ('admin', 'manager', 'employee')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_price DOUBLE PRECISION NOT NULL CHECK (unit_price >= 0),
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0),
                supplier TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                product_id BIGINT,
                sku TEXT NOT NULL,
                product_name TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('IN', 'OUT')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                note TEXT NOT NULL DEFAULT '',
                balance INTEGER NOT NULL CHECK (balance >= 0),
                timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (LOWER(username))",
            "CREATE UNIQUE INDEX IF NOT EXISTS products_sku_lower_idx ON products (LOWER(sku))",
        )
        with self._connection() as connection:
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'employee'"
            )
            if connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone() is None:
                connection.execute(
                    "UPDATE users SET role = 'admin' WHERE id = "
                    "(SELECT id FROM users ORDER BY id LIMIT 1)"
                )

    def has_users(self) -> bool:
        with self._connection() as connection:
            return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def create_user(self, username: str, password: str, role: str = "employee") -> None:
        username = username.strip()
        if not username or not password or role not in {"admin", "manager", "employee"}:
            raise ValueError("Username, password, and a valid role are required.")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
        password_hash = f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, password_hash, role),
                )
        except (sqlite3.IntegrityError, psycopg.IntegrityError) as error:
            raise ValueError("That username is already in use.") from error

    def authenticate_user(self, username: str, password: str) -> User | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, role FROM users "
                "WHERE LOWER(username) = LOWER(?)",
                (username.strip(),),
            ).fetchone()
        if row is None:
            return None
        try:
            algorithm, iterations, salt_hex, digest_hex = row["password_hash"].split("$")
            if algorithm != "pbkdf2_sha256":
                return None
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            )
        except (ValueError, TypeError):
            return None
        if not hmac.compare_digest(actual, expected):
            return None
        return User(row["id"], row["username"], row["role"])

    def list_users(self) -> list[User]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, username, role FROM users ORDER BY LOWER(username)"
            ).fetchall()
        return [User(row["id"], row["username"], row["role"]) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return User(row["id"], row["username"], row["role"])

    def update_user_role(self, user_id: int, role: str) -> None:
        if role not in {"admin", "manager", "employee"}:
            raise ValueError("Invalid user role.")
        with self._connection() as connection:
            current = connection.execute(
                "SELECT role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if current is None:
                raise LookupError("The user no longer exists.")
            if current["role"] == "admin" and role != "admin":
                admins = connection.execute(
                    "SELECT COUNT(*) AS count FROM users WHERE role = 'admin'"
                ).fetchone()["count"]
                if admins <= 1:
                    raise ValueError("At least one administrator account is required.")
            connection.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    @staticmethod
    def _product(row: Any) -> Product:
        return Product(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            unit=row["unit"],
            unit_price=row["unit_price"],
            quantity=row["quantity"],
            reorder_level=row["reorder_level"],
            supplier=row["supplier"],
            location=row["location"],
        )

    @staticmethod
    def _transaction(row: Any) -> Transaction:
        from datetime import datetime

        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return Transaction(
            id=row["id"],
            sku=row["sku"],
            product_name=row["product_name"],
            type=row["type"],
            quantity=row["quantity"],
            note=row["note"],
            balance=row["balance"],
            timestamp=timestamp,
        )

    def list_products(
        self, search: str = "", low_stock: bool = False, category: str = ""
    ) -> list[Product]:
        sql = "SELECT * FROM products WHERE 1 = 1"
        params: list[object] = []
        if search.strip():
            term = f"%{search.strip()}%"
            sql += """ AND (
                LOWER(sku) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?)
                OR LOWER(category) LIKE LOWER(?) OR LOWER(supplier) LIKE LOWER(?)
                OR LOWER(location) LIKE LOWER(?)
            )"""
            params.extend((term, term, term, term, term))
        if low_stock:
            sql += " AND quantity <= reorder_level"
        if category.strip():
            sql += " AND category = ?"
            params.append(category.strip())
        sql += " ORDER BY LOWER(name)"
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._product(row) for row in rows]

    def get_product(self, product_id: int) -> Product | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        return self._product(row) if row else None

    def sku_exists(self, sku: str) -> bool:
        with self._connection() as connection:
            return connection.execute(
                "SELECT 1 FROM products WHERE LOWER(sku) = LOWER(?)", (sku,)
            ).fetchone() is not None

    def sku_exists_for_other(self, sku: str, product_id: int) -> bool:
        with self._connection() as connection:
            return connection.execute(
                "SELECT 1 FROM products WHERE LOWER(sku) = LOWER(?) AND id != ?",
                (sku, product_id),
            ).fetchone() is not None

    def save_product(self, values: dict[str, object], product_id: int | None = None) -> int:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if product_id is None:
                statement = """INSERT INTO products
                    (sku, name, category, unit, unit_price, quantity,
                     reorder_level, supplier, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                if self.postgres:
                    row = connection.execute(
                        statement + " RETURNING id",
                        self._product_values(values),
                    ).fetchone()
                    saved_id = int(row["id"])
                else:
                    cursor = connection.execute(statement, self._product_values(values))
                    saved_id = int(cursor.lastrowid)
            else:
                lock_clause = " FOR UPDATE" if self.postgres else ""
                previous = connection.execute(
                    f"SELECT quantity FROM products WHERE id = ?{lock_clause}",
                    (product_id,),
                ).fetchone()
                if previous is None:
                    raise LookupError("The product no longer exists.")
                cursor = connection.execute(
                    """UPDATE products SET sku = ?, name = ?, category = ?, unit = ?,
                    unit_price = ?, quantity = ?, reorder_level = ?, supplier = ?,
                    location = ? WHERE id = ?""",
                    (*self._product_values(values), product_id),
                )
                if cursor.rowcount != 1:
                    raise LookupError("The product no longer exists.")
                saved_id = product_id
                old_quantity = int(previous["quantity"])
                new_quantity = int(values["quantity"])
                if old_quantity != new_quantity:
                    connection.execute(
                        """INSERT INTO transactions
                        (product_id, sku, product_name, type, quantity, note, balance)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            product_id,
                            values["sku"],
                            values["name"],
                            "IN" if new_quantity > old_quantity else "OUT",
                            abs(new_quantity - old_quantity),
                            "Stock adjustment from product edit",
                            new_quantity,
                        ),
                    )
            connection.commit()
            return saved_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _product_values(values: dict[str, object]) -> tuple[object, ...]:
        return (
            values["sku"],
            values["name"],
            values["category"],
            values["unit"],
            values["unit_price"],
            values["quantity"],
            values["reorder_level"],
            values["supplier"],
            values["location"],
        )

    def delete_product(self, product_id: int) -> None:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
            if cursor.rowcount != 1:
                raise LookupError("The product no longer exists.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_movement(
        self, product_id: int, movement_type: str, quantity: int, note: str = ""
    ) -> int:
        if movement_type not in ("IN", "OUT") or quantity <= 0:
            raise ValueError("Invalid stock movement.")
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE" if self.postgres else ""
            product = connection.execute(
                f"SELECT * FROM products WHERE id = ?{lock_clause}",
                (product_id,),
            ).fetchone()
            if product is None:
                raise LookupError("The selected product no longer exists.")
            current = int(product["quantity"])
            if movement_type == "OUT" and quantity > current:
                raise ValueError(f"Only {current} available.")
            balance = current + quantity if movement_type == "IN" else current - quantity
            connection.execute(
                "UPDATE products SET quantity = ? WHERE id = ?", (balance, product_id)
            )
            connection.execute(
                """INSERT INTO transactions
                (product_id, sku, product_name, type, quantity, note, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    product["sku"],
                    product["name"],
                    movement_type,
                    quantity,
                    note.strip(),
                    balance,
                ),
            )
            connection.commit()
            return balance
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_transactions(
        self, limit: int | None = None, movement_type: str | None = None
    ) -> list[Transaction]:
        sql = "SELECT * FROM transactions"
        params: list[object] = []
        if movement_type is not None:
            sql += " WHERE type = ?"
            params.append(movement_type)
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._transaction(row) for row in rows]

    def dashboard_stats(self) -> tuple[int, float, int]:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS products,
                COALESCE(SUM(unit_price * quantity), 0) AS stock_value,
                COALESCE(SUM(CASE WHEN quantity <= reorder_level THEN 1 ELSE 0 END), 0)
                    AS low_stock
                FROM products"""
            ).fetchone()
        return int(row["products"]), float(row["stock_value"]), int(row["low_stock"])

    def seed_sample_data(self) -> None:
        samples = (
            ("PEN001", "Ballpoint Pens", "Office Supplies", "box", 4.50, 12, 5, "WriteWell", "A1-01"),
            ("BOX002", "Shipping Carton", "Packaging", "pcs", 1.25, 4, 5, "PackCo", "B2-03"),
            ("TOOL03", "Utility Knife", "Tools", "pcs", 8.99, 18, 3, "Handy Ltd", "C1-02"),
        )
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            insert = """INSERT INTO products
                (sku, name, category, unit, unit_price, quantity,
                 reorder_level, supplier, location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            if self.postgres:
                insert += " ON CONFLICT DO NOTHING"
            else:
                insert = insert.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
            connection.executemany(insert, samples)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def export_inventory(self, path: str | Path) -> None:
        import csv

        products = self.list_products()
        with Path(path).open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.writer(output)
            writer.writerow(
                ("SKU", "Name", "Category", "Unit", "Unit Price", "Quantity",
                 "Reorder Level", "Supplier", "Location", "Stock Value")
            )
            for product in products:
                writer.writerow(
                    (
                        product.sku, product.name, product.category, product.unit,
                        product.unit_price, product.quantity, product.reorder_level,
                        product.supplier, product.location,
                        f"{product.unit_price * product.quantity:.2f}",
                    )
                )

    def export_transactions(self, path: str | Path) -> None:
        import csv

        transactions = list(reversed(self.list_transactions()))
        with Path(path).open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.writer(output)
            writer.writerow(
                ("Timestamp", "SKU", "Product", "Type", "Quantity", "Note", "Balance")
            )
            for transaction in transactions:
                writer.writerow(
                    (
                        transaction.timestamp.isoformat(sep=" ", timespec="seconds"),
                        transaction.sku,
                        transaction.product_name,
                        transaction.type,
                        transaction.quantity,
                        transaction.note,
                        transaction.balance,
                    )
                )
