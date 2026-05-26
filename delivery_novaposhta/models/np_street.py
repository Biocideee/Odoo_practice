import logging

from odoo import api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class NPStreet(models.Model):
    _name = "plugit.np_street"
    _description = "Вулиці"
    _rec_name = "item_name"

    ref = fields.Char(string="Ref")
    np_settlement_id = fields.Many2one("plugit.np_settlement", string="Населений пункт")
    name = fields.Char(string="Назва")
    name_ru = fields.Char(string="Назва російскою (для пошуку)")
    street_type = fields.Char(string="Тип")
    item_name = fields.Char(compute="_item_name", store=True)

    _sql_constraints = [
        ("ref_unique", "unique(ref)", "Ref should be unique."),
    ]

    @api.depends("name", "np_settlement_id.full_name")
    def _item_name(self):
        for rec in self:
            rec.item_name = f"{rec.name}, {rec.np_settlement_id.full_name}"

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        domain = Domain.AND([["|", ("name", "ilike", name), ("name_ru", "ilike", name)], args or []])
        records = self.search_fetch(domain, ["id", "display_name"], limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]
