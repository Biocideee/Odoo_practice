import logging

from odoo import _, fields, models

from ..tools.exceptions import UkrposhtaAPIException
from ..tools.up_ttn import UkrposhtaConnector

UKRPOSHTA = "ukrposhta"

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[(UKRPOSHTA, "Укрпошта")],
        ondelete={UKRPOSHTA: "set default"},
    )
    ukrposhta_production_api_key = fields.Char(string="Production API Key")
    ukrposhta_test_api_key = fields.Char(string="Test API Key")
    ukrposhta_production_token = fields.Char(string="Production Token")
    ukrposhta_test_token = fields.Char(string="Test Token")

    def _get_ukrposhta_credentials(self):
        """
        Повертає (api_key, token, sandbox) залежно від prod_environment.
        """
        self.ensure_one()
        if self.prod_environment:
            return (
                self.sudo().ukrposhta_production_api_key,
                self.sudo().ukrposhta_production_token,
                False,
            )
        return (
            self.sudo().ukrposhta_test_api_key,
            self.sudo().ukrposhta_test_token,
            True,
        )

    def ukrposhta_send_shipping(self, pickings):
        """
        Створює ТТН в Укрпошти для кожного picking. Відправника беремо
        з prevідки picking'у (з warehouse.partner_ids, як це робить NP).

        Зверни увагу: ця функція пишет результат у picking.up_ttn (єдиний
        запис ТТН у One2many), тому передбачається, що ТТН-запис уже створений
        (через action_create_up_ttn).
        """
        api_key, token, sandbox = self._get_ukrposhta_credentials()
        if not api_key or not token:
            raise UkrposhtaAPIException(_("Не задано API ключ або token Укрпошти"))

        connector = UkrposhtaConnector(api_key, token, sandbox=sandbox)

        for picking in pickings:
            ttn = picking.up_ttn[:1]
            if not ttn:
                raise UkrposhtaAPIException(_("Для %s не створено ТТН Укрпошти.") % picking.name)
            sender = ttn.sender_id
            if not sender:
                raise UkrposhtaAPIException(_("Не задано відправника на ТТН для %s.") % picking.name)
            try:
                response = connector.create_ttn(sender, ttn)
            except UkrposhtaAPIException:
                _logger.exception(
                    "Ukrposhta create_ttn failed for picking_id=%s",
                    picking.id,
                )
                raise
            ttn.write({
                "ukrposhta_id": response.get("uuid"),
                "ttn_number": response.get("barcode") or response.get("ttnNumber") or response.get("uuid"),
                "api_key": api_key,
                "status": "wait_for_send",
            })

    def ukrposhta_get_tracking_link(self, picking):
        return False

    def ukrposhta_cancel_shipment(self, pickings):
        return False

    def ukrposhta_get_default_custom_package_code(self):
        return False

    def ukrposhta_rate_shipment(self, order):
        return {
            "success": True,
            "price": 0.0,
            "error_message": False,
            "warning_message": False,
        }
