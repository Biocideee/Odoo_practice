from odoo import Command, _, fields, models


UKRPOSHTA = "ukrposhta"


class StockPicking(models.Model):
    _inherit = "stock.picking"

    up_ttn = fields.One2many("plugit.ukrposhta_ttn", "stock_picking_id", string="ТТН Укрпошти")
    # carrier_type визначається у delivery_novaposhta теж; якщо два модулі ставлять його разом,
    # один із них візьме верх — поведінка ідентична (related на carrier_id.delivery_type),
    # тому конфлікту немає.
    carrier_type = fields.Selection(related="carrier_id.delivery_type", store=False)
    warehouse_partners_ids = fields.Many2many(
        related="location_dest_id.warehouse_id.partner_ids",
        string="Партнери складу",
    )
    ukrposhta_show_error = fields.Boolean(compute="_compute_ukrposhta_show_error")

    def _compute_ukrposhta_show_error(self):
        for rec in self:
            rec.ukrposhta_show_error = (
                rec.picking_type_code in ("outgoing", "internal")
                and rec.carrier_type == UKRPOSHTA
                and (
                    not bool(rec.carrier_id.ukrposhta_production_api_key)
                    and not bool(rec.carrier_id.ukrposhta_test_api_key)
                    or not rec.carrier_id.active
                )
            )

    def _get_default_ukrposhta_sender(self):
        """
        Сендер за замовчуванням — партнер зі списку warehouse.partner_ids,
        у якого carrier_type == 'ukrposhta'. Логіка аналогічна
        delivery_novaposhta/models/stock_picking.py:action_create_np_ttn.
        """
        self.ensure_one()
        warehouse = self.picking_type_id.warehouse_id
        partners = warehouse.partner_ids.filtered(lambda p: p.carrier_type == UKRPOSHTA)
        return partners[:1]

    def action_create_up_ttn(self):
        """
        Відкриває форму створення ТТН Укрпошти з префілом полів з партнера.
        Прибрав 'view_type': 'form' — застарілий ключ, ігнорується з v15+.
        """
        self.ensure_one()
        partner = self.partner_id
        default_sender = self._get_default_ukrposhta_sender()
        # Заглушка-парсел: користувач відредагує. NP робить так само через Command.create.
        default_parcels = [
            Command.create({
                "sequence": 10,
                "weight": 0.5,
                "length": 10,
                "width": 10,
                "height": 10,
                "description": "",
            })
        ]
        return {
            "name": _("Укрпошта. Нова ТТН"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "plugit.ukrposhta_ttn",
            "target": "current",
            "context": {
                "default_stock_picking_id": self.id,
                "default_sender_id": default_sender and default_sender.id,
                "default_phone": partner.phone,
                "default_name_contact": partner.contact_person_name,
                "default_middle_name": partner.contact_middle_name,
                "default_surname": partner.contact_person_surname,
                "default_zip_code": partner.zip,
                "default_region": (partner.state_id and partner.state_id.name) or "",
                "default_district": partner.ukrposhta_district or "",
                "default_city": partner.city,
                "default_street": partner.street,
                "default_house_number": partner.house_number,
                "default_apart_number": partner.apart_number,
                "default_parcel_ids": default_parcels,
            },
        }

    def action_open_up_ttn(self):
        """
        Відкриває існуючий запис ТТН Укрпошти у формовому виді.
        """
        self.ensure_one()
        return {
            "name": _("Укрпошта. ТТН"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "plugit.ukrposhta_ttn",
            "res_id": self.up_ttn[:1].id,
        }
