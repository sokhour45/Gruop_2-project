"""Entry point and main window for the warehouse system."""

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from warehouse.db import WarehouseDB
from warehouse.ui.dashboard import DashboardScreen
from warehouse.ui.history import HistoryScreen
from warehouse.ui.login import LoginScreen
from warehouse.ui.products import ProductsScreen
from warehouse.ui.reports import ReportsScreen
from warehouse.ui.stock_in import StockInScreen
from warehouse.ui.stock_out import StockOutScreen
from warehouse.ui.users import UsersScreen
from warehouse.models import User


class WarehouseApp(tk.Tk):
    def __init__(self, db: WarehouseDB | None = None):
        super().__init__()
        self.db = db or WarehouseDB()
        self.title("Small Warehouse Management System")
        self.geometry("1180x720")
        self.minsize(920, 580)
        self.configure(bg="#f3f5f7")
        self._configure_styles()
        self.current_user: User | None = None
        self.login_screen = LoginScreen(self, self)
        self.login_screen.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def login_successful(self, user: User) -> None:
        self.current_user = user
        self.login_screen.destroy()
        self._build_shell()

    def _build_shell(self) -> None:

        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(1, weight=1)
        self.sidebar = ttk.Frame(shell, style="Sidebar.TFrame", padding=(10, 18))
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.content = ttk.Frame(shell)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        ttk.Label(self.sidebar, text="WAREHOUSE", style="Brand.TLabel").pack(
            anchor="w", padx=10, pady=(0, 18)
        )
        ttk.Label(
            self.sidebar, text=f"Signed in as {self.current_user.username} ({self.current_user.role})",
            style="SidebarUser.TLabel"
        ).pack(anchor="w", padx=10, pady=(0, 12))
        all_pages = (
            ("Dashboard", DashboardScreen),
            ("Products", ProductsScreen),
            ("Stock In", StockInScreen),
            ("Stock Out", StockOutScreen),
            ("History", HistoryScreen),
            ("Reports", ReportsScreen),
        )
        pages = tuple(
            page for page in all_pages
            if self.current_user.role != "employee"
            or page[0] not in {"Stock In", "Stock Out"}
        )
        self.screens = {
            name: screen_class(self.content, self) for name, screen_class in pages
        }
        for name, _ in pages:
            ttk.Button(
                self.sidebar, text=name, style="Nav.TButton",
                command=lambda page=name: self.show_page(page),
            ).pack(fill="x", pady=3)
        if self.current_user.role == "admin":
            ttk.Button(
                self.sidebar, text="User Accounts", style="Nav.TButton",
                command=lambda: self.show_page("User Accounts"),
            ).pack(fill="x", pady=3)
            self.screens["User Accounts"] = UsersScreen(self.content, self)
        ttk.Button(
            self.sidebar, text="Log out", style="Nav.TButton", command=self.logout
        ).pack(fill="x", pady=(18, 3))

        footer = ttk.Frame(self)
        footer.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = ttk.Label(footer, textvariable=self.status_var, padding=(10, 6))
        self.status_label.pack(fill="x")
        self.show_page("Dashboard")

    def logout(self) -> None:
        if not messagebox.askyesno("Log out", "Do you want to log out?", parent=self):
            return
        for child in self.winfo_children():
            child.destroy()
        self.current_user = None
        self.login_screen = LoginScreen(self, self)
        self.login_screen.pack(fill="both", expand=True)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("TFrame", background="#eef3ff")
        style.configure("Sidebar.TFrame", background="#0f172a")
        style.configure("Brand.TLabel", background="#0f172a", foreground="#e2e8f0",
                        font=("Segoe UI", 13, "bold"))
        style.configure("LoginBrand.TLabel", background="#eef3ff", foreground="#2563eb",
                        font=("Segoe UI", 13, "bold"))
        style.configure("SidebarUser.TLabel", background="#0f172a", foreground="#94a3b8",
                        font=("Segoe UI", 9))
        style.configure("Nav.TButton", anchor="w", padding=(14, 10),
                        background="#111827", foreground="#f8fafc",
                        relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Nav.TButton", background=[("active", "#1e293b")],
                  foreground=[("active", "#f8fafc")])
        style.configure("Accent.TButton", background="#2563eb", foreground="white",
                        padding=(14, 10), relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#1d4ed8")],
                  foreground=[("active", "white")])
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"),
                        foreground="#0f172a", background="#eef3ff")
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"),
                        foreground="#0f172a", background="#eef3ff")
        style.configure("Metric.TLabel", font=("Segoe UI", 22, "bold"),
                        foreground="#0f766e", background="#ffffff")
        style.configure("Treeview", rowheight=27, background="#ffffff",
                        fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#e2e8f0")
        style.map("Treeview", background=[("selected", "#dbeafe")])
        style.configure("Invalid.TEntry", fieldbackground="#fff1f2")
        style.configure("Invalid.TCombobox", fieldbackground="#fff1f2")

    def show_page(self, name: str) -> None:
        if (
            self.current_user is not None
            and self.current_user.role == "employee"
            and name in {"Stock In", "Stock Out"}
        ):
            self.set_status("Employees cannot use stock in or stock out.", error=True)
            return
        for screen in self.screens.values():
            screen.grid_forget()
        screen = self.screens[name]
        screen.grid(row=0, column=0, sticky="nsew")
        self.refresh_all()

    def refresh_all(self) -> None:
        for screen in self.screens.values():
            self.refresh_screen(screen)

    def refresh_screen(self, screen: ttk.Frame) -> bool:
        try:
            screen.refresh()
            return True
        except sqlite3.Error as error:
            self.report_error("Could not refresh data", error)
            return False

    def set_status(self, message: str, error: bool = False) -> None:
        self.status_var.set(message)
        self.status_label.configure(foreground="#b42318" if error else "#344054")

    def report_error(self, action: str, error: Exception) -> None:
        message = str(error).strip() or "The operation could not be completed."
        self.set_status(f"{action}: {message}", error=True)
        messagebox.showerror(action, message, parent=self)


def main() -> None:
    try:
        app = WarehouseApp()
        app.mainloop()
    except Exception as error:
        messagebox.showerror(
            "Warehouse could not start",
            f"The application could not start.\n\n{error}",
        )


if __name__ == "__main__":
    main()
