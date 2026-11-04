import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from warehouse.ui.common import Screen


class ReportsScreen(Screen):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        ttk.Label(self, text="Reports", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="Export a CSV snapshot for spreadsheets or record keeping.").grid(
            row=1, column=0, sticky="w", pady=12
        )
        ttk.Button(self, text="Export Inventory CSV", command=self.export_inventory).grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Button(self, text="Export Transaction History CSV", command=self.export_transactions).grid(
            row=3, column=0, sticky="w", pady=4
        )

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
