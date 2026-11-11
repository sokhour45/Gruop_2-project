import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from warehouse.models import Product
from warehouse.ui.common import ModalForm, Screen
from warehouse.validation import CATEGORIES, UNITS, FieldError, validate_product


class ProductsScreen(Screen):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text="Products", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        actions = ttk.Frame(self)
        actions.grid(row=1, column=0, sticky="ew", pady=12)
        ttk.Label(actions, text="Search").pack(side="left")
        self.search_var = tk.StringVar()
        search = ttk.Entry(actions, textvariable=self.search_var, width=30)
        search.pack(side="left", padx=8)
        search.bind("<KeyRelease>", lambda _event: self.app.refresh_screen(self))
        ttk.Label(actions, text="Category").pack(side="left", padx=(12, 0))
        self.category_var = tk.StringVar(value="All categories")
        self.category_filter = ttk.Combobox(
            actions, textvariable=self.category_var, state="readonly", width=18
        )
        self.category_filter.pack(side="left", padx=8)
        self.category_filter.bind("<<ComboboxSelected>>",
                                  lambda _event: self.app.refresh_screen(self))
        self.low_only = tk.BooleanVar()
        ttk.Checkbutton(actions, text="Low stock only", variable=self.low_only,
                        command=lambda: self.app.refresh_screen(self)).pack(side="left", padx=8)
        ttk.Button(actions, text="Add Product", style="Accent.TButton",
                   command=self.add_product).pack(side="right", padx=4)
        if self.app.current_user.role != "employee":
            ttk.Button(actions, text="Edit", command=self.edit_selected).pack(side="right", padx=4)
            ttk.Button(actions, text="Delete", command=self.delete_selected).pack(side="right", padx=4)

        columns = (
            ("sku", "SKU", 95), ("name", "Name", 165), ("category", "Category", 130),
            ("unit", "Unit", 60), ("price", "Unit Price", 90), ("quantity", "In Stock", 80),
            ("reorder", "Reorder At", 85), ("supplier", "Supplier", 120),
            ("location", "Location", 100), ("status", "Status", 90),
        )
        self.tree = self.make_tree(self, columns)
        self.tree.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        if self.app.current_user.role != "employee":
            self.tree.bind("<Double-1>", lambda _event: self.edit_selected())

    def refresh(self) -> None:
        categories = sorted({product.category for product in self.app.db.list_products()})
        category_values = ["All categories", *categories]
        selected_category = self.category_var.get()
        self.category_filter.configure(values=category_values)
        if selected_category not in category_values:
            self.category_var.set("All categories")
        category = "" if self.category_var.get() == "All categories" else self.category_var.get()

        self.tree.delete(*self.tree.get_children())
        for product in self.app.db.list_products(
            self.search_var.get(), self.low_only.get(), category
        ):
            tags = ("low_stock",) if product.quantity <= product.reorder_level else ()
            status = "Low stock" if product.quantity <= product.reorder_level else "Healthy"
            self.tree.insert(
                "", "end", iid=str(product.id),
                values=(product.sku, product.name, product.category, product.unit,
                        f"{product.unit_price:.2f}", product.quantity,
                        product.reorder_level, product.supplier, product.location, status),
                tags=tags,
            )

    def set_category(self, category: str) -> None:
        self.category_var.set(category)
        self.app.show_page("Products")

    def selected_product(self) -> Product | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a product", "Select a product row first.", parent=self)
            return None
        try:
            product = self.app.db.get_product(int(selection[0]))
        except sqlite3.Error as error:
            self.app.report_error("Could not load product", error)
            return None
        if product is None:
            messagebox.showerror("Product not found", "That product no longer exists.", parent=self)
            self.app.refresh_screen(self)
        return product

    def add_product(self) -> None:
        ProductForm(self, self.app)

    def edit_selected(self) -> None:
        if self.app.current_user.role == "employee":
            self.app.set_status("Employees can only add products.", error=True)
            return
        product = self.selected_product()
        if product is not None:
            ProductForm(self, self.app, product)

    def delete_selected(self) -> None:
        if self.app.current_user.role == "employee":
            self.app.set_status("Employees can only add products.", error=True)
            return
        product = self.selected_product()
        if product is None:
            return
        if not messagebox.askyesno(
            "Delete product", f"Delete {product.sku} - {product.name}?",
            icon="warning", parent=self,
        ):
            return
        try:
            self.app.db.delete_product(product.id)
            self.app.set_status(f"Deleted product {product.sku}.")
            self.app.refresh_all()
        except (sqlite3.Error, LookupError) as error:
            self.app.report_error("Could not delete product", error)


