"""Login and first-user setup screen."""

import tkinter as tk
from tkinter import messagebox, ttk


class LoginScreen(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, padding=32)
        self.app = app
        self.setup_mode = not app.db.has_users()
        self.register_mode = False
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.confirm_password = tk.StringVar()
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        card = ttk.Frame(self, padding=34)
        card.grid(row=0, column=0)
        ttk.Label(card, text="WAREHOUSE", style="LoginBrand.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 8)
        )
        title = (
            "Create administrator account"
            if self.setup_mode
            else ("Register account" if self.register_mode else "Sign in")
        )
        ttk.Label(card, text=title, style="Title.TLabel").grid(
            row=1, column=0, columnspan=2, pady=(0, 20)
        )
        if self.setup_mode or self.register_mode:
            description = (
                "Create the first administrator account."
                if self.setup_mode
                else "New accounts are registered as employees."
            )
            ttk.Label(card, text=description).grid(
                row=2, column=0, columnspan=2, pady=(0, 12)
            )
        row = 3
        ttk.Label(card, text="Username").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        username_entry = ttk.Entry(card, textvariable=self.username, width=30)
        username_entry.grid(row=row, column=1, pady=6)
        row += 1
        ttk.Label(card, text="Password").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        password_entry = ttk.Entry(card, textvariable=self.password, show="*", width=30)
        password_entry.grid(row=row, column=1, pady=6)
        if self.setup_mode or self.register_mode:
            row += 1
            ttk.Label(card, text="Confirm password").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=6
            )
            confirm_entry = ttk.Entry(card, textvariable=self.confirm_password, show="*", width=30)
            confirm_entry.grid(row=row, column=1, pady=6)
        action_row = row + 1
        button_text = (
            "Create account" if self.setup_mode
            else ("Register account" if self.register_mode else "Log in")
        )
        ttk.Button(card, text=button_text, style="Accent.TButton", command=self.submit).grid(
            row=action_row, column=0, columnspan=2, sticky="ew", pady=(18, 0)
        )
        if not self.setup_mode:
            ttk.Button(
                card,
                text="Back to sign in" if self.register_mode else "Create new account",
                command=self.toggle_register,
            ).grid(row=action_row + 1, column=0, columnspan=2, pady=(8, 0))
        password_entry.bind("<Return>", lambda _event: self.submit())
        username_entry.focus_set()

    def submit(self) -> None:
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            messagebox.showerror("Login required", "Enter both a username and password.", parent=self)
            return
        if self.setup_mode or self.register_mode:
            if len(password) < 8:
                messagebox.showerror(
                    "Password too short", "Use a password with at least 8 characters.", parent=self
                )
                return
            if password != self.confirm_password.get():
                messagebox.showerror("Passwords do not match", "Enter the same password twice.", parent=self)
                return
            try:
                self.app.db.create_user(
                    username, password, "admin" if self.setup_mode else "employee"
                )
            except ValueError as error:
                messagebox.showerror("Could not create account", str(error), parent=self)
                return
            if self.setup_mode:
                user = self.app.db.authenticate_user(username, password)
                if user is None:
                    messagebox.showerror(
                        "Could not sign in",
                        "The administrator account was created but could not be loaded.",
                        parent=self,
                    )
                    return
                self.app.login_successful(user)
            else:
                self.toggle_register()
                messagebox.showinfo(
                    "Account created",
                    "Your employee account was created. You can now sign in.",
                    parent=self,
                )
            return
        else:
            user = self.app.db.authenticate_user(username, password)
            if user is None:
                messagebox.showerror("Sign-in failed", "Invalid username or password.", parent=self)
                self.password.set("")
                return
            self.app.login_successful(user)

    def toggle_register(self) -> None:
        self.register_mode = not self.register_mode
        for child in self.winfo_children():
            child.destroy()
        self._build()
