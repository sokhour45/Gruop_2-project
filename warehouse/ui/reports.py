import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from warehouse.ui.common import Screen


class ReportsScreen(Screen):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Reports", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="Download current warehouse data for analysis and record keeping.",
                  style="CardBody.TLabel").grid(
            row=1, column=0, sticky="w", pady=(5, 22)
        )
        cards = ttk.Frame(self)
        cards.grid(row=2, column=0, sticky="ew")
        cards.columnconfigure((0, 1), weight=1)
        self._report_card(
            cards, 0, "Inventory report",
            "Products, quantities, pricing, suppliers, and locations.",
            "Export Inventory CSV", self.export_inventory
        )
        self._report_card(
            cards, 1, "Transaction history",
            "A complete record of stock received and issued.",
            "Export Transactions CSV", self.export_transactions
        )

    def _report_card(self, parent: tk.Misc, column: int, title: str,
                     description: str, action: str, command) -> None:
        card = ttk.LabelFrame(parent, text="", style="Card.TLabelframe", padding=18)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 12) if column == 0 else (0, 0))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text=description, style="CardBody.TLabel",
                  wraplength=250).pack(anchor="w", pady=(8, 18))
        ttk.Button(card, text=action, style="Accent.TButton", command=command).pack(anchor="w")

    def export_inventory(self) -> None:
        self._export("inventory.csv", self.app.db.export_inventory, "Inventory report")

    def export_transactions(self) -> None:
        self._export("transactions.csv", self.app.db.export_transactions, "Transaction history")

    def _export(self, initial_name: str, export, label: str) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title=f"Export {label}", initialfile=initial_name,
            defaultextension=".csv", filetypes=(("CSV files", "*.csv"),)
        )
        if not path:
            return
        try:
            export(path)
            self.app.set_status(f"{label} exported.")
            messagebox.showinfo("Export complete", f"{label} saved successfully.", parent=self)
        except (OSError, sqlite3.Error) as error:
            self.app.report_error(f"Could not export {label.lower()}", error)
