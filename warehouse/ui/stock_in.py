from warehouse.ui.stock_movement import StockMovementScreen


class StockInScreen(StockMovementScreen):
    movement_type = "IN"
    title = "Stock In"
    action = "Receive Stock"
