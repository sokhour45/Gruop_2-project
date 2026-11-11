import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from warehouse.models import Product
from warehouse.ui.common import ModalForm, Screen
from warehouse.validation import FieldError, validate_movement


class StockMovementScreen(Screen):
    movement_type = "IN"
    title = "Stock"
    action = "Submit"

    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text=self.title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            self, text="Choose a product and enter the movement details in the form.",
            style="CardBody.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        control_bar = ttk.Frame(self)
        control_bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(control_bar, text=f"New {self.title}", style="Accent.TButton",
                   command=self.open_form).pack(side="left")
        ttk.Button(control_bar, text="Refresh", command=lambda: self.app.refresh_screen(self)).pack(side="left", padx=(8, 0))

        self.products: list[Product] = []
        self.tree = self.make_tree(
            self,
            (("sku", "SKU", 90), ("name", "Name", 170), ("category", "Category", 130),
             ("unit", "Unit", 60), ("quantity", "Available", 90), ("reorder", "Reorder", 80),
             ("location", "Location", 120))
        )
        self.tree.grid(row=3, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=3, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self.open_form())

    def refresh(self) -> None:
        self.products = self.app.db.list_products()
        self.tree.delete(*self.tree.get_children())
        for product in self.products:
            tags = ("low_stock",) if product.quantity <= product.reorder_level else ()
            self.tree.insert(
                "", "end",
                values=(product.sku, product.name, product.category, product.unit,
                        product.quantity, product.reorder_level, product.location),
                tags=tags,
            )

    def open_form(self) -> None:
        if not self.app.refresh_screen(self):
            return
        if not self.products:
            messagebox.showinfo("No products", "Add a product before recording stock.", parent=self)
            return
        MovementForm(self, self.app, self.products, self.movement_type, self.action)


class MovementForm(ModalForm):
    def __init__(
        self,
        parent: StockMovementScreen,
        app: "WarehouseApp",
        products: list[Product],
        movement_type: str,
        action: str,
    ):
        super().__init__(parent, action, app)
        self.parent_screen = parent
        self.products = products
        self.movement_type = movement_type
        self.action = action
        self.validated_product: Product | None = None
        self.validated_quantity: int | None = None
        self.product_by_label = {
            f"{product.sku} - {product.name} (available: {product.quantity})": product
            for product in products
        }
        frame = ttk.Frame(self, padding=22, style="Modal.TFrame")
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Product", style="Modal.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.product_choice = ttk.Combobox(
            frame, values=list(self.product_by_label), state="readonly", width=42
        )
        self.product_choice.grid(row=0, column=1, sticky="ew", pady=5)
        self.fields["product"] = self.product_choice
        self.add_entry(frame, 1, "quantity", "Quantity", "")
        self.add_entry(frame, 2, "note", "Note (optional)", "")
        buttons = ttk.Frame(frame, style="Modal.TFrame")
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(15, 0))
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text=action, command=self.submit).pack(side="right")
        self.bind("<Return>", lambda _event: self.submit())
        self.product_choice.focus_set()

    def submit(self) -> None:
        if not self.gate(self.validate_form):
            return
        product = self.validated_product
        quantity_value = self.validated_quantity
        if product is None or quantity_value is None:
            return
        if not messagebox.askyesno(
            "Confirm stock change",
            f"{self.action} {quantity_value} {product.unit} of {product.name}?",
            parent=self,
        ):
            return
        try:
            balance = self.app.db.record_movement(
                product.id, self.movement_type, quantity_value, self.fields["note"].get()
            )
            self.app.set_status(f"Stock movement saved. New balance: {balance}.")
            self.app.refresh_all()
            self.finish()
        except (sqlite3.Error, LookupError, ValueError) as error:
            self.app.report_error("Could not record stock movement", error)
            self.focus_field("quantity")

    def validate_form(self) -> tuple[bool, list[FieldError]]:
        self.validated_product = self.product_by_label.get(self.product_choice.get())
        errors: list[FieldError] = []
        if self.validated_product is None:
            errors.append(FieldError("product", "Choose a product from the list."))
        quantity, quantity_errors = validate_movement(
            self.fields["quantity"].get(),
            self.movement_type,
            self.validated_product.quantity if self.validated_product is not None else None,
        )
        self.validated_quantity = quantity
        errors.extend(quantity_errors)
        return not errors, errors
