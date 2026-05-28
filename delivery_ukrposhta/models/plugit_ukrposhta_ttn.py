import logging

from odoo import _, api, fields, models

from ..tools.exceptions import DeliveryAPIException, UkrposhtaAPIException
from ..tools.up_ttn import UkrposhtaConnector

_logger = logging.getLogger(__name__)

UKRPOSHTA = "ukrposhta"

ttn_statuses = [
    ("new", "Нова"),
    ("wait_for_send", "Підготовлена"),
    ("in_progress", "Відправлена"),
    ("delivered", "Доставлена"),
    ("error", "Помилка"),
    ("returning", "Повертається"),
    ("deleted", "Видалена"),
]

# Інверсована мапа: ключі — статуси API Укрпошти, значення — наші коди.
# В оригінальному коді мапа була ('наш статус' → 'статус API'), і потім
# код намагався робити .get(api_status) — завжди None.
API_STATUS_MAP = {
    "CREATED": "wait_for_send",
    "REGISTERED": "wait_for_send",
    "SENT": "in_progress",
    "PROCESSING": "in_progress",
    "DELIVERING": "in_progress",
    "ARRIVED": "in_progress",
    "DELIVERED": "delivered",
    "RECEIVED": "delivered",
    "RETURNED": "returning",
    "RETURNING": "returning",
    "CANCELED": "deleted",
    "CANCELLED": "deleted",
    "FAILED": "error",
}

delivery_type_list = [
    ("W2D", "Склад-Двері"),
    ("W2W", "Склад-Склад"),
    ("D2W", "Двері-Склад"),
    ("D2D", "Двері-Двері"),
]

# Значення мають збігатися з enum'ом API УП (ShipmentType): UPPER_SNAKE_CASE.
# Доступні також: SMARTBOX, INTERNATIONAL, DOCUMENT, CARGO, STANDARD_CARGO,
# DOCUMENT_BACK, VALUABLE_LETTER, INTERNATIONAL_EXPORT_PLUS, INTERNATIONAL_CONSIGNMENT.
# Залишаємо два найпоширеніші — Standard і Express.
types = [
    ("STANDARD", "Стандарт"),
    ("EXPRESS", "Експрес"),
]


