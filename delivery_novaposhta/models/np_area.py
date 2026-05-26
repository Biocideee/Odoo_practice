import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class NPArea(models.Model):
    _name = "plugit.np_area"
    _description = "Області"

    ref = fields.Char(string="External ID")
    name = fields.Char(string="Назва")
    type = fields.Char(string="Тип")

    _sql_constraints = [
        ("ref_unique", "unique(ref)", "Ref should be unique."),
    ]
