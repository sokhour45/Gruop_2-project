"""Administrator screen for managing registered users."""

import tkinter as tk
from tkinter import messagebox, ttk

from warehouse.ui.common import Screen


class UsersScreen(Screen):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        self.selected_id: int | None = None
        ttk.Label(self, text="User accounts", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self, text="Manage access levels for registered accounts. New registrations default to employee.",
            style="CardBody.TLabel"
        ).pack(anchor="w", pady=(4, 14))
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 10))
        self.role_var = tk.StringVar(value="employee")
        ttk.Label(actions, text="Selected role:").pack(side="left")
        ttk.Combobox(
            actions, textvariable=self.role_var,
            values=("admin", "manager", "employee"), state="readonly", width=16
        ).pack(side="left", padx=8)
        ttk.Button(actions, text="Save role", style="Accent.TButton",
                   command=self.save_role).pack(side="left")
        self.tree = self.make_tree(
            self, (("username", "Username", 280), ("role", "Role", 180))
        )
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select_user)

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for user in self.app.db.list_users():
            self.tree.insert("", "end", iid=str(user.id), values=(user.username, user.role))
        self.selected_id = None

    def select_user(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.selected_id = int(selection[0])
        self.role_var.set(self.tree.set(selection[0], "role"))

    def save_role(self) -> None:
        if self.selected_id is None:
            messagebox.showerror("Select a user", "Select an account first.", parent=self)
            return
        try:
            self.app.db.update_user_role(self.selected_id, self.role_var.get())
        except (ValueError, LookupError) as error:
            self.app.report_error("Could not update role", error)
            return
        self.app.set_status("User role updated.")
        self.refresh()