class UkrposhtaTtn(models.Model):
    _name = "plugit.ukrposhta_ttn"
    _description = "ТТН Укрпошти"
    _order = "create_date DESC, id DESC"

    name = fields.Char(compute="_compute_name")
    stock_picking_id = fields.Many2one("stock.picking", string="Доставка", copy=True)
    available_sender_ids = fields.Many2many(
        related="stock_picking_id.picking_type_id.warehouse_id.partner_ids",
    )
    sender_id = fields.Many2one(
        "res.partner",
        string="Адреса відправки",
        copy=True,
        domain="[('id', 'in', available_sender_ids), ('carrier_type', '=', 'ukrposhta')]",
    )
    sender_address = fields.Char(related="sender_id.full_delivery_address", string="Адреса відправника")
    full_delivery_address = fields.Char(string="Адреса доставки", copy=True)
    create_date = fields.Datetime(string="Створено")
    delivery_date = fields.Datetime(string="Дата відвантаження")

    status = fields.Selection(ttn_statuses, string="Статус", default="new", copy=False)
    ukrposhta_id = fields.Char(string="UUID Укрпошти", readonly=True, copy=False)
    ttn_number = fields.Char(string="Номер ТТН", readonly=True, copy=False)
    api_key = fields.Char(string="API Key", readonly=True, copy=False)
    error = fields.Char(string="Помилка", copy=False, readonly=True)

    parcel_ids = fields.One2many(
        "plugit.ukrposhta_ttn_parcels", "ukrposhta_ttn_id",
        string="Місця", copy=True,
    )

    delivery_type = fields.Selection(delivery_type_list, string="Тип доставки", default="W2W", copy=True)
    type = fields.Selection(types, string="Швидкість", default="STANDARD", copy=True)

    # Контакт-поля: необов'язкові на рівні моделі, обов'язковість керується UI/onSubmit
    # (різні delivery_type вимагають різних полів).
    phone = fields.Char(string="Телефон", copy=True)
    name_contact = fields.Char(string="Ім'я", copy=True)
    surname = fields.Char(string="Прізвище", copy=True)
    middle_name = fields.Char(string="По-батькові", copy=True)
    zip_code = fields.Char(string="Індекс", copy=True)
    region = fields.Char(string="Область", copy=True)
    district = fields.Char(string="Район", copy=True)
    city = fields.Char(string="Місто", copy=True)
    street = fields.Char(string="Вулиця", copy=True)
    house_number = fields.Char(string="Будинок", copy=True)
    apart_number = fields.Char(string="Квартира", copy=True)

    currency_id = fields.Many2one(
        "res.currency", string="Валюта",
        default=lambda self: self.env.company.currency_id.id,
    )
    post_pay = fields.Monetary(string="Післяплата", currency_field="currency_id")
    paid_by_recipient = fields.Boolean(string="Оплачує отримувач")
    fragile = fields.Boolean(string="Крихке")
    sms = fields.Boolean(string="SMS-повідомлення")
    transfer_post_pay_to_bank_account = fields.Boolean(string="Післяплата на рахунок")
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Створюємо лише запис ТТН — без автоматичної відправки на сервер
        Укрпошти. Відправка відбувається окремо через action_send(), що
        дозволяє користувачу зберегти чернетку (в НП так само).
        """
        records = super().create(vals_list)
        return records

    def _compute_name(self):
        for rec in self:
            if rec.ttn_number:
                rec.name = f"ТТН №{rec.ttn_number}"
            elif rec.ukrposhta_id:
                rec.name = f"ТТН {rec.ukrposhta_id}"
            else:
                rec.name = _("Нова ТТН Укрпошти")

    # --- Дії над ТТН ---------------------------------------------------

    def action_send(self):
        """
        Відправити ТТН на сервер Укрпошти. Показуємо сповіщення.
        """
        self.ensure_one()
        if self.ukrposhta_id:
            return self._notify(_("ТТН вже надіслано"), success=False)
        if not self.stock_picking_id.carrier_id or self.stock_picking_id.carrier_id.delivery_type != UKRPOSHTA:
            return self._notify(_("Носій доставки не є Укрпоштою"), success=False)
        try:
            self.stock_picking_id.carrier_id.send_shipping(pickings=[self.stock_picking_id])
        except (UkrposhtaAPIException, DeliveryAPIException) as exc:
            _logger.exception("Ukrposhta send_shipping failed for ttn_id=%s", self.id)
            self.write({"error": str(exc), "status": "error"})
            return self._notify(_("Помилка створення ТТН: %s") % str(exc), success=False)
        except Exception as exc:
            _logger.exception("Unexpected error while sending Ukrposhta TTN id=%s", self.id)
            self.write({"error": str(exc), "status": "error"})
            return self._notify(_("Непередбачувана помилка: %s") % str(exc), success=False)
        return self._notify(_("ТТН створено"), success=True)

    def action_recreate_ttn(self):
        """
        Архівувати поточний запис і створити копію зі статусом `new`.
        Аналог NP `action_recreate_ttn`.
        """
        self.ensure_one()
        new_ttn = self.copy(default={
            "status": "new",
            "ukrposhta_id": False,
            "ttn_number": False,
            "api_key": False,
            "error": False,
        })
        self.write({"active": False, "status": "deleted"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "plugit.ukrposhta_ttn",
            "view_mode": "form",
            "res_id": new_ttn.id,
            "target": "main",
        }

    def action_show_label_a4(self):
        """Завантажити PDF-етикетку формату A4."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/download/ukrposhta-label/{self.id}?page_format=A4",
            "target": "self",
        }

    def action_show_label_zebra(self):
        """Завантажити PDF-етикетку формату Zebra (термопринтер)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/download/ukrposhta-label/{self.id}?page_format=Z",
            "target": "self",
        }

    def action_cancel_ttn(self):
        """
        Скасувати ТТН в УП. Працює лише поки ТТН не у фінальному стані
        (delivered/deleted). Викликає DELETE /shipments/{uuid} через carrier.
        """
        self.ensure_one()
        if not self.ukrposhta_id:
            return self._notify(_("ТТН ще не надіслана в УП"), success=False)
        if self.status in ("delivered", "deleted"):
            return self._notify(_("Не можна скасувати ТТН у статусі %s") % self.status, success=False)
        try:
            self.stock_picking_id.carrier_id.cancel_shipment(pickings=[self.stock_picking_id])
        except (UkrposhtaAPIException, DeliveryAPIException) as exc:
            _logger.exception("Ukrposhta cancel_ttn failed for ttn_id=%s", self.id)
            self.write({"error": str(exc)})
            return self._notify(_("Помилка скасування ТТН: %s") % str(exc), success=False)
        except Exception as exc:
            _logger.exception("Unexpected error cancelling Ukrposhta TTN id=%s", self.id)
            self.write({"error": str(exc)})
            return self._notify(_("Непередбачувана помилка: %s") % str(exc), success=False)
        return self._notify(_("ТТН скасовано"), success=True)

    @staticmethod
    def _notify(message, success=True):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if success else "warning",
                "sticky": False,
                "message": message,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"} if success else None,
            },
        }

    # --- Перевірка статусів --------------------------------------------

    def check_ttn_status(self):
        """
        Cron-метод. Проходить по всіх ТТН, які:
          * мають заповнений ukrposhta_id (інакше нема що питати),
          * статус не у фінальних ('delivered', 'deleted').
        Зміни статусу записує атомарно.

        Старий код брав api_key/token з `self.sudo().stock_picking_id.carrier_id`,
        але `self` тут — env-обгортка над модельним класом (cron виконує
        `model.search().check_ttn_status()`). Це працювало випадково.
        Тепер беремо облікові дані ПО КОЖНОМУ запису з його carrier — кожен
        запис може належати своєму carrier'у з власними ключами.
        """
        records = self.env["plugit.ukrposhta_ttn"].search([
            ("ukrposhta_id", "!=", False),
            ("status", "not in", ("delivered", "deleted", "error")),
        ])
        _logger.info(
            "Ukrposhta status check: found %s TTN(s) to query",
            len(records),
        )
        # Групуємо за carrier, щоб не створювати конектор на кожен запис.
        by_carrier = {}
        for record in records:
            carrier = record.stock_picking_id.carrier_id
            if not carrier:
                _logger.warning(
                    "TTN id=%s has no carrier on its picking — skipping", record.id,
                )
                continue
            by_carrier.setdefault(carrier.id, (carrier, self.env["plugit.ukrposhta_ttn"]))
            by_carrier[carrier.id] = (carrier, by_carrier[carrier.id][1] | record)

        for carrier, recs in by_carrier.values():
            try:
                api_key, token, sandbox = carrier._get_ukrposhta_credentials()
            except Exception:
                _logger.exception("Failed to get Ukrposhta credentials for carrier %s", carrier.id)
                continue
            if not api_key or not token:
                _logger.warning(
                    "Carrier %s has no Ukrposhta credentials — skipping %s TTN(s)",
                    carrier.id, len(recs),
                )
                continue
            connector = UkrposhtaConnector(api_key, token, sandbox=sandbox)
            for record in recs:
                _logger.info(
                    "Querying Ukrposhta status for TTN id=%s uuid=%s",
                    record.id, record.ukrposhta_id,
                )
                try:
                    api_status = connector.check_ttn_status(record.ukrposhta_id)
                except (UkrposhtaAPIException, DeliveryAPIException):
                    _logger.exception(
                        "Ukrposhta check_ttn_status failed for ttn_id=%s",
                        record.id,
                    )
                    continue
                lifecycle = (api_status or {}).get("lifecycle") or {}
                raw_status = lifecycle.get("status")
                if not raw_status:
                    _logger.info(
                        "TTN id=%s: API responded but no lifecycle.status — skipping",
                        record.id,
                    )
                    continue
                new_status = API_STATUS_MAP.get(raw_status)
                _logger.info(
                    "TTN id=%s: API status='%s' mapped to '%s' (current: '%s')",
                    record.id, raw_status, new_status, record.status,
                )
                if new_status and record.status != new_status:
                    record.write({"status": new_status})
                    _logger.info("TTN id=%s status updated to '%s'", record.id, new_status)
