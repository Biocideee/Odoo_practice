from odoo import _, api, fields, models

from odoo.addons.plugit_delivery_base.models.res_partner import PlugitDeliveryPartner


class TargetTypes:
    warehouse = "warehouse"
    poshtomat = "poshtomat"
    courier = "courier"


target_type_list = [(TargetTypes.warehouse, "Поштове відділення"), (TargetTypes.poshtomat, "Поштомат"), (TargetTypes.courier, "Адреса")]


class PlugitNovaposhtaPartner(models.Model):
    _inherit = "res.partner"

    np_target_type = fields.Selection(target_type_list, string="Вид доставки")
    np_settlement_id = fields.Many2one("plugit.np_settlement", string="Місто")
    np_warehouse_id = fields.Many2one("plugit.np_warehouse", string="Склад", domain=[("deny_to_select", "=", False)])
    np_street_id = fields.Many2one("plugit.np_street", string="Вулиця")
    contact_person_name = fields.Char(string="Ім'я")
    contact_middle_name = fields.Char(string="По-батькові")
    contact_person_surname = fields.Char(string="Прізвище")

    np_counterparty_ref = fields.Char(string="Ідентифікатор контрагента в базі НП")
    np_contact_person_ref = fields.Char(string="Ідентифікатор контакта в базі НП")
    np_address_ref = fields.Char(string="Ідентифікатор адреси в базі НП")

    address_tokens = PlugitDeliveryPartner.address_tokens + [
        "np_settlement_id",
        "np_warehouse_id",
        "np_target_type",
        "np_street_id",
        "phone",
    ]

    @api.onchange("carrier_id")
    def onchange_np_data(self):
        if self.carrier_id.delivery_type != "novaposhta":
            self.np_target_type = False
            self.np_settlement_id = False
            self.np_warehouse_id = False
            self.np_street_id = False
        else:
            self.country_id = self.env.ref("base.ua").id

    @api.onchange("np_target_type")
    def onchange_settlement_id(self):
        if self.np_target_type in ("poshtomat", "warehouse"):
            self.np_street_id = False
            self.house_number = False
            self.apart_number = False
        else:
            self.np_warehouse_id = False

    def get_full_address(self, record):
        if record.carrier_id.delivery_type == "novaposhta":
            address = []
            type_repr = ""
            if record.np_target_type == "courier":
                type_repr = _("Адреса")
                address.append(record.np_settlement_id and record.np_settlement_id.full_name)
                address.append(record.np_street_id and f"{record.np_street_id.name}")
                address.append(record.house_number and f"б. {record.house_number}")
                address.append(record.apart_number and f"кв. {record.apart_number}")
                address.append(record.phone and f"тел. {record.phone}")
            else:
                address.append(record.np_warehouse_id and record.np_warehouse_id.description)
                address.append(record.phone and f"тел. {record.phone}")
            type_repr = f"{type_repr}: " if type_repr else ""
            address = [token for token in address if token]
            record.full_delivery_address = f"{record.carrier_id.delivery_type_label}: {type_repr}{', '.join(address)}"
        else:
            super().get_full_address(record)

    @api.depends(*address_tokens)
    def _compute_full_delivery_address(self):
        # Just extend the depends decorator
        super()._compute_full_delivery_address()

    @api.onchange("carrier_type", "np_target_type", "np_settlement_id", "np_street_id", "np_warehouse_id", "house_number", "apart_number")
    def _update_contact_name(self):
        if self.type == "delivery":
            self.get_full_address(self)
            self.name = self.full_delivery_address
