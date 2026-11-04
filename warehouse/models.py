from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str


@dataclass(frozen=True)
class Product:
    id: int | None
    sku: str
    name: str
    category: str
    unit: str
    unit_price: float
    quantity: int
    reorder_level: int
    supplier: str
    location: str


@dataclass(frozen=True)
class Transaction:
    id: int
    sku: str
    product_name: str
    type: str
    quantity: int
    note: str
    balance: int
    timestamp: datetime
