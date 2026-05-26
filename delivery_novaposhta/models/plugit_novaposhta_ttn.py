import datetime
import logging

from odoo import _, api, fields, models
from odoo.api import depends
from odoo.exceptions import ValidationError

from odoo.addons.delivery_novaposhta.models.delivery_carrier import payment_sides, payment_types
from odoo.addons.delivery_novaposhta.tools.exceptions import NovaposhtaAPIException

from ..tools.np_ttn import NovaposhtaConnector


class NovaposhtaTtn(models.Model):
    _name = "plugit.novaposhta_ttn"
    _description = "ТТН Нової пошти"
    _order = "create_date DESC, id DESC"

    ttn_statuses = [
        ("new", "Нова"),
        ("wait_for_send", "Підготовлена"),
        ("in_progress", "Відправлена"),
        ("delivered", "Доставлена"),
        ("error", "Помилка"),
        ("returning", "Повертається"),
        ("deleted", "Видалена"),
    ]
    ttn_statuses_dict = dict(ttn_statuses)
    service_type_list = [
        ("WarehouseDoors", "Склад-Двері"),
        ("WarehouseWarehouse", "Склад-Склад"),
        ("DoorsWarehouse", "Двері-Склад"),
        ("DoorsDoors", "Двері-Двері"),
    ]
    statuses_map = {
        "1": "wait_for_send",
        "2": "deleted",
        "3": "error",
        "4": "in_progress",
        "41": "in_progress",
        "5": "in_progress",
        "6": "in_progress",
        "7": "in_progress",
        "8": "in_progress",
        "101": "in_progress",
        "9": "delivered",
        "10": "delivered",
        "11": "delivered",
        "102": "returning",
        "103": "returning",
        "111": "error",
        "105": "error",
    }

    service_type_map = {
        ("warehouse", "warehouse"): "WarehouseWarehouse",
        ("warehouse", "poshtomat"): "WarehouseWarehouse",
        ("poshtomat", "poshtomat"): "WarehouseWarehouse",
        ("poshtomat", "warehouse"): "WarehouseWarehouse",
        ("courier", "warehouse"): "DoorsWarehouse",
        ("courier", "poshtomat"): "DoorsWarehouse",
        ("warehouse", "courier"): "WarehouseDoors",
        ("poshtomat", "courier"): "WarehouseDoors",
        ("courier", "courier"): "DoorsDoors",
    }

    name = fields.Char(compute="_compute_name")
    stock_picking_id = fields.Many2one("stock.picking", string="Доставка", copy=True)
    available_sender_ids = fields.Many2many(
        related="stock_picking_id.picking_type_id.warehouse_id.partner_ids",
    )
    partner_id = fields.Many2one("res.partner")
    main_partner_id = fields.Many2one("res.partner", string="Отримувач")
    partner_warning = fields.Char(compute="_compute_partner_warning")
    create_date = fields.Datetime(string="Дата створеня")
    delivery_date = fields.Date(string="Дата відвантаження", compute="_compute_delivery_date", readonly=False, store=True, copy=True)
    sender_id = fields.Many2one("res.partner", required=True, string="Адреса відправки", copy=True)
    sender_address = fields.Char(related="sender_id.full_delivery_address", string="Адреса відправки")
    # sender_warning = fields.Char(compute=)
    status = fields.Selection(ttn_statuses, string="Статус", copy=True, default="new")
    error = fields.Char(copy=False)
    ttn_number = fields.Char(string="Номер ТТН", copy=False)
    np_ref = fields.Char(copy=False)
    phone = fields.Char(string="Телефон", required=True, copy=True)
    contact_name = fields.Char(string="Ім'я", required=True, copy=True)
    contact_surname = fields.Char(string="Прізвище", required=True, copy=True)
    contact_middle_name = fields.Char(string="По-батькові", copy=True)
    service_type = fields.Selection(
        service_type_list, "Вид доставки (за Новою Поштою)", compute="_compute_service_type", store=True, copy=True
    )
    np_settlement_id = fields.Many2one("plugit.np_settlement", string="Населений пункт", copy=True)
    np_warehouse_id = fields.Many2one("plugit.np_warehouse", string="Склад", copy=True)

    np_street_id = fields.Many2one("plugit.np_street", string="Вулиця", copy=True)
    np_street_name = fields.Char(related="np_street_id.name")
    house_number = fields.Char(string="Будинок", copy=True)
    apart_number = fields.Char(string="Квартира/офіс", copy=True)

    full_delivery_address = fields.Char("Адреса доставки", copy=True)

    cost = fields.Float(string="Оголошена вартість", copy=True)
    delivery_cost = fields.Float(string="Вартість доставки", copy=True)
    description = fields.Char(string="Опис", copy=True)
    seat_ids = fields.One2many("plugit.novaposhta_ttn_seats", "novaposhta_ttn_id", string="Місця", copy=True)
    np_target_type = fields.Char(compute="_compute_np_target_type")
    back_payment = fields.Boolean("Післяплата")

    novaposhta_payment_type = fields.Selection(payment_types, string="Тип оплати")
    novaposhta_payment_side = fields.Selection(payment_sides, string="Сторона оплати")
    novaposhta_show_error = fields.Boolean(related="stock_picking_id.novaposhta_show_error")

    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals):
        records = super().create(vals)
        for record in records:
            record.stock_picking_id.np_ttn_id = record
        return records

    def action_send(self):
        try:
            if self.delivery_date < datetime.date.today():
                raise ValidationError(_("Дата відвантаження не може бути в минулому. Скоригуйте, будь-ласка"))
            self.create_remote()
            number = len(self)
            if number > 1:
                message = _("Створено %(number)s накладних", number=number)
            else:
                message = _("Накладну створено")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "sticky": False,
                    "message": message,
                    "next": {
                        "type": "ir.actions.client",
                        "tag": "soft_reload",
                    },
                },
            }
        except Exception as e:
            logging.exception("Create NP TTN failed")
            if isinstance(e, NovaposhtaAPIException) and e.errors:
                message_errors = e.errors
            else:
                message_errors = "Невідома помилка. Зверніться до розробників"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "sticky": False,
                    "message": _("Помилка створення накладної") + f": {message_errors}" if message_errors else "",
                },
            }

    def create_remote(self):
        for record in self:
            if not record.ttn_number:
                record.stock_picking_id.carrier_id.send_shipping(pickings=[record.stock_picking_id])

    def check_np_ttn_status(self):
        records = self.env["plugit.novaposhta_ttn"].search([("status", "not in", ("delivered", "deleted")), ("ttn_number", "!=", False)])
        api_key = self.sudo().stock_picking_id.carrier_id.get_np_api_key()
        np = NovaposhtaConnector(api_key)
        docs = []
        docs_by_ttn = {}
        for record in records:
            docs.append((record.ttn_number, record.phone))
            docs_by_ttn[record.ttn_number] = record
        if not docs:
            return

        try:
            api_statuses = np.track_ttn(docs)
        except NovaposhtaAPIException:
            logging.exception("np.track_ttn error", extra={"docs": docs})
            raise UserWarning("Помилка при з'єднанні з сервісом Нова Пошта. ")
        for doc_resp in api_statuses["data"]:
            new_status = self.statuses_map.get(doc_resp["StatusCode"])
            if new_status:
                record = docs_by_ttn[doc_resp["Number"]]
                if record.status != new_status:
                    update = {"status": new_status}
                    if new_status == "error":
                        update["error"] = doc_resp["Status"]
                    record.write(update)

    def _compute_name(self):
        for rec in self:
            rec.name = f"ТТН №{rec.ttn_number}, {rec.main_partner_id.name}" if rec.ttn_number else f"Нова ТТН. {rec.main_partner_id.name}"

    @depends("stock_picking_id.scheduled_date")
    def _compute_delivery_date(self):
        for rec in self:
            rec.delivery_date = rec.stock_picking_id.scheduled_date and rec.stock_picking_id.scheduled_date.date()

    @depends("sender_id", "stock_picking_id")
    def _compute_service_type(self):
        for rec in self:
            rec.service_type = self.service_type_map.get((rec.sender_id.np_target_type, rec.partner_id.np_target_type))

    @depends("stock_picking_id")
    def _compute_np_target_type(self):
        for rec in self:
            if rec.partner_id:
                rec.np_target_type = rec.partner_id.np_target_type
            else:
                rec.np_target_type = False

    def action_show_label_a4(self):
        return {"type": "ir.actions.act_url", "url": f"/download/ttn-label/{self.id}?page_format=A4"}

    def action_show_label_zebra(self):
        return {"type": "ir.actions.act_url", "url": f"/download/ttn-label/{self.id}?page_format=Marking_100x100"}

    def action_recreate_ttn(self):
        """
        Archive the current TTN and create a new copy with status 'new'
        """
        self.ensure_one()

        # Create a copy of the record with default copy behavior
        new_ttn = self.copy(
            default={
                "status": "new",
                "ttn_number": False,
                "np_ref": False,
                "error": False,
            }
        )

        # Archive the current record
        self.write({"active": False, "status": "deleted"})

        # Return the form view for the new record
        return {
            "type": "ir.actions.act_window",
            "res_model": "plugit.novaposhta_ttn",
            "view_mode": "form",
            "res_id": new_ttn.id,
            "target": "main",
        }

    def get_label(self, page_format):
        api_key = self.stock_picking_id.carrier_id.get_np_api_key()
        connector = NovaposhtaConnector(api_key)
        return connector.get_ttn_print([self.np_ref], page_format)

    @depends("main_partner_id", "main_partner_id.company_registry", "main_partner_id.is_company")
    def _compute_partner_warning(self):
        for record in self:
            if record.main_partner_id.is_company and not record.main_partner_id.company_registry:
                record.partner_warning = f"Не задан код ЄДРПОУ для компанії {record.main_partner_id.name}"
            else:
                record.partner_warning = False
