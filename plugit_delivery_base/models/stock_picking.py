from odoo import fields, models
from odoo.api import onchange


class StockPickingPlugit(models.Model):
    _inherit = "stock.picking"

    full_delivery_address = fields.Char("Повна адреса", related="sale_id.full_delivery_address", store=True)

    @onchange("sale_id")
    def get_delivery_from_sale(self):
        self.carrier_id = self.sale_id.carrier_id
