import tkinter as tk
from tkinter import ttk

from warehouse.ui.common import Screen


class DashboardScreen(Screen):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text="Dashboard", style="Title.TLabel").grid(row=0, column=0, sticky="w")

        metrics = ttk.Frame(self)
        metrics.grid(row=1, column=0, sticky="ew", pady=14)
        self.metric_labels: dict[str, ttk.Label] = {}
        for index, (key, label) in enumerate(
            (("products", "Total Products"), ("value", "Total Stock Value"),
             ("low", "Low-Stock Items"))
        ):
            card = ttk.LabelFrame(metrics, text=label, padding=(16, 14),
                                  style="Card.TLabelframe")
            card.grid(row=0, column=index, sticky="ew", padx=(0, 12))
            metrics.columnconfigure(index, weight=1)
            value = ttk.Label(card, text="0", style="Metric.TLabel")
            value.pack(anchor="center")
            self.metric_labels[key] = value

        chart_area = ttk.Frame(self)
        chart_area.grid(row=2, column=0, sticky="nsew")
        chart_area.columnconfigure(0, weight=1)
        chart_area.columnconfigure(1, weight=1)
        chart_area.rowconfigure(0, weight=1)

        category_card = ttk.LabelFrame(chart_area, text="", style="Card.TLabelframe",
                                       padding=(10, 8))
        category_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        category_card.columnconfigure(0, weight=1)
        category_card.rowconfigure(0, weight=1)
        self.category_canvas = tk.Canvas(category_card, width=320, height=270, bg="#ffffff",
                                        highlightthickness=0)
        self.category_canvas.grid(row=0, column=0, sticky="nsew")
        self.category_canvas.bind("<Button-1>", self._select_category)
        status_card = ttk.LabelFrame(chart_area, text="", style="Card.TLabelframe",
                                     padding=(10, 8))
        status_card.grid(row=0, column=1, sticky="nsew")
        status_card.columnconfigure(0, weight=1)
        status_card.rowconfigure(0, weight=1)
        self.status_canvas = tk.Canvas(status_card, width=320, height=220, bg="#ffffff",
                                     highlightthickness=0)
        self.status_canvas.grid(row=0, column=0, sticky="nsew")

        panels = ttk.Frame(self)
        panels.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        panels.columnconfigure((0, 1), weight=1)
        panels.rowconfigure(1, weight=1)
        ttk.Label(panels, text="Low-Stock Alerts", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(4, 8)
        )
        ttk.Label(panels, text="Recent Transactions", style="Heading.TLabel").grid(
            row=0, column=1, sticky="w", pady=(4, 8)
        )
        self.low_tree = self.make_tree(
            panels, (("sku", "SKU", 90), ("name", "Name", 150),
                     ("quantity", "Stock", 70), ("reorder", "Reorder At", 85))
        )
        self.low_tree.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.recent_tree = self.make_tree(
            panels, (("time", "Time", 145), ("sku", "SKU", 85),
                     ("type", "Type", 60), ("quantity", "Qty", 55),
                     ("balance", "Balance", 75))
        )
        self.recent_tree.grid(row=1, column=1, sticky="nsew")

    def refresh(self) -> None:
        count, value, low_count = self.app.db.dashboard_stats()
        self.metric_labels["products"].configure(text=str(count))
        self.metric_labels["value"].configure(text=f"${value:,.2f}")
        self.metric_labels["low"].configure(text=str(low_count))

        self._draw_category_chart()
        self._draw_status_chart()

        self.low_tree.delete(*self.low_tree.get_children())
        for product in self.app.db.list_products(low_stock=True):
            self.low_tree.insert(
                "", "end", values=(product.sku, product.name, product.quantity,
                                  product.reorder_level), tags=("low_stock",)
            )
        self.recent_tree.delete(*self.recent_tree.get_children())
        for transaction in self.app.db.list_transactions(limit=12):
            self.recent_tree.insert(
                "", "end",
                values=(transaction.timestamp.strftime("%Y-%m-%d %H:%M"),
                        transaction.sku, transaction.type, transaction.quantity,
                        transaction.balance),
            )

    def _draw_category_chart(self) -> None:
        self.category_canvas.delete("all")
        products = self.app.db.list_products()
        if not products:
            self.category_canvas.create_text(160, 110, text="No products", fill="#64748b",
                                             font=("Segoe UI", 12, "bold"))
            return
        self.category_canvas.create_text(160, 16, text="Products by Category",
                                         fill="#0f172a", font=("Segoe UI", 11, "bold"))
        self.category_canvas.create_text(160, 32, text="Click a category to view its products",
                                         fill="#64748b", font=("Segoe UI", 8))
        self.category_canvas.create_text(10, 106, text="Products", angle=90,
                                         fill="#64748b", font=("Segoe UI", 8))
        category_counts: dict[str, int] = {}
        for product in products:
            category_counts[product.category] = category_counts.get(product.category, 0) + 1
        colors = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6"]
        max_count = max(category_counts.values())
        width = 260
        left = 32
        gap = 14
        bar_width = (width - (len(category_counts) - 1) * gap) / max(1, len(category_counts))
        for index, (category, count) in enumerate(category_counts.items()):
            x0 = left + index * (bar_width + gap)
            h = 120 * count / max_count if max_count else 0
            y0 = 182 - h
            self.category_canvas.create_rectangle(
                x0, y0, x0 + bar_width, 182,
                fill=colors[index % len(colors)], outline="", tags=("category_bar", category)
            )
            self.category_canvas.create_text(
                x0 + bar_width / 2, y0 + h / 2,
                text=category.replace(" ", "\n"),
                fill="#ffffff", font=("Segoe UI", 8, "bold"),
                tags=("category_bar", category),
            )
            self.category_canvas.create_text(x0 + bar_width / 2, y0 - 8, text=str(count),
                                             fill="#0f172a", font=("Segoe UI", 8, "bold"),
                                             tags=("category_bar", category))
        self.category_canvas.create_line(24, 182, 304, 182, fill="#94a3b8", width=1)
        legend_y = 215
        legend_columns = 2
        legend_width = 150
        for index, (category, _) in enumerate(category_counts.items()):
            column = index % legend_columns
            row = index // legend_columns
            x = 25 + column * legend_width
            y = legend_y + row * 22
            self.category_canvas.create_rectangle(
                x, y - 7, x + 12, y + 5,
                fill=colors[index % len(colors)], outline="",
                tags=("category_bar", category),
            )
            self.category_canvas.create_text(
                x + 18, y - 1, text=category, anchor="w",
                fill="#334155", font=("Segoe UI", 8),
                tags=("category_bar", category),
            )

    def _select_category(self, event: tk.Event) -> None:
        selected = self.category_canvas.find_withtag("current")
        if not selected:
            return
        tags = self.category_canvas.gettags(selected[0])
        if len(tags) > 1 and tags[0] == "category_bar":
            self.app.screens["Products"].set_category(tags[1])

    def _draw_status_chart(self) -> None:
        self.status_canvas.delete("all")
        products = self.app.db.list_products()
        if not products:
            self.status_canvas.create_text(160, 110, text="No stock data", fill="#64748b",
                                          font=("Segoe UI", 12, "bold"))
            return
        self.status_canvas.create_text(160, 16, text="Stock Status",
                                       fill="#0f172a", font=("Segoe UI", 11, "bold"))
        low = sum(1 for product in products if product.quantity <= product.reorder_level)
        healthy = max(len(products) - low, 0)
        total = max(len(products), 1)
        slices = [(healthy, "#10b981", "Healthy"), (low, "#ef4444", "Low")]
        start = 0
        cx, cy = 140, 110
        radius = 68
        visible_slices = [(value, color, label) for value, color, label in slices if value > 0]
        if len(visible_slices) == 1:
            value, color, _ = visible_slices[0]
            self.status_canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                           fill=color, outline="")
        else:
            for value, color, label in visible_slices:
                angle = 360 * (value / total)
                self.status_canvas.create_arc(
                    cx - radius, cy - radius, cx + radius, cy + radius,
                    start=start, extent=angle, fill=color, outline="", style="pieslice"
                )
                start += angle
        self.status_canvas.create_oval(cx - 36, cy - 36, cx + 36, cy + 36, fill="#f8fbff",
                                       outline="")
        center_value = low if low else healthy
        center_label = "Low" if low else "Healthy"
        self.status_canvas.create_text(cx, cy, text=f"{center_value}", fill="#0f172a",
                                      font=("Segoe UI", 18, "bold"))
        self.status_canvas.create_text(cx, cy + 24, text=center_label, fill="#64748b",
                                      font=("Segoe UI", 9))
        legend_y = 180
        for value, color, label in visible_slices:
            self.status_canvas.create_rectangle(225, legend_y - 8, 240, legend_y + 8,
                                               fill=color, outline="")
            self.status_canvas.create_text(250, legend_y, text=f"{label}: {value}", anchor="w",
                                          fill="#334155", font=("Segoe UI", 9))
            legend_y += 22
