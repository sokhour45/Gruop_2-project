from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for

from warehouse.db import WarehouseDB
from warehouse.validation import CATEGORIES, UNITS, FieldError, validate_product, validate_movement


def create_app(database: WarehouseDB | None = None) -> Flask:
    base_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )
    app.config["SECRET_KEY"] = "warehouse-web-secret-key"
    db = database or WarehouseDB()

    if not db.has_users():
        db.seed_sample_data()

    def current_user() -> dict[str, str] | None:
        user = session.get("user")
        if not isinstance(user, dict):
            return None
        return user

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                return redirect(url_for("login_page"))
            return view(*args, **kwargs)

        return wrapped

    def role_required(*allowed_roles):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                user = current_user()
                if user is None:
                    return redirect(url_for("login_page"))
                if user.get("role") not in allowed_roles:
                    flash("You do not have permission for that action.", "error")
                    return redirect(url_for("dashboard"))
                return view(*args, **kwargs)

            return wrapped

        return decorator

    def user_list() -> list[dict[str, str | int]]:
        return [
            {"id": user.id, "username": user.username, "role": user.role}
            for user in db.list_users()
        ]

    @app.context_processor
    def inject_context() -> dict[str, Any]:
        return {
            "current_user": current_user(),
            "CATEGORIES": CATEGORIES,
            "UNITS": UNITS,
            "user_roles": ("admin", "manager", "employee"),
        }

    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        setup_mode = not db.has_users()
        register_mode = request.args.get("register") == "1"
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            if setup_mode or register_mode:
                if not username or not password:
                    flash("Enter both a username and password.", "error")
                elif len(password) < 8:
                    flash("Password must be at least 8 characters.", "error")
                elif password != confirm:
                    flash("Passwords do not match.", "error")
                else:
                    try:
                        db.create_user(username, password, "admin" if setup_mode else "employee")
                    except ValueError as error:
                        flash(str(error), "error")
                        return render_template(
                            "login.html",
                            setup_mode=setup_mode,
                            register_mode=register_mode,
                            username=username,
                        )
                    if setup_mode:
                        user = db.authenticate_user(username, password)
                        if user is None:
                            flash("The administrator account could not be loaded.", "error")
                            return render_template(
                                "login.html",
                                setup_mode=setup_mode,
                                register_mode=register_mode,
                                username=username,
                            )
                        session["user"] = {"id": user.id, "username": user.username, "role": user.role}
                        return redirect(url_for("dashboard"))
                    flash("Account created. You can now sign in.", "success")
                    return redirect(url_for("login_page"))
            else:
                user = db.authenticate_user(username, password)
                if user is None:
                    flash("Invalid username or password.", "error")
                    return render_template(
                        "login.html",
                        setup_mode=False,
                        register_mode=False,
                        username=username,
                    )
                session["user"] = {"id": user.id, "username": user.username, "role": user.role}
                return redirect(url_for("dashboard"))
        return render_template(
            "login.html",
            setup_mode=setup_mode,
            register_mode=register_mode,
            username="",
        )

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_page"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        total_products, stock_value, low_stock_count = db.dashboard_stats()
        categories = {}
        for product in db.list_products():
            categories[product.category] = categories.get(product.category, 0) + 1
        return render_template(
            "dashboard.html",
            total_products=total_products,
            stock_value=stock_value,
            low_stock_count=low_stock_count,
            category_totals=categories,
            low_products=db.list_products(low_stock=True),
            recent_transactions=db.list_transactions(limit=12),
            page_title="Dashboard",
        )

    @app.route("/products", methods=["GET"])
    @login_required
    def products():
        search = request.args.get("search", "").strip()
        low_stock_only = request.args.get("low_stock", "") == "1"
        category = request.args.get("category", "").strip()
        product_list = db.list_products(search=search, low_stock=low_stock_only, category=category)
        categories = sorted({product.category for product in db.list_products()})
        return render_template(
            "products.html",
            products=product_list,
            categories=categories,
            current_search=search,
            current_category=category,
            low_stock_only=low_stock_only,
            page_title="Products",
        )

    @app.route("/products/new", methods=["GET", "POST"])
    @login_required
    def add_product():
        if request.method == "POST":
            values = {key: request.form.get(key, "") for key in (
                "sku", "name", "category", "unit", "unit_price", "quantity",
                "reorder_level", "supplier", "location"
            )}
            normalized, errors = validate_product(values, db.sku_exists)
            if errors:
                flash("Please fix the highlighted fields.", "error")
                return render_template(
                    "product_form.html",
                    product=None,
                    values=values,
                    errors=errors,
                    title="Add Product",
                    action="/products/new",
                    page_title="Add Product",
                )
            db.save_product(normalized)
            flash("Product saved.", "success")
            return redirect(url_for("products"))
        return render_template(
            "product_form.html",
            product=None,
            values={},
            errors=[],
            title="Add Product",
            action="/products/new",
            page_title="Add Product",
        )

    @app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin", "manager")
    def edit_product(product_id: int):
        product = db.get_product(product_id)
        if product is None:
            flash("That product no longer exists.", "error")
            return redirect(url_for("products"))
        if request.method == "POST":
            values = {key: request.form.get(key, "") for key in (
                "sku", "name", "category", "unit", "unit_price", "quantity",
                "reorder_level", "supplier", "location"
            )}
            normalized, errors = validate_product(values, lambda sku: db.sku_exists_for_other(sku, product_id))
            if errors:
                flash("Please fix the highlighted fields.", "error")
                return render_template(
                    "product_form.html",
                    product=product,
                    values=values,
                    errors=errors,
                    title="Edit Product",
                    action=f"/products/{product_id}/edit",
                    page_title="Edit Product",
                )
            db.save_product(normalized, product_id)
            flash("Product updated.", "success")
            return redirect(url_for("products"))
        return render_template(
            "product_form.html",
            product=product,
            values={
                "sku": product.sku,
                "name": product.name,
                "category": product.category,
                "unit": product.unit,
                "unit_price": str(product.unit_price),
                "quantity": str(product.quantity),
                "reorder_level": str(product.reorder_level),
                "supplier": product.supplier,
                "location": product.location,
            },
            errors=[],
            title="Edit Product",
            action=f"/products/{product_id}/edit",
            page_title="Edit Product",
        )

    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin", "manager")
    def delete_product(product_id: int):
        product = db.get_product(product_id)
        if product is None:
            flash("That product no longer exists.", "error")
            return redirect(url_for("products"))
        db.delete_product(product_id)
        flash(f"Deleted product {product.sku}.", "success")
        return redirect(url_for("products"))

    @app.route("/stock-in", methods=["GET", "POST"])
    @login_required
    def stock_in():
        if request.method == "POST":
            product_id = request.form.get("product_id")
            quantity = request.form.get("quantity", "")
            note = request.form.get("note", "")
            product = db.get_product(int(product_id)) if product_id else None
            if product is None:
                flash("Choose a product from the list.", "error")
                return redirect(url_for("stock_in"))
            valid_quantity, errors = validate_movement(quantity, "IN", product.quantity)
            if errors:
                flash("; ".join(error.message for error in errors), "error")
                return render_template(
                    "stock_movement.html",
                    title="Stock In",
                    movement_type="IN",
                    action_url="/stock-in",
                    products=db.list_products(),
                    selected_product=product,
                    quantity=quantity,
                    note=note,
                    errors=errors,
                    page_title="Stock In",
                )
            db.record_movement(product.id, "IN", valid_quantity, note)
            flash(f"Stock movement saved. New balance: {product.quantity + valid_quantity}.", "success")
            return redirect(url_for("stock_in"))
        return render_template(
            "stock_movement.html",
            title="Stock In",
            movement_type="IN",
            action_url="/stock-in",
            products=db.list_products(),
            selected_product=None,
            quantity="",
            note="",
            errors=[],
            page_title="Stock In",
        )

    @app.route("/stock-out", methods=["GET", "POST"])
    @login_required
    def stock_out():
        if request.method == "POST":
            product_id = request.form.get("product_id")
            quantity = request.form.get("quantity", "")
            note = request.form.get("note", "")
            product = db.get_product(int(product_id)) if product_id else None
            if product is None:
                flash("Choose a product from the list.", "error")
                return redirect(url_for("stock_out"))
            valid_quantity, errors = validate_movement(quantity, "OUT", product.quantity)
            if errors:
                flash("; ".join(error.message for error in errors), "error")
                return render_template(
                    "stock_movement.html",
                    title="Stock Out",
                    movement_type="OUT",
                    action_url="/stock-out",
                    products=db.list_products(),
                    selected_product=product,
                    quantity=quantity,
                    note=note,
                    errors=errors,
                    page_title="Stock Out",
                )
            db.record_movement(product.id, "OUT", valid_quantity, note)
            flash(f"Stock movement saved. New balance: {product.quantity - valid_quantity}.", "success")
            return redirect(url_for("stock_out"))
        return render_template(
            "stock_movement.html",
            title="Stock Out",
            movement_type="OUT",
            action_url="/stock-out",
            products=db.list_products(),
            selected_product=None,
            quantity="",
            note="",
            errors=[],
            page_title="Stock Out",
        )

    @app.route("/history")
    @login_required
    def history():
        return render_template(
            "history.html",
            transactions=db.list_transactions(),
            page_title="Transaction History",
        )

    @app.route("/reports")
    @login_required
    def reports_page():
        return render_template("reports.html", page_title="Reports")

    @app.route("/export/inventory.csv")
    @login_required
    def export_inventory_csv():
        import io
        buffer = io.StringIO()
        writer = __import__("csv").writer(buffer)
        writer.writerow([
            "SKU", "Name", "Category", "Unit", "Unit Price", "Quantity",
            "Reorder Level", "Supplier", "Location", "Stock Value",
        ])
        for product in db.list_products():
            writer.writerow([
                product.sku,
                product.name,
                product.category,
                product.unit,
                product.unit_price,
                product.quantity,
                product.reorder_level,
                product.supplier,
                product.location,
                f"{product.unit_price * product.quantity:.2f}",
            ])
        output = buffer.getvalue().encode("utf-8-sig")
        return send_file(
            __import__("io").BytesIO(output),
            mimetype="text/csv",
            as_attachment=True,
            download_name="inventory.csv",
        )

    @app.route("/export/transactions.csv")
    @login_required
    def export_transactions_csv():
        import io
        buffer = io.StringIO()
        writer = __import__("csv").writer(buffer)
        writer.writerow(["Timestamp", "SKU", "Product", "Type", "Quantity", "Note", "Balance"])
        for transaction in list(reversed(db.list_transactions())):
            writer.writerow([
                transaction.timestamp.isoformat(sep=" ", timespec="seconds"),
                transaction.sku,
                transaction.product_name,
                transaction.type,
                transaction.quantity,
                transaction.note,
                transaction.balance,
            ])
        output = buffer.getvalue().encode("utf-8-sig")
        return send_file(
            __import__("io").BytesIO(output),
            mimetype="text/csv",
            as_attachment=True,
            download_name="transactions.csv",
        )

    @app.route("/users")
    @login_required
    @role_required("admin")
    def users():
        return render_template("users.html", users=user_list(), page_title="User Accounts")

    @app.route("/users/<int:user_id>/role", methods=["POST"])
    @login_required
    @role_required("admin")
    def update_user_role(user_id: int):
        role = request.form.get("role", "employee")
        try:
            db.update_user_role(user_id, role)
            flash("User role updated.", "success")
        except (ValueError, LookupError) as error:
            flash(str(error), "error")
        return redirect(url_for("users"))

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app


app = create_app()
