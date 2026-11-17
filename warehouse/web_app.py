from __future__ import annotations

from datetime import date, timedelta
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
                stored_user = db.get_user(user["id"])
                if stored_user is None:
                    session.clear()
                    return redirect(url_for("login_page"))
                user = {
                    "id": stored_user.id,
                    "username": stored_user.username,
                    "role": stored_user.role,
                }
                session["user"] = user
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
        products = db.list_products()
        categories = {}
        for product in products:
            categories[product.category] = categories.get(product.category, 0) + 1
        out_of_stock_count = sum(product.quantity == 0 for product in products)
        reorder_count = sum(
            0 < product.quantity <= product.reorder_level for product in products
        )
        healthy_count = total_products - out_of_stock_count - reorder_count
        product_count = len(products)

        def percent(count: int) -> int:
            return round(count / product_count * 100) if product_count else 0

        return render_template(
            "dashboard.html",
            total_products=total_products,
            stock_value=stock_value,
            low_stock_count=low_stock_count,
            total_units=sum(product.quantity for product in products),
            out_of_stock_count=out_of_stock_count,
            stock_health={
                "healthy": healthy_count,
                "healthy_percent": percent(healthy_count),
                "reorder": reorder_count,
                "reorder_percent": percent(reorder_count),
                "out_of_stock": out_of_stock_count,
                "out_of_stock_percent": percent(out_of_stock_count),
            },
            category_totals=categories,
            category_max=max(categories.values(), default=0),
            low_products=db.list_products(low_stock=True),
            recent_transactions=db.list_transactions(limit=8),
            page_title="Dashboard",
        )

    @app.route("/products", methods=["GET"])
    @login_required
    def products():
        search = request.args.get("search", "").strip()
        low_stock_only = request.args.get("low_stock", "") == "1"
        out_of_stock_only = request.args.get("out_of_stock", "") == "1"
        category = request.args.get("category", "").strip()
        all_products = db.list_products()
        product_list = db.list_products(search=search, low_stock=low_stock_only, category=category)
        if out_of_stock_only:
            product_list = [product for product in product_list if product.quantity == 0]
        total_products = len(all_products)
        return render_template(
            "products.html",
            products=product_list,
            categories=sorted({product.category for product in all_products}),
            current_search=search,
            current_category=category,
            low_stock_only=low_stock_only,
            out_of_stock_only=out_of_stock_only,
            total_products=total_products,
            total_units=sum(product.quantity for product in all_products),
            low_stock_count=sum(
                product.quantity <= product.reorder_level for product in all_products
            ),
            stock_value=sum(
                product.unit_price * product.quantity for product in all_products
            ),
            filtered_count=len(product_list),
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

    def render_stock_movement(
        movement_type: str,
        selected_product=None,
        quantity: str = "",
        note: str = "",
        errors=(),
        form_error: str = "",
    ):
        products = db.list_products()
        is_inbound = movement_type == "IN"
        movement_title = "Stock In" if is_inbound else "Stock Out"
        recent_transactions = db.list_transactions(limit=5, movement_type=movement_type)
        return render_template(
            "stock_movement.html",
            title=movement_title,
            subtitle=(
                "Record received goods and update available inventory."
                if is_inbound
                else "Issue picked goods and prevent stock from going below zero."
            ),
            movement_type=movement_type,
            action_url=url_for("stock_in" if is_inbound else "stock_out"),
            products=products,
            selected_product=selected_product,
            quantity=quantity,
            note=note,
            errors=errors,
            form_error=form_error,
            total_products=len(products),
            total_units=sum(product.quantity for product in products),
            available_sku_count=sum(product.quantity > 0 for product in products),
            reorder_count=sum(
                product.quantity <= product.reorder_level for product in products
            ),
            recent_transactions=recent_transactions,
            page_title=movement_title,
        )

    @app.route("/stock-in", methods=["GET", "POST"])
    @login_required
    def stock_in():
        if request.method == "POST":
            product_id_text = request.form.get("product_id", "")
            quantity = request.form.get("quantity", "")
            note = request.form.get("note", "").strip()
            try:
                product_id = int(product_id_text)
            except ValueError:
                product_id = 0
            product = db.get_product(product_id) if product_id > 0 else None
            if product is None:
                return render_stock_movement(
                    "IN", quantity=quantity, note=note,
                    form_error="Choose a valid product from the list.",
                )
            valid_quantity, errors = validate_movement(quantity, "IN", product.quantity)
            if errors:
                return render_stock_movement(
                    "IN", product, quantity, note, errors=errors
                )
            try:
                balance = db.record_movement(product.id, "IN", valid_quantity, note)
            except (LookupError, ValueError) as error:
                current_product = db.get_product(product.id)
                return render_stock_movement(
                    "IN",
                    current_product,
                    quantity,
                    note,
                    form_error=str(error),
                )
            flash(f"Stock movement saved. New balance: {balance}.", "success")
            return redirect(url_for("stock_in"))
        return render_stock_movement("IN")

    @app.route("/stock-out", methods=["GET", "POST"])
    @login_required
    def stock_out():
        if request.method == "POST":
            product_id_text = request.form.get("product_id", "")
            quantity = request.form.get("quantity", "")
            note = request.form.get("note", "").strip()
            try:
                product_id = int(product_id_text)
            except ValueError:
                product_id = 0
            product = db.get_product(product_id) if product_id > 0 else None
            if product is None:
                return render_stock_movement(
                    "OUT", quantity=quantity, note=note,
                    form_error="Choose a valid product from the list.",
                )
            valid_quantity, errors = validate_movement(quantity, "OUT", product.quantity)
            if errors:
                return render_stock_movement(
                    "OUT", product, quantity, note, errors=errors
                )
            try:
                balance = db.record_movement(product.id, "OUT", valid_quantity, note)
            except (LookupError, ValueError) as error:
                current_product = db.get_product(product.id)
                return render_stock_movement(
                    "OUT",
                    current_product,
                    quantity,
                    note,
                    form_error=str(error),
                )
            flash(f"Stock movement saved. New balance: {balance}.", "success")
            return redirect(url_for("stock_out"))
        return render_stock_movement("OUT")

    @app.route("/history")
    @login_required
    def history():
        search = request.args.get("search", "").strip()
        movement_type = request.args.get("movement_type", "").upper()
        if movement_type not in {"", "IN", "OUT"}:
            movement_type = ""
            filter_error = "Choose a valid movement type."
        else:
            filter_error = ""

        def parse_date_filter(field: str) -> date | None:
            nonlocal filter_error
            value = request.args.get(field, "").strip()
            if not value:
                return None
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                filter_error = "Use valid dates in YYYY-MM-DD format."
                return None
            if parsed.isoformat() != value:
                filter_error = "Use valid dates in YYYY-MM-DD format."
                return None
            return parsed

        from_date = parse_date_filter("from_date")
        to_date = parse_date_filter("to_date")
        if from_date and to_date and from_date > to_date:
            filter_error = "The start date must be on or before the end date."
            from_date = to_date = None

        all_transactions = db.list_transactions()
        filtered_transactions = [
            transaction
            for transaction in all_transactions
            if (not movement_type or transaction.type == movement_type)
            and (
                not search
                or search.lower()
                in f"{transaction.sku} {transaction.product_name} {transaction.note}".lower()
            )
            and (not from_date or transaction.timestamp.date() >= from_date)
            and (not to_date or transaction.timestamp.date() <= to_date)
        ]
        page_size = 50
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        total_matches = len(filtered_transactions)
        page_count = max(1, (total_matches + page_size - 1) // page_size)
        page = min(page, page_count)
        page_start = (page - 1) * page_size
        return render_template(
            "history.html",
            transactions=filtered_transactions[page_start:page_start + page_size],
            total_transactions=len(all_transactions),
            total_matches=total_matches,
            inbound_units=sum(
                transaction.quantity for transaction in all_transactions
                if transaction.type == "IN"
            ),
            outbound_units=sum(
                transaction.quantity for transaction in all_transactions
                if transaction.type == "OUT"
            ),
            current_search=search,
            current_movement_type=movement_type,
            current_from_date=from_date.isoformat() if from_date else "",
            current_to_date=to_date.isoformat() if to_date else "",
            filter_error=filter_error,
            page=page,
            page_count=page_count,
            page_start=page_start,
            first_result=page_start + 1 if total_matches else 0,
            last_result=min(page_start + page_size, total_matches),
            page_title="Transaction History",
        )

    @app.route("/reports")
    @login_required
    def reports_page():
        products = db.list_products()
        transactions = db.list_transactions()
        categories = {}
        for product in products:
            summary = categories.setdefault(
                product.category,
                {"product_count": 0, "units": 0, "stock_value": 0.0},
            )
            summary["product_count"] += 1
            summary["units"] += product.quantity
            summary["stock_value"] += product.unit_price * product.quantity

        recent_cutoff = date.today() - timedelta(days=30)
        recent_transactions = [
            transaction
            for transaction in transactions
            if transaction.timestamp.date() >= recent_cutoff
        ]
        low_products = sorted(
            (product for product in products if product.quantity <= product.reorder_level),
            key=lambda product: (product.quantity, product.name.lower()),
        )
        return render_template(
            "reports.html",
            total_products=len(products),
            total_units=sum(product.quantity for product in products),
            stock_value=sum(
                product.unit_price * product.quantity for product in products
            ),
            low_stock_count=len(low_products),
            inbound_units=sum(
                transaction.quantity for transaction in recent_transactions
                if transaction.type == "IN"
            ),
            outbound_units=sum(
                transaction.quantity for transaction in recent_transactions
                if transaction.type == "OUT"
            ),
            recent_movement_count=len(recent_transactions),
            category_summary=sorted(categories.items()),
            category_max=max(
                (summary["units"] for summary in categories.values()), default=0
            ),
            low_products=low_products[:5],
            page_title="Reports",
        )

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
        account_list = user_list()
        role_counts = {
            role: sum(user["role"] == role for user in account_list)
            for role in ("admin", "manager", "employee")
        }
        return render_template(
            "users.html",
            users=account_list,
            role_counts=role_counts,
            current_user_id=current_user()["id"],
            page_title="User Accounts",
        )

    @app.route("/users/<int:user_id>/role", methods=["POST"])
    @login_required
    @role_required("admin")
    def update_user_role(user_id: int):
        role = request.form.get("role", "employee")
        if current_user()["id"] == user_id and role != "admin":
            flash("You cannot remove your own administrator access.", "error")
            return redirect(url_for("users"))
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
