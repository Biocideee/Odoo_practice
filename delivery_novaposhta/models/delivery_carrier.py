import logging

from odoo import fields, models
from odoo.api import depends

from odoo.addons.delivery_novaposhta.tools.exceptions import NovaposhtaAPIException, TestEnvironmentWarning

from ..models.constants import API_URL, NOVAPOSHTA
from ..tools.np_load import NPLoader
from ..tools.np_ttn import NovaposhtaConnector


class PaymentTypes:
    cash = "Cash"
    non_cash = "NonCash"


payment_types = [(PaymentTypes.cash, "Готівкова"), (PaymentTypes.non_cash, "Безготівкова")]


class PaymentSides:
    sender = "Sender"
    recipient = "Recipient"


payment_sides = [(PaymentSides.sender, "Відправник"), (PaymentSides.recipient, "Одержувач")]


class SenderType:
    private = "PrivatePerson"
    organisation = "Organization"


sender_types = [(SenderType.private, "Приватна особа"), (SenderType.organisation, "Організація")]


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[(NOVAPOSHTA, "Нова пошта")], ondelete={NOVAPOSHTA: "set default"})
    novaposhta_production_api_key = fields.Char(string="API ключ ")
    novaposhta_endpoint = fields.Char(string="Адреса сервера", default=API_URL)
    novaposhta_payment_type = fields.Selection(payment_types, string="Тип оплати", default=PaymentTypes.cash)
    novaposhta_payment_side = fields.Selection(payment_sides, string="Сторона оплати", default=PaymentSides.recipient)
    novaposhta_sender_ref = fields.Char(compute="_update_counterparty_data", store=True)
    novaposhta_private_recipient_ref = fields.Char(compute="_update_counterparty_data", store=True)
    novaposhta_sender_type = fields.Char(compute="_update_counterparty_data", store=True)

    @property
    def delivery_type_label(self):
        return dict(self._fields["delivery_type"].selection).get(self.delivery_type)

    def novaposhta_rate_shipment(self, order):
        return {"price": 0.0, "success": False, "error_message": False, "warning_message": "Розрахунок поки недоступний"}

    def novaposhta_send_shipping(self, pickings):
        api_key = self.sudo().get_np_api_key()
        if not self.prod_environment:
            logging.warning("Ввімкнено тестове середовище. Реальне створення ТТН не відбувається")
            raise TestEnvironmentWarning("Не встановлений сендер")

        np = NovaposhtaConnector(api_key)
        for picking in pickings:
            if not picking.np_ttn_id.sender_id:
                raise UserWarning("Не встановлений сендер")

            try:
                ttn = np.create_ttn(picking)
            except NovaposhtaAPIException as e:
                logging.exception("np.create_ttn error", extra={"picking_id": picking.id, "picking_name": picking.name})
                raise UserWarning(f"Критична помилка при відправленні ТТН в Нова Пошта. {str(e)}") from e
            picking.np_ttn_id.ttn_number = ttn["IntDocNumber"]
            picking.np_ttn_id.np_ref = ttn["Ref"]
            picking.np_ttn_id.delivery_cost = float(ttn["CostOnSite"])

    def novaposhta_get_tracking_link(self, picking):
        ...

    def novaposhta_cancel_shipment(self, pickings):
        ...

    def novaposhta_get_default_custom_package_code(self):
        ...

    def get_np_api_key(self):
        return self.novaposhta_production_api_key

    def notify_user(self, user, message_body):
        odoobot_id = self.env.ref("base.partner_root").id
        channel = self.env["discuss.channel"]._get_or_create_chat([odoobot_id, user.partner_id.id])
        channel.sudo().message_post(
            author_id=odoobot_id,
            body=message_body,
            message_type="comment",
        )
        self.env.cr.commit()

    def _start_loader(self, user):
        self.notify_user(user, "Завантаження НП почалось")
        try:
            NPLoader().run(self.env, with_raise=True)
        except Exception:
            self.env.cr.rollback()
            message_body = "Помилка завантаження довідників Нова Пошта"
        else:
            message_body = "Завантаження довідників Нова Пошта завершено"

        self.notify_user(user, message_body)

    def load_novaposhta_data(self):
        manually = self.env.context.get("manually", False)
        user = self.env.user
        if manually:
            logging.info("Запуск вручну")
            self = self.with_delay()
        else:
            logging.info("Запуск з крона")
        self._start_loader(user)

    def load_counterparty_data(self):
        np_api = NovaposhtaConnector(self.get_np_api_key())
        sender_data = np_api.get_counterparty()[0]
        self.novaposhta_sender_ref = sender_data["Ref"]
        self.novaposhta_sender_type = sender_data["CounterpartyType"]
        # novaposhta_private_recipient_ref зберігає посилання на recipient private person counterparty,
        # який групує всіх приватних отримувачив
        recipients_data = np_api.get_counterparty(counterparty_property="Recipient")
        for recipient in recipients_data:
            if recipient["CounterpartyType"] == SenderType.private:
                self.novaposhta_private_recipient_ref = recipient["Ref"]
                break

    @depends("novaposhta_production_api_key")
    def _update_counterparty_data(self):
        for rec in self:
            if rec.novaposhta_production_api_key:
                rec.load_counterparty_data()
            else:
                self.novaposhta_sender_ref = False
                self.novaposhta_sender_type = False
                self.novaposhta_private_recipient_ref = False
