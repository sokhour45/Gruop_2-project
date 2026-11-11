"""Login and first-user setup screen."""

import tkinter as tk
from tkinter import messagebox, ttk


class LoginScreen(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent)
        self.app = app
        self.setup_mode = not app.db.has_users()
        self.register_mode = False
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.confirm_password = tk.StringVar()
        self.error_message = tk.StringVar()
        self._build()

    def _build(self) -> None:
        self.configure(style="LoginPage.TFrame")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        panel = ttk.Frame(self, padding=(40, 38), style="LoginPanel.TFrame")
        panel.grid(row=0, column=0, sticky="nsew")
        ttk.Label(panel, text="WAREHOUSE", style="LoginPanelBrand.TLabel").grid(
            row=0, column=0, sticky="nw"
        )
        message = ttk.Frame(panel, style="LoginPanel.TFrame")
        message.grid(row=1, column=0, sticky="sw", pady=(0, 0))
        ttk.Label(message, text="Know what is on\nevery shelf.",
                  style="LoginPanelTitle.TLabel").pack(anchor="w")
        ttk.Label(
            message, text="Track products, receive and issue stock, and see\n"
            "low-stock alerts in one place.",
            style="LoginPanelBody.TLabel"
        ).pack(anchor="w", pady=(12, 0))
        ttk.Label(panel, text="Small Warehouse Management System",
                  style="LoginPanelFoot.TLabel").grid(row=2, column=0, sticky="sw",
                                                      pady=(0, 0))
        panel.rowconfigure(1, weight=1)

        content = ttk.Frame(self, style="LoginPage.TFrame")
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)

        card = ttk.Frame(content, padding=(20, 20), style="LoginCard.TFrame")
        card.grid(row=1, column=0)
        card.columnconfigure(0, weight=1)
        title = "Create administrator account" if self.setup_mode else (
            "Register account" if self.register_mode else "Sign in"
        )
        description = (
            "Create the first administrator account." if self.setup_mode
            else ("New accounts are registered as employees." if self.register_mode
                  else "Use your warehouse account.")
        )
        ttk.Label(card, text=title, style="LoginTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        ttk.Label(card, text=description, style="LoginHint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 12)
        )
        self.error_label = ttk.Label(
            card, textvariable=self.error_message, style="LoginError.TLabel",
            wraplength=250, justify="left"
        )
        self.error_label.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.error_label.grid_remove()
        form_offset = 3
        row = form_offset
        ttk.Label(card, text="Username", style="LoginField.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        username_entry = ttk.Entry(card, textvariable=self.username, width=30,
                                   style="Login.TEntry")
        username_entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, 9))
        row += 1
        ttk.Label(card, text="Password", style="LoginField.TLabel").grid(
            row=row + 1, column=0, sticky="w", pady=(0, 4)
        )
        password_entry = ttk.Entry(card, textvariable=self.password, show="*", width=30,
                                   style="Login.TEntry")
        password_entry.grid(row=row + 2, column=0, sticky="ew", pady=(0, 9))
        row += 2
        if self.setup_mode or self.register_mode:
            row += 1
            ttk.Label(card, text="Confirm password", style="LoginField.TLabel").grid(
                row=row, column=0, sticky="w", pady=(0, 4)
            )
            confirm_entry = ttk.Entry(card, textvariable=self.confirm_password, show="*",
                                      width=30, style="Login.TEntry")
            confirm_entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, 9))
        action_row = row + (2 if self.setup_mode or self.register_mode else 1)
        button_text = (
            "Create account" if self.setup_mode
            else ("Register account" if self.register_mode else "Log in")
        )
        ttk.Button(card, text=button_text, style="Accent.TButton", command=self.submit).grid(
            row=action_row, column=0, sticky="ew", pady=(2, 0)
        )
        if not self.setup_mode:
            ttk.Button(
                card,
                text="Back to sign in" if self.register_mode else "Create new account",
                command=self.toggle_register,
            ).grid(row=action_row + 1, column=0, sticky="ew", pady=(8, 0))
        password_entry.bind("<Return>", lambda _event: self.submit())
        for variable in (self.username, self.password, self.confirm_password):
            variable.trace_add("write", lambda *_args: self._clear_error())
        username_entry.focus_set()

    def _clear_error(self) -> None:
        self.error_message.set("")
        self.error_label.grid_remove()
        for child in self.winfo_children():
            self._reset_entries(child)

    def _reset_entries(self, widget: tk.Misc) -> None:
        if isinstance(widget, ttk.Entry):
            widget.configure(style="Login.TEntry")
        for child in widget.winfo_children():
            self._reset_entries(child)

    def _show_error(self, message: str, *entries: ttk.Entry) -> None:
        self.error_message.set(message)
        self.error_label.grid()
        for entry in entries:
            entry.configure(style="LoginInvalid.TEntry")

    def submit(self) -> None:
        self._clear_error()
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self._show_error("Enter both a username and password.")
            return
        if self.setup_mode or self.register_mode:
            if len(password) < 8:
                self._show_error("Password must be at least 8 characters.")
                return
            if password != self.confirm_password.get():
                self._show_error("Passwords do not match.")
                return
            try:
                self.app.db.create_user(
                    username, password, "admin" if self.setup_mode else "employee"
                )
            except ValueError as error:
                self._show_error(str(error))
                return
            if self.setup_mode:
                user = self.app.db.authenticate_user(username, password)
                if user is None:
                    self._show_error("The administrator account could not be loaded.")
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
                self.password.set("")
                self._show_error("Invalid username or password.")
                return
            self.app.login_successful(user)

    def toggle_register(self) -> None:
        self.register_mode = not self.register_mode
        for child in self.winfo_children():
            child.destroy()
        self._build()
