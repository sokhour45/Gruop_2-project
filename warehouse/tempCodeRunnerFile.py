
    @app.context_processor
    def inject_context() -> dict[str, Any]:
        return {
            "current_user": current_user(),
            "CATEGORIES": CATEGORIES,
            "UNITS": UNITS,
            "user_roles": ("admin", "manager", "employee"),
            "demo_admin_username": DEMO_ADMIN_USERNAME,
            "demo_admin_password": DEMO_ADMIN_PASSWORD,
        }