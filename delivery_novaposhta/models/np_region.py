import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class NPRegion(models.Model):
    _name = "plugit.np_region"
    _description = "Райони та громади областей"

    ref = fields.Char(string="External ID")
    name = fields.Char(string="Назва")
    type = fields.Char(string="Тип")
    area_id = fields.Many2one("plugit.np_area", string="Область")

    _sql_constraints = [
        ("ref_unique", "unique(ref)", "Ref should be unique."),
    ]
