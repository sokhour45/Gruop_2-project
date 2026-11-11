import tkinter as tk
from tkinter import ttk

from warehouse.ui.common import Screen


class HistoryScreen(Screen):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text="Transaction History", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        ttk.Label(self, text="Review every inventory movement and resulting balance.",
                  style="CardBody.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 16))
        self.tree = self.make_tree(
            self, (("time", "Timestamp", 160), ("sku", "SKU", 90),
                   ("product", "Product", 165), ("type", "Type", 70),
                   ("quantity", "Quantity", 80), ("note", "Note", 200),
                   ("balance", "Resulting Balance", 130))
        )
        self.tree.grid(row=2, column=0, sticky="nsew")
    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for item in self.app.db.list_transactions():
            self.tree.insert(
                "", "end",
                values=(item.timestamp.strftime("%Y-%m-%d %H:%M:%S"), item.sku,
                        item.product_name, item.type, item.quantity, item.note, item.balance),
            )
