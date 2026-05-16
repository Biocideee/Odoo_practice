from odoo import http
from odoo.http import request


class DeliveryMockController(http.Controller):
    @http.route(
        "/wp-json/delivery-calendar/v1/dates",
        type="jsonrpc",  # Оновлено для Odoo 19
        auth="public",
        methods=["PUT"],
        csrf=False,
    )
    def mock_delivery_sync(self, **kwargs):
        data = request.get_json_data()
        print(f"--- MOCK RECEIVED DATES: {data.get('dates')} ---")
        return {"status": "success"}
