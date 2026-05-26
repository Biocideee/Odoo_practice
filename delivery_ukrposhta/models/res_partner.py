from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Поля для адреси Укрпошти. У стандарті Odoo `region` та `district`
    # відсутні (`state_id` — це область, окремого Char-у для району немає).
    # Використовуємо власні поля з префіксом ukrposhta_, щоб не конфліктувати
    # з можливими розширеннями інших модулів.
    ukrposhta_region = fields.Char(string="Область (Укрпошта)")
    ukrposhta_district = fields.Char(string="Район (Укрпошта)")
