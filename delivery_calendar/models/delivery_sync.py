import json
import logging
import requests
from datetime import datetime, timedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class DeliverySync(models.AbstractModel):
    _name = "delivery.sync"
    _description = "Delivery Calendar Synchronization Logic"

    def action_sync_delivery_dates(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        url = get_param("delivery_sync.address")
        api_key = get_param("delivery_sync.api_key")

        if not url or not api_key:
            _logger.warning("Синхронізація пропущена: не налаштовані URL або API Key.")
            return

        # 2. Шукаємо дати на рік вперед
        date_from = fields.Date.today()
        date_to = date_from + timedelta(days=365)

        # Шукаємо події з нашою міткою
        tag_id = self.env.ref("delivery_calendar.calendar_delivery_type").id
        events = self.env["calendar.event"].search(
            [
                ("categ_ids", "in", [tag_id]),
                ("start", ">=", date_from),
                ("start", "<=", date_to),
            ]
        )

        # Форматуємо дати в список "YYYY-MM-DD"
        raw_dates = events.mapped("start")
        dates = [d.strftime("%Y-%m-%d") for d in raw_dates if d]

        # 3. Відправляємо на сайт
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"dates": sorted(list(set(dates)))}

        try:
            response = requests.put(
                f"{url}/wp-json/delivery-calendar/v1/dates",
                data=json.dumps(payload),
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()  # Перевіряємо статус відповіді

            # Зберігаємо час успіху
            self.env["ir.config_parameter"].sudo().set_param(
                "delivery_sync.last_success", fields.Datetime.now()
            )
            _logger.info("Дати доставки успішно оновлені на сайті.")

        except requests.exceptions.RequestException as e:
            _logger.error("Помилка з'єднання з сайтом: %s", e)
        except Exception as e:
            _logger.error("Критична помилка синхронізації: %s", e)
