from odoo import fields, models


class UkrposhtaTtnParcels(models.Model):
    _name = "plugit.ukrposhta_ttn_parcels"
    _description = "Місця ТТН Укрпошти"
    _order = "sequence, id"

    sequence = fields.Integer(string="Послідовність", default=10)
    ukrposhta_ttn_id = fields.Many2one("plugit.ukrposhta_ttn", string="ТТН Укрпошти", ondelete="cascade")
    weight = fields.Float(string="Вага, кг")
    length = fields.Float(string="Довжина, см")
    height = fields.Float(string="Висота, см")
    description = fields.Char(string="Опис")
    uuid = fields.Char(string="UUID")
    currency_id = fields.Many2one(
        "res.currency", string="Валюта",
        default=lambda self: self.env.company.currency_id.id,
    )
    declared_price = fields.Monetary(string="Оголошена вартість", currency_field="currency_id")
