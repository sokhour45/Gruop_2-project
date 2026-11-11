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
        self.minsize(760, 520)
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
        self.sidebar.configure(width=176)
        self.sidebar.grid_propagate(False)
        self.content = ttk.Frame(shell)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        brand = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        brand.pack(fill="x", padx=10, pady=(0, 26))
        ttk.Label(brand, text="W", style="BrandMark.TLabel").pack(side="left")
        ttk.Label(brand, text="WAREHOUSE", style="Brand.TLabel").pack(
            side="left", padx=9
        )
        ttk.Label(
            self.sidebar, text=f"Signed in as {self.current_user.username} ({self.current_user.role})",
            style="SidebarUser.TLabel"
        ).pack(anchor="w", padx=10, pady=(0, 12))
        ttk.Label(self.sidebar, text="WORKSPACE", style="SidebarSection.TLabel").pack(
            anchor="w", padx=10, pady=(4, 6)
        )
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
        self.nav_buttons: dict[str, ttk.Button] = {}
        for name, _ in pages:
            button = ttk.Button(
                self.sidebar, text=name, style="Nav.TButton",
                command=lambda page=name: self.show_page(page),
            )
            button.pack(fill="x", pady=2)
            self.nav_buttons[name] = button
        if self.current_user.role == "admin":
            button = ttk.Button(
                self.sidebar, text="User Accounts", style="Nav.TButton",
                command=lambda: self.show_page("User Accounts"),
            )
            button.pack(fill="x", pady=2)
            self.nav_buttons["User Accounts"] = button
            self.screens["User Accounts"] = UsersScreen(self.content, self)
        ttk.Frame(self.sidebar, style="Sidebar.TFrame").pack(fill="both", expand=True)
        ttk.Button(
            self.sidebar, text="Log out", style="Nav.TButton", command=self.logout
        ).pack(fill="x", pady=(10, 3))

        footer = ttk.Frame(self)
        footer.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = ttk.Label(footer, textvariable=self.status_var, padding=(18, 7))
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

        style.configure("TFrame", background="#f7f8fc")
        style.configure("Sidebar.TFrame", background="#0f172a")
        style.configure("Topbar.TFrame", background="#ffffff")
        style.configure("BrandMark.TLabel", background="#2563eb", foreground="#ffffff",
                        font=("Segoe UI", 14, "bold"), padding=(8, 5))
        style.configure("Brand.TLabel", background="#0f172a", foreground="#f8fafc",
                        font=("Segoe UI", 12, "bold"))
        style.configure("SidebarSection.TLabel", background="#0f172a", foreground="#6b7280",
                        font=("Segoe UI", 8, "bold"))
        style.configure("LoginBrand.TLabel", background="#f7f8fc", foreground="#4f46e5",
                        font=("Segoe UI", 13, "bold"))
        style.configure("LoginPanel.TFrame", background="#0f172a")
        style.configure("LoginPage.TFrame", background="#f1f5f9")
        style.configure("LoginPanelBrand.TLabel", background="#0f172a", foreground="#ffffff",
                        font=("Segoe UI", 9, "bold"))
        style.configure("LoginPanelTitle.TLabel", background="#0f172a", foreground="#ffffff",
                        font=("Segoe UI", 26, "bold"))
        style.configure("LoginPanelBody.TLabel", background="#0f172a", foreground="#cbd5e1",
                        font=("Segoe UI", 10))
        style.configure("LoginPanelFoot.TLabel", background="#0f172a", foreground="#64748b",
                        font=("Segoe UI", 8))
        style.configure("LoginCard.TFrame", background="#ffffff", relief="solid",
                        borderwidth=1)
        style.configure("LoginTitle.TLabel", background="#ffffff", foreground="#111827",
                        font=("Segoe UI", 16, "bold"))
        style.configure("LoginHint.TLabel", background="#ffffff", foreground="#6b7280",
                        font=("Segoe UI", 8))
        style.configure("LoginField.TLabel", background="#ffffff", foreground="#111827",
                        font=("Segoe UI", 8, "bold"))
        style.configure("LoginError.TLabel", background="#fee2e2", foreground="#991b1b",
                        font=("Segoe UI", 8), padding=(8, 7))
        style.configure("Login.TEntry", padding=(7, 6), fieldbackground="#ffffff",
                        borderwidth=1)
        style.configure("LoginInvalid.TEntry", padding=(7, 6), fieldbackground="#fff1f2",
                        borderwidth=1)
        style.configure("SidebarUser.TLabel", background="#111827", foreground="#9ca3af",
                        font=("Segoe UI", 9))
        style.configure("Nav.TButton", anchor="w", padding=(14, 10),
                        background="#0f172a", foreground="#d1d5db",
                        relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Nav.TButton", background=[("active", "#1d4ed8")],
                  foreground=[("active", "#ffffff")])
        style.configure("NavActive.TButton", anchor="w", padding=(14, 10),
                        background="#2563eb", foreground="#ffffff",
                        relief="flat", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background="#2563eb", foreground="white",
                        padding=(16, 10), relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#1d4ed8")],
                  foreground=[("active", "white")])
        style.configure("TopbarTitle.TLabel", background="#ffffff", foreground="#111827",
                        font=("Segoe UI", 11, "bold"))
        style.configure("TopbarUser.TLabel", background="#ffffff", foreground="#6b7280",
                        font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"),
                        foreground="#111827", background="#f7f8fc")
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"),
                        foreground="#111827", background="#f7f8fc")
        style.configure("Metric.TLabel", font=("Segoe UI", 22, "bold"),
                        foreground="#0f766e", background="#ffffff")
        style.configure("Treeview", rowheight=27, background="#ffffff",
                        fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#eef0f6", foreground="#4b5563")
        style.map("Treeview", background=[("selected", "#dbeafe")])
        style.configure("Card.TLabelframe", background="#ffffff", borderwidth=1,
                        relief="solid")
        style.configure("Card.TLabelframe.Label", background="#ffffff",
                        foreground="#111827", font=("Segoe UI", 10, "bold"))
        style.configure("CardBody.TLabel", background="#ffffff", foreground="#6b7280",
                        font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#111827",
                        font=("Segoe UI", 12, "bold"))
        style.configure("TButton", padding=(12, 8), font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", padding=(8, 7), fieldbackground="#ffffff")
        style.configure("TCombobox", padding=(7, 6), fieldbackground="#ffffff")
        style.configure("TCheckbutton", background="#f7f8fc", foreground="#4b5563")
        style.configure("Modal.TFrame", background="#ffffff")
        style.configure("Modal.TLabel", background="#ffffff", foreground="#374151",
                        font=("Segoe UI", 9, "bold"))
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
        for page, button in self.nav_buttons.items():
            button.configure(style="NavActive.TButton" if page == name else "Nav.TButton")
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
