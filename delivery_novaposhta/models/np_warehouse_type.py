import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class NPWarehouseType(models.Model):
    _name = "plugit.np_warehouse_type"
    _description = "Типи відділень"

    ref = fields.Char(string="External ID")
    name = fields.Char(string="Назва")
    np_target_type = fields.Selection([("warehouse", "Склад"), ("poshtomat", "Поштомат")])

    _sql_constraints = [
        ("ref_unique", "unique(ref)", "Ref should be unique."),
    ]