class ProductForm(ModalForm):
    def __init__(self, parent: ProductsScreen, app: "WarehouseApp", product: Product | None = None):
        super().__init__(parent, "Edit Product" if product else "Add Product", app)
        self.parent_screen = parent
        self.product = product
        self.validated_values: dict[str, object] = {}
        container = ttk.Frame(self, padding=22, style="Modal.TFrame")
        container.grid(sticky="nsew")
        defaults = {
            "sku": product.sku if product else "",
            "name": product.name if product else "",
            "category": product.category if product else "",
            "unit": product.unit if product else "",
            "unit_price": str(product.unit_price) if product else "",
            "quantity": str(product.quantity) if product else "0",
            "reorder_level": str(product.reorder_level) if product else "0",
            "supplier": product.supplier if product else "",
            "location": product.location if product else "",
        }
        fields = (
            ("sku", "SKU", defaults["sku"], "entry"),
            ("name", "Name", defaults["name"], "entry"),
            ("category", "Category", defaults["category"], "category"),
            ("unit", "Unit", defaults["unit"], "unit"),
            ("unit_price", "Unit price", defaults["unit_price"], "entry"),
            ("quantity", "Quantity in stock", defaults["quantity"], "entry"),
            ("reorder_level", "Reorder level", defaults["reorder_level"], "entry"),
            ("supplier", "Supplier", defaults["supplier"], "entry"),
            ("location", "Location (rack/shelf)", defaults["location"], "entry"),
        )
        for index, (key, label, value, kind) in enumerate(fields):
            row, column = divmod(index, 2)
            cell = ttk.Frame(container, style="Modal.TFrame")
            cell.grid(row=row, column=column, sticky="ew", padx=(0, 10) if column == 0 else (10, 0),
                     pady=(0, 12))
            ttk.Label(cell, text=label, style="Modal.TLabel").pack(anchor="w", pady=(0, 5))
            if kind == "category":
                widget = ttk.Combobox(cell, values=CATEGORIES, state="readonly", width=25)
                widget.set(value)
            elif kind == "unit":
                widget = ttk.Combobox(cell, values=UNITS, state="readonly", width=25)
                widget.set(value)
            else:
                widget = ttk.Entry(cell, width=28)
                widget.insert(0, value)
            widget.pack(fill="x")
            self.fields[key] = widget
        container.columnconfigure((0, 1), weight=1)

        buttons = ttk.Frame(container)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(4, 0))
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save", command=self.submit).pack(side="right")
        self.bind("<Return>", lambda _event: self.submit())
        self.fields["sku"].focus_set()

    def submit(self) -> None:
        try:
            valid = self.gate(self.validate_form)
        except sqlite3.Error as error:
            self.app.report_error("Could not validate product", error)
            self.focus_field("sku")
            return
        if not valid:
            return
        if (
            self.product is not None
            and self.product.quantity != self.validated_values["quantity"]
        ):
            difference = int(self.validated_values["quantity"]) - self.product.quantity
            movement = "increase" if difference > 0 else "decrease"
            if not messagebox.askyesno(
                "Confirm stock adjustment",
                f"This will {movement} stock by {abs(difference)} and record the change "
                "in transaction history. Continue?",
                parent=self,
            ):
                return
        try:
            self.app.db.save_product(
                self.validated_values, self.product.id if self.product else None
            )
            self.app.set_status("Product saved.")
            self.app.refresh_all()
            self.finish()
        except (sqlite3.Error, LookupError) as error:
            self.app.report_error("Could not save product", error)
            self.focus_field("sku")

    def validate_form(self) -> tuple[bool, list[FieldError]]:
        sku_exists = self.app.db.sku_exists
        if self.product is not None:
            sku_exists = lambda sku: self.app.db.sku_exists_for_other(sku, self.product.id)
        values, errors = validate_product(self.field_values(), sku_exists)
        self.validated_values.clear()
        self.validated_values.update(values)
        return not errors, errors
