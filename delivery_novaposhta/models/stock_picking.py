from odoo import Command, _, fields, models
from odoo.api import depends, onchange
from odoo.exceptions import ValidationError

from odoo.addons.delivery_novaposhta.models.constants import NOVAPOSHTA


class NovaposhtaInventoryDeliveryAddress(models.Model):
    _inherit = "stock.picking"

    np_ttn_id = fields.One2many(
        "plugit.novaposhta_ttn",
        "stock_picking_id",
        string="ТТН",
    )
    carrier_type = fields.Selection(related="carrier_id.delivery_type")
    carrier_id = fields.Many2one("delivery.carrier", string="Carrier", check_company=True, store=True, compute="_compute_carrier_id")
    novaposhta_show_error = fields.Boolean(compute="_compute_novaposhta_show_error")
    warehouse_partners_ids = fields.Many2many(related="location_dest_id.warehouse_id.partner_ids")
    internal_partner_id = fields.Many2one(
        "res.partner", string="Адреса доставки", domain="[('id', 'in', warehouse_partners_ids), ('carrier_id', '=', carrier_id)]"
    )

    @depends("partner_id", "partner_id.carrier_id")
    def _compute_carrier_id(self):
        for rec in self:
            if rec.partner_id:
                rec.carrier_id = rec.partner_id.carrier_id

    @onchange("location_dest_id", "carrier_id")
    def _compute_partner_id(self):
        if self.picking_type_code == "internal" and not self.partner_id:
            if self.location_dest_id:
                partner_ids = self.location_dest_id.warehouse_id.partner_ids.filtered(lambda x: x.carrier_id == self.carrier_id)
                if partner_ids:
                    self.internal_partner_id = partner_ids[0]
                    return
        self.internal_partner_id = False

    def action_create_np_ttn(self):
        if self.picking_type_code == "internal":
            partner = self.internal_partner_id
        else:
            partner = self.partner_id
        default_sender = self.env["res.partner"].search(
            [("id", "in", [partner.id for partner in self.picking_type_id.warehouse_id.partner_ids]), ("carrier_type", "=", "novaposhta")],
            limit=1,
        )

        action = {
            "name": _("Нова пошта. Нова ТТН"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "plugit.novaposhta_ttn",
            "context": {
                "default_stock_picking_id": self.id,
                "default_partner_id": partner.id,
                "default_main_partner_id": partner.parent_id.id,
                "default_contact_name": partner.contact_person_name,
                "default_contact_surname": partner.contact_person_surname,
                "default_contact_middle_name": partner.contact_middle_name,
                "default_np_warehouse_id": partner.np_warehouse_id.id,
                "default_np_settlement_id": partner.np_settlement_id.id,
                "default_np_street_id": partner.np_street_id.id,
                "default_house_number": partner.house_number,
                "default_apart_number": partner.apart_number,
                "default_cost": self.sale_id.amount_total,
                "default_phone": partner.phone,
                "default_full_delivery_address": partner.full_delivery_address,
                "default_sender_id": default_sender and default_sender.id,
                "default_novaposhta_payment_type": self.carrier_id.novaposhta_payment_type,
                "default_novaposhta_payment_side": self.carrier_id.novaposhta_payment_side,
                "default_seat_ids": [
                    Command.create(
                        {
                            "sequence": 10,
                            "width": 10,
                            "length": 10,
                            "height": 10,
                            "weight": 0.1,
                        }
                    )
                ],
            },
        }
        return action

    def action_open_np_ttn(self):
        action = {
            "name": _("Нова пошта. ТТН"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "plugit.novaposhta_ttn",
            "res_id": self.np_ttn_id.id,
        }
        return action

    @depends("partner_id.carrier_id.novaposhta_production_api_key", "partner_id.carrier_id.active")
    def _compute_novaposhta_show_error(self):
        for rec in self:
            rec.novaposhta_show_error = (
                rec.picking_type_code in ("outgoing", "internal")
                and rec.carrier_type == NOVAPOSHTA
                and (not bool(rec.carrier_id.novaposhta_production_api_key) or not rec.carrier_id.active)
            )

    def action_confirm(self):
        if not self.np_ttn_id:
            return

        if self.np_ttn_id.delivery_date < fields.Date.today():
            raise ValidationError(_("Дата відвантаження не може бути в минулому. Скоригуйте, будь-ласка"))
