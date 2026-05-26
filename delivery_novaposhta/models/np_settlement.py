import logging

from odoo import api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class NPSettlementType(models.Model):
    _name = "plugit.np_settlement_type"
    _description = "Типи населених пунктів"

    ref = fields.Char("Ref")
    name = fields.Char("Назва")
    short_name = fields.Char("Скорочена назва")


class NPSettlement(models.Model):
    _name = "plugit.np_settlement"
    _description = "Населені пункти"
    _rec_name = "full_name"

    ref = fields.Char(string="Ref")
    name = fields.Char(string="Назва")
    name_ru = fields.Char(string="Назва (ru)")
    region_id = fields.Many2one("plugit.np_region", string="Район")
    area_id = fields.Many2one("plugit.np_area", string="Область")
    settlement_type_id = fields.Many2one("plugit.np_settlement_type")
    full_name = fields.Char(compute="_compute_full_name", store=True)

    _sql_constraints = [
        ("ref_unique", "unique(ref)", "Ref should be unique."),
    ]

    @api.depends("name", "region_id.name", "region_id.type", "area_id.name", "area_id.type")
    def _compute_full_name(self):
        for record in self:
            if record.region_id.name:
                full_settlement = (
                    f"{record.settlement_type_id.short_name} {record.name}, {record.region_id.name} {record.region_id.type}, "
                    f"{record.area_id.name} {record.area_id.type}"
                )
            else:
                full_settlement = f"{record.settlement_type_id.short_name} {record.name}, {record.area_id.name} {record.area_id.type}"
            record.full_name = full_settlement

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        domain = Domain.AND([["|", ("name", "ilike", name), ("name_ru", "ilike", name)], args or []])
        records = self.search_fetch(domain, ["id", "display_name"], limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]
