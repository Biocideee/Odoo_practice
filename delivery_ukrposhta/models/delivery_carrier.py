import json
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
        з ТТН-запису (sender_id), який заздалегідь створений через
        action_create_up_ttn з warehouse.partner_ids.

        Контракт Odoo (`stock_delivery/models/stock_picking.py:send_to_shipper`)
        вимагає, щоб метод повертав СПИСОК dict-ів (по одному на picking):
            [{'exact_price': <float>, 'tracking_number': <str>}, ...]
        Інакше при автоматичному виклику з button_validate() буде падати
        `TypeError: 'NoneType' object is not subscriptable`.

        Якщо для picking уже є ТТН з ukrposhta_id (тобто API виклик вже відбувся
        через action_send) — НЕ дублюємо запит, повертаємо існуючий tracking.
        """
        api_key, token, sandbox = self._get_ukrposhta_credentials()
        if not api_key or not token:
            raise UkrposhtaAPIException(_("Не задано API ключ або token Укрпошти"))

        connector = UkrposhtaConnector(api_key, token, sandbox=sandbox)
        result = []

        for picking in pickings:
            ttn = picking.up_ttn[:1]
            if not ttn:
                raise UkrposhtaAPIException(_("Для %s не створено ТТН Укрпошти.") % picking.name)

            # Ідемпотентність: якщо ТТН уже надіслана, не створюємо нову.
            if ttn.ukrposhta_id:
                _logger.info(
                    "Picking %s already has Ukrposhta TTN (uuid=%s), skipping API call",
                    picking.name, ttn.ukrposhta_id,
                )
                result.append({
                    "exact_price": 0.0,
                    "tracking_number": ttn.ttn_number or ttn.ukrposhta_id,
                })
                continue

            sender = ttn.sender_id
            if not sender:
                raise UkrposhtaAPIException(_("Не задано відправника на ТТН для %s.") % picking.name)
            try:
                response = connector.create_ttn(sender, ttn)
            except UkrposhtaAPIException as exc:
                # Логуємо помилковий запит окремо — payload є у connector
                self._log_ukrposhta_call(
                    connector, "ukrposhta_create_ttn",
                    extra_note=f"FAILED: {exc}",
                )
                _logger.exception(
                    "Ukrposhta create_ttn failed for picking_id=%s",
                    picking.id,
                )
                raise
            # Успішний — логуємо запит + відповідь
            self._log_ukrposhta_call(connector, "ukrposhta_create_ttn")
            tracking_number = response.get("barcode") or response.get("ttnNumber") or response.get("uuid")
            ttn.write({
                "ukrposhta_id": response.get("uuid"),
                "ttn_number": tracking_number,
                "api_key": api_key,
                "status": "wait_for_send",
            })
            result.append({
                "exact_price": 0.0,
                "tracking_number": tracking_number,
            })

        return result

    def ukrposhta_get_tracking_link(self, picking):
        """
        Повертає публічну сторінку відстеження УП.
        Якщо у picking ще нема ТТН (або вона без барко-кода) — повертаємо False,
        стандартна Odoo покаже діалог "Your delivery method has no redirect...".
        """
        ttn = picking.up_ttn[:1]
        if not ttn or not ttn.ttn_number:
            return False
        return f"https://track.ukrposhta.ua/tracking_UA.html?barcode={ttn.ttn_number}"

    def ukrposhta_cancel_shipment(self, pickings):
        """
        Скасування ТТН в УП через DELETE /shipments/{uuid}.
        Викликається стандартним Odoo через cancel-action на picking,
        а також з action_cancel_ttn() на TTN-формі.
        Після успішного скасування — пише статус 'deleted' і active=False
        на ТТН-записі. Picking сам це не вимагає, але ми чистимо хвости.
        """
        api_key, token, sandbox = self._get_ukrposhta_credentials()
        if not api_key or not token:
            raise UkrposhtaAPIException(_("Не задано API ключ або token Укрпошти"))

        connector = UkrposhtaConnector(api_key, token, sandbox=sandbox)

        for picking in pickings:
            ttn = picking.up_ttn.filtered(lambda t: t.active and t.ukrposhta_id)[:1]
            if not ttn:
                _logger.info(
                    "Picking %s: no active TTN with ukrposhta_id — nothing to cancel",
                    picking.name,
                )
                continue
            try:
                connector.cancel_ttn(ttn.ukrposhta_id)
            except UkrposhtaAPIException as exc:
                self._log_ukrposhta_call(
                    connector, "ukrposhta_cancel_ttn",
                    extra_note=f"FAILED: {exc}",
                )
                _logger.exception(
                    "Ukrposhta cancel_ttn failed for ttn_id=%s uuid=%s",
                    ttn.id, ttn.ukrposhta_id,
                )
                raise
            self._log_ukrposhta_call(connector, "ukrposhta_cancel_ttn")
            ttn.write({"status": "deleted", "active": False})
        return True

    def _log_ukrposhta_call(self, connector, func_name, extra_note=None):
        """
        Логує payload запиту та відповіді через стандартний log_xml(),
        який пише у таблицю ir.logging — видиму через UI Odoo
        (Налаштування → Технічні → Logging).

        Записується лише якщо debug_logging=True (внутрішня перевірка log_xml).

        :param connector: UkrposhtaConnector з .last_request_payload та .last_response_payload
        :param func_name: ім'я функції-джерела (для колонки `func` у ir.logging)
        :param extra_note: опціональна нотатка (наприклад, текст помилки)
        """
        if not self.debug_logging:
            return  # явний exit щоб не серіалізувати JSON даремно

        try:
            request_str = json.dumps(
                connector.last_request_payload,
                ensure_ascii=False, indent=2, default=str,
            )
        except Exception:
            request_str = repr(connector.last_request_payload)
        try:
            response_str = json.dumps(
                connector.last_response_payload,
                ensure_ascii=False, indent=2, default=str,
            )
        except Exception:
            response_str = repr(connector.last_response_payload)

        message = f"REQUEST:\n{request_str}\n\nRESPONSE:\n{response_str}"
        if extra_note:
            message = f"{extra_note}\n\n{message}"

        self.log_xml(message, func_name)

    def ukrposhta_get_default_custom_package_code(self):
        """
        Code посилки для митних декларацій (HS-code). УП API цього окремо
        не вимагає, тому повертаємо None — стандартна Odoo не звертає уваги.
        """
        return None

    def ukrposhta_rate_shipment(self, order):
        """
        Розрахунок вартості доставки.

        УП API має ендпоінт /tariff/* для точного розрахунку, але він вимагає
        деталей посилки (вага, габарити, адреса призначення), які на стадії
        Sales Order ще не повні. Тому повертаємо безпечну заглушку з price=0
        і warning'ом, що ціна буде уточнена при створенні ТТН.

        Це коректний contract Odoo: ключі `success`, `price`, `error_message`,
        `warning_message` — обов'язкові. Інші модулі (NP теж) роблять так само.
        """
        return {
            "success": True,
            "price": 0.0,
            "error_message": False,
            "warning_message": _(
                "Точна вартість доставки Укрпошти буде розрахована "
                "при створенні ТТН за фактичними габаритами."
            ),
        }
