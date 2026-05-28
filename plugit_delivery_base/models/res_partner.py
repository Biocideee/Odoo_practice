import re

from operator import attrgetter

from odoo import api, fields, models
from odoo.api import depends, onchange
from odoo.exceptions import ValidationError


class PlugitDeliveryPartner(models.Model):
    _inherit = "res.partner"
    _rec_names_search = ['complete_name', 'email', 'ref', 'vat', 'company_registry', 'phone_normalized']

    carrier_id = fields.Many2one("delivery.carrier", string="Спосіб доставки")
    carrier_type = fields.Selection(string="Провайдер", related="carrier_id.delivery_type")
    full_delivery_address = fields.Char("Адреса доставки", compute="_compute_full_delivery_address", store=True)
    default_delivery_address_id = fields.Many2one("res.partner", compute="_compute_default_delivery_address")

    phone_normalized = fields.Char(compute='_compute_phone_normalized', store=True, index=True)

    contact_person_name = fields.Char(string="Ім'я")
    contact_middle_name = fields.Char(string="По-батькові")
    contact_person_surname = fields.Char(string="Прізвище")

    house_number = fields.Char("Будинок")
    apart_number = fields.Char("Квартира")
    notes = fields.Char("Додатково")

    address_tokens = [
        "street",
        "house_number",
        "apart_number",
        "city",
        "state_id.name",
        "zip",
    ]

    @api.depends('phone')
    def _compute_phone_normalized(self):
        for rec in self:
            if rec.phone:
                # Витягуємо тільки цифри
                digits_only = re.sub(r"\D", "", rec.phone)
                # Додаємо код країни, якщо ввели 10 цифр
                if len(digits_only) == 10 and digits_only.startswith("0"):
                    digits_only = "38" + digits_only

                rec.phone_normalized = digits_only
            else:
                rec.phone_normalized = False

    @api.onchange('phone')
    def _onchange_format_phone_ui(self):
        if self.phone:
            digits_only = re.sub(r"\D", "", self.phone)
            if len(digits_only) == 10 and digits_only.startswith("0"):
                digits_only = "38" + digits_only

            if len(digits_only) == 12 and digits_only.startswith('380'):
                self.phone = f"+{digits_only[:3]}{digits_only[3:5]}{digits_only[5:8]}{digits_only[8:10]}{digits_only[10:]}"

    @api.constrains('phone', 'type', 'carrier_id')
    def _check_phone_strict_validation(self):
        for record in self:
            if record.type == 'delivery' and record.carrier_id:
                if not record.phone:
                    raise ValidationError("Помилка! Для адреси доставки обов'язково потрібно вказати телефон.")

                normalized = record.phone_normalized or ''
                if not normalized:
                    digits_only = re.sub(r'\D', '', record.phone)
                    normalized = '38' + digits_only if len(digits_only) == 10 and digits_only.startswith(
                        '0') else digits_only

                if len(normalized) != 12 or not normalized.startswith('380'):
                    raise ValidationError(
                        f"Недійсний номер телефону: {record.phone}. "
                        f"Номер отримувача повинен мати вигляд (наприклад, +380 69 360 13 37) "
                        f"і мати рівно 12 цифр."
                    )

    @onchange("parent_id")
    def _set_phone(self):
        if self.parent_id and not self.phone:
            self.phone = self.parent_id.phone

    @onchange("type")
    def on_type_change(self):
        self.carrier_id = False
        if self.type == "delivery":
            carrier_id = self.env["delivery.carrier"].search([("delivery_type", "=", "fixed")])
            if carrier_id:
                self.carrier_id = carrier_id[0]

    @depends("carrier_id")
    def _compute_carrier_type(self):
        for rec in self:
            rec.carrier_type = rec.carrier_id.delivery_type

    def get_full_address(self, record):
        address = []

        for token in self.address_tokens:
            value = attrgetter(token)(record)
            if value:
                if isinstance(value, str):
                    address.append(value)
                elif hasattr(value, "name"):
                    address.append(value.name)

        record.full_delivery_address = ", ".join(address)

    @api.depends(*address_tokens)
    def _compute_full_delivery_address(self):
        for record in self:
            if record.type == "delivery":
                self.get_full_address(record)

    @api.depends("child_ids.carrier_type", "property_delivery_carrier_id")
    def _compute_default_delivery_address(self):
        for rec in self:
            rec.default_delivery_address_id = False
            delivery_addresses = rec.child_ids.filtered(
                lambda x: x.type == "delivery" and x.carrier_id == rec.property_delivery_carrier_id)
            if delivery_addresses:
                rec.default_delivery_address_id = delivery_addresses[-1]
