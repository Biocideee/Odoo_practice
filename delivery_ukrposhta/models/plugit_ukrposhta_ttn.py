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

types = [
    ("Express", "Express"),
    ("Standard", "Standard"),
]


class UkrposhtaTtn(models.Model):
    _name = "plugit.ukrposhta_ttn"
    _description = "ТТН Укрпошти"
    _order = "create_date DESC, id DESC"

    name = fields.Char(compute="_compute_name")
    stock_picking_id = fields.Many2one("stock.picking", string="Доставка", copy=False)
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
    type = fields.Selection(types, string="Швидкість", default="Standard", copy=True)

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
        дозволяє користувачу зберегти чернетку (NP робить так само).
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
        Відправити ТТН на сервер Укрпошти. Помилку API не пробрасуємо
        стактрейсом у user — показуємо красиве сповіщення.
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
        # Групуємо за carrier, щоб не створювати конектор на кожен запис.
        by_carrier = {}
        for record in records:
            carrier = record.stock_picking_id.carrier_id
            if not carrier:
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
                continue
            connector = UkrposhtaConnector(api_key, token, sandbox=sandbox)
            for record in recs:
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
                    continue
                new_status = API_STATUS_MAP.get(raw_status)
                if new_status and record.status != new_status:
                    record.write({"status": new_status})
