from odoo import api, fields, models


class SaleOrderPlugit(models.Model):
    _inherit = "sale.order"

    full_delivery_address = fields.Char("Повна адреса доставки", related="partner_shipping_id.full_delivery_address")

    @api.depends("partner_id")
    def _compute_partner_shipping_id(self):
        super()._compute_partner_shipping_id()
        for order in self:
            if order.partner_id.default_delivery_address_id:
                order.partner_shipping_id = order.partner_id.default_delivery_address_id
