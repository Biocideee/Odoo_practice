import logging

from odoo import api, fields, models
from odoo.api import depends
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class NPWarehouse(models.Model):
    _name = "plugit.np_warehouse"
    _description = "Novaposhta warehouse"
    _rec_name = "description"

    key = fields.Char()
    ref = fields.Char("External ID")
    description = fields.Char(string="Опис", search=True)
    description_ru = fields.Char(search=True)
    short_address = fields.Char(string="Адреса")
    short_address_ru = fields.Char()
    phone = fields.Char(string="Телефон")
    type_ref = fields.Char("Type External ID")
    type_id = fields.Many2one("plugit.np_warehouse_type", string="Тип")
    number = fields.Char(string="Номер")
    settlement_ref = fields.Char("City External ID")
    settlement_id = fields.Many2one("plugit.np_settlement", string="Населений пункт")
    total_max_weight_allowed = fields.Float(string="Максимальна вага")
    place_max_weight_allowed = fields.Float(string="Максимальна вага на одне місце")
    sending_limitations_on_dimensions = fields.Char(string="Ліміт розмірів на відправлення")
    receiving_limitations_on_dimensions = fields.Char(string="Ліміт розмірів на отримання")
    reception_schedule = fields.Char(string="Графік приймання відправлень")
    delivery_schedule = fields.Char(string="Графік відправки день в день")
    schedule = fields.Char(string="Графік роботи")
    deny_to_select = fields.Boolean(string="Заборона вибору складу в ІД")
    status = fields.Char(string="Статус відділення")
    category = fields.Char(string="Категорія складу")
    np_target_type = fields.Char(compute="_compute_np_target_type", store=True)

    _sql_constraints = [
        ("ref_unique", "unique(ref)", "Ref should be unique."),
    ]

    fields_mapping = {
        "SiteKey": "key",
        "Ref": "ref",
        "Description": "description",
        "DescriptionRu": "description_ru",
        "ShortAddress": "short_address",
        "ShortAddressRu": "short_address_ru",
        "Phone": "phone",
        "TypeOfWarehouse": "type_ref",
        "Number": "number",
        "SettlementId": "settlement_id",
        "CityRef": "settlement_ref",
        "TotalMaxWeightAllowed": "total_max_weight_allowed",
        "PlaceMaxWeightAllowed": "place_max_weight_allowed",
        "SendingLimitationsOnDimensions": "sending_limitations_on_dimensions",
        "ReceivingLimitationsOnDimensions": "receiving_limitations_on_dimensions",
        "Reception": "reception_schedule",
        "Delivery": "delivery_schedule",
        "Schedule": "schedule",
        "DenyToSelect": "deny_to_select",
        "WarehouseStatus": "status",
        "CategoryOfWarehouse": "category",
    }

    @depends("type_id")
    def _compute_np_target_type(self):
        for rec in self:
            rec.np_target_type = rec.type_id and rec.type_id.np_target_type or False

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        domain = Domain.AND([["|", ("description", "ilike", name), ("description_ru", "ilike", name)], args or []])
        records = self.search_fetch(domain, ["id", "display_name"], limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]
