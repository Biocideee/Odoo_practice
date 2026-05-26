from odoo import fields, models


class ProductTemplateDeliveryBase(models.Model):
    _inherit = "product.template"

    product_width = fields.Float(string="Ширина (см)", digits=(6, 2))
    product_length = fields.Float(string="Длина (см)", digits=(6, 2))
    product_depth = fields.Float(string="Глибина (см)", digits=(6, 2))
