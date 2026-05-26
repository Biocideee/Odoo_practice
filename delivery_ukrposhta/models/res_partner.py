from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Область — використовуємо стандартне Odoo-поле `state_id` (Many2one на
    # res.country.state). Дані вже є — для України Odoo підвантажує всі області
    # через модуль `base.l10n`. Так уникнули дублювання та друкарських помилок.
    #
    # Район — окрема концепція, у стандарті Odoo нема Char-еквівалента, тому
    # залишаємо як власне поле.
    ukrposhta_district = fields.Char(string="Район (Укрпошта)")
