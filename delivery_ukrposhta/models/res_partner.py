from odoo import api, fields, models
from odoo.addons.plugit_delivery_base.models.res_partner import PlugitDeliveryPartner


class ResPartnerUkrposhta(models.Model):
    _inherit = "res.partner"

    ukrposhta_district = fields.Char(string="Район (Укрпошта)")

    # 1. Розширюємо список токенів (полів), зміна яких має запускати перерахунок
    address_tokens = PlugitDeliveryPartner.address_tokens + [
        "state_id",
        "ukrposhta_district",
        "phone",
    ]

    # 2. Перевизначаємо метод збирання адреси
    def get_full_address(self, record):
        # Перевіряємо, чи це саме Укрпошта
        if record.carrier_id.delivery_type == "ukrposhta":
            address_parts = []

            # По черзі додаємо всі існуючі елементи адреси
            if record.zip:
                address_parts.append(record.zip)
            if record.state_id:
                address_parts.append(record.state_id.name)  # Беремо назву області, а не об'єкт
            if record.ukrposhta_district:
                address_parts.append(f"{record.ukrposhta_district} р-н")
            if record.city:
                address_parts.append(record.city)
            if record.street:
                address_parts.append(record.street)
            if record.house_number:
                address_parts.append(f"б. {record.house_number}")
            if record.apart_number:
                address_parts.append(f"кв. {record.apart_number}")
            if record.phone:
                address_parts.append(f"тел. {record.phone}")

            # З'єднуємо всі знайдені частини через кому
            address_string = ", ".join(address_parts)

            # Формуємо фінальний рядок з префіксом (наприклад: "Укрпошта: 01001, Київська...")
            prefix = record.carrier_id.delivery_type_label or "Укрпошта"
            record.full_delivery_address = f"{prefix}: {address_string}"
        else:
            # Якщо це не Укрпошта (наприклад, Нова Пошта), передаємо роботу далі
            super().get_full_address(record)

    # 3. Розширюємо декоратор залежностей
    @api.depends(*address_tokens)
    def _compute_full_delivery_address(self):
        super()._compute_full_delivery_address()

    # 4. Тригер оновлення поля 'name' у реальному часі
    @api.onchange("carrier_type", "zip", "state_id", "ukrposhta_district", "city", "street", "house_number",
                  "apart_number", "phone")
    def _update_contact_name(self):
        super()._update_contact_name()

        # Якщо зараз обрана Укрпошта і тип "Доставка" — перезаписуємо ім'я
        if self.type == "delivery" and self.carrier_type == "ukrposhta":
            self.get_full_address(self)
            self.name = self.full_delivery_address
