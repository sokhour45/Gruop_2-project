from warehouse.ui.stock_movement import StockMovementScreen


class StockOutScreen(StockMovementScreen):
    movement_type = "OUT"
    title = "Stock Out"
    action = "Issue Stock"
