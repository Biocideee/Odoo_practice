import json
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install")
class TestDeliverySync(TransactionCase):

    def setUp(self):
        super(TestDeliverySync, self).setUp()
        # 1. Отримуємо нашу мітку "Відправка"
        self.tag = self.env.ref("delivery_calendar.calendar_delivery_type")

        # 2. Встановлюємо параметри синхронізації в "сейф"
        self.env["ir.config_parameter"].sudo().set_param(
            "delivery_sync.address", "http://localhost:8069"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "delivery_sync.api_key", "test_api_key_123"
        )

        # 3. Створюємо подію в календарі з цією міткою
        self.event = self.env["calendar.event"].create(
            {
                "name": "Доставка замовлень #1",
                "start": "2026-04-01 10:00:00",
                "stop": "2026-04-01 11:00:00",
                "categ_ids": [(4, self.tag.id)],  # Додаємо мітку
            }
        )

    def test_sync_delivery_dates_logic(self):
        """Перевіряємо, чи правильно збираються дати для відправки"""

        # Використовуємо patch, щоб не робити реальний запит в інтернет,
        # а просто перевірити, що Odoo намагається відправити
        with patch("requests.put") as mock_put:
            # Запускаємо синхронізацію
            self.env["delivery.sync"].action_sync_delivery_dates()

            # Перевіряємо, чи був викликаний запит
            self.assertTrue(mock_put.called, "Метод не спробував відправити дані!")

            # Перевіряємо, що в даних була наша дата "2026-04-01"
            args, kwargs = mock_put.call_args
            sent_data = kwargs.get("data")
            self.assertIn(
                "2026-04-01", sent_data, "Дата доставки не потрапила в запит!"
            )

    def test_sync_no_events(self):
        """Перевірка поведінки, коли в календарі немає подій"""
        # Видаляємо всі події
        self.env["calendar.event"].search([]).unlink()

        with patch("requests.put") as mock_put:
            self.env["delivery.sync"].action_sync_delivery_dates()
            args, kwargs = mock_put.call_args
            sent_data = json.loads(kwargs.get("data"))
            self.assertEqual(
                sent_data["dates"], [], "Має відправлятись порожній список!"
            )

    def test_missing_parameters(self):
        """Перевірка, чи не падає код, якщо налаштування адреси видалено"""
        self.env["ir.config_parameter"].sudo().set_param("delivery_sync.address", False)

        with patch("requests.put") as mock_put:
            self.env["delivery.sync"].action_sync_delivery_dates()
            self.assertFalse(mock_put.called, "Запит не має відправлятись без URL!")
