# -*- coding: utf-8 -*-

"""
Цей файл розширює стандартну модель Point of Sale сесії (pos.session)
для інтеграції з сервісом фіскалізації Checkbox.

Основна логіка включає:
- Автоматичне відкриття зміни в Checkbox при старті сесії в Odoo.
- Автоматичне закриття зміни та створення Z-звіту при закритті сесії.
- Збереження Z-звіту як прикріпленого файлу до сесії.
- Передачу токена доступу Checkbox у фронтенд-частину POS.
"""

import base64
import logging

import requests

from odoo import fields, models, api
from odoo.exceptions import UserError

# Створюємо екземпляр логера для цього файлу.
# Це дозволяє виводити інформацію, попередження та помилки в консоль Odoo.
_logger = logging.getLogger(__name__)

# Список текстових маркерів, які вказують на те, що зміна в Checkbox вже відкрита.
# Це потрібно для коректної обробки помилок від API Checkbox.
ALREADY_OPEN_MARKERS = [
    "base.bad_request",
    "Касир вже працює",
    "касир вже працює",
    "already_opened",
    "вже працює",
    "already open",
    "shift is already",
    "SHIFT_ALREADY",
]


class PosSession(models.Model):
    """
    Клас, що розширює стандартну модель pos.session.
    """
    _inherit = 'pos.session'

    # Нове поле для зберігання тимчасового токена доступу від Checkbox.
    # Токен потрібен для всіх запитів до API Checkbox протягом однієї сесії.
    # `copy=False` означає, що при дублюванні сесії це поле не буде копіюватися.
    checkbox_access_token = fields.Char(
        string="Checkbox JWT Токен",
        copy=False
    )

    def action_pos_session_open(self):
        """
        Перевизначення стандартного методу відкриття сесії.
        Цей метод викликається, коли користувач натискає кнопку "Open Session".
        """
        # Викликаємо оригінальний (батьківський) метод, щоб виконати стандартні дії.
        res = super().action_pos_session_open()
        for session in self:
            # Перевіряємо, чи сесія успішно відкрита, чи в налаштуваннях POS вказано
            # ключ ліцензії Checkbox, і чи токен ще не отримано.
            if (session.state == 'opened' and
                    session.config_id.checkbox_license_key and not
                    session.checkbox_access_token):
                try:
                    # Викликаємо наш кастомний метод для ініціалізації та відкриття зміни.
                    session._checkbox_init_and_open_shift()
                except UserError as e:
                    # Якщо виникає помилка, яку ми передбачили (UserError),
                    # логуємо її і показуємо користувачу.
                    _logger.error(
                        f"Checkbox: помилка відкриття зміни для сесії "
                        f"{session.name}: {e}"
                    )
                    raise
        return res

    def set_opening_control(self, *args, **kwargs):
        """
        Перевизначення методу, що відповідає за екран контролю готівки при відкритті.
        Цей метод також є точкою входу у відкриття сесії.
        """
        res = super().set_opening_control(*args, **kwargs)
        for session in self:
            # Логіка аналогічна до `action_pos_session_open`.
            # Це забезпечує, що зміна відкриється незалежно від того,
            # чи є у користувача екран контролю готівки.
            if (session.config_id.checkbox_license_key and not
            session.checkbox_access_token):
                try:
                    session._checkbox_init_and_open_shift()
                except UserError as e:
                    _logger.error(
                        f"Checkbox: помилка відкриття зміни для сесії "
                        f"{session.name}: {e}"
                    )
                    raise
        return res

    def _checkbox_get_fresh_token(self):
        """
        Допоміжний метод для отримання нового (свіжого) токена доступу.
        Це потрібно перед закриттям зміни, щоб гарантувати, що токен не застарів.
        """
        # `ensure_one` перевіряє, що метод викликається для одного запису (сесії).
        self.ensure_one()
        user = self.user_id
        # Якщо у користувача не вказано логін або пароль, нічого не робимо.
        if not user.checkbox_login or not user.checkbox_password:
            return None
        try:
            # Робимо запит на авторизацію в Checkbox.
            response = requests.post(
                "https://api.checkbox.ua/api/v1/cashier/signin",
                json={
                    "login": user.checkbox_login,
                    "password": user.checkbox_password
                },
                timeout=10,
            )
            # Якщо запит неуспішний (статус не 2xx), генеруємо помилку.
            response.raise_for_status()
            token = response.json().get('access_token')
            if token:
                # Зберігаємо токен в поточній сесії з правами суперкористувача,
                # щоб уникнути проблем з правами доступу.
                self.sudo().write({'checkbox_access_token': token})
            return token
        except Exception as e:
            # Логуємо будь-яку помилку, що могла виникнути.
            _logger.error(
                f"Checkbox: не вдалося оновити токен для {self.name}: {e}"
            )
            return None

    def _checkbox_init_and_open_shift(self):
        """
        Основний метод для авторизації касира та відкриття зміни в Checkbox.
        """
        self.ensure_one()
        user = self.user_id
        # Перевірка наявності логіну та пароля.
        if not user.checkbox_login or not user.checkbox_password:
            raise UserError(
                "У вашому профілі користувача не налаштовано логін/пароль "
                "Checkbox!"
            )

        try:
            # Крок 1: Авторизація касира.
            response = requests.post(
                "https://api.checkbox.ua/api/v1/cashier/signin",
                json={
                    "login": user.checkbox_login,
                    "password": user.checkbox_password
                },
                timeout=10,
            )
            response.raise_for_status()
            token = response.json().get('access_token')
            if not token:
                raise UserError(
                    "Checkbox не повернув токен авторизації. "
                    "Перевірте логін/пароль."
                )
            self.sudo().write({'checkbox_access_token': token})

            # Крок 2: Відкриття зміни.
            headers = {
                "Authorization": f"Bearer {token}",
                "X-License-Key": self.config_id.checkbox_license_key,
            }
            shift_resp = requests.post(
                "https://api.checkbox.ua/api/v1/shifts",
                headers=headers,
                timeout=10,
            )
            body = shift_resp.text

            # Обробка різних статусів відповіді від Checkbox.
            if shift_resp.status_code in [200, 201, 202]:
                _logger.info(
                    f"Checkbox: зміну успішно відкрито для сесії {self.name}."
                )
            elif shift_resp.status_code in [400, 422]:
                # Якщо помилка "Bad Request", перевіряємо, чи не тому,
                # що зміна вже відкрита.
                search_text = body
                try:
                    json_body = shift_resp.json()
                    search_text += json_body.get('code', '') + json_body.get(
                        'message', '')
                except Exception:
                    pass

                if any(marker in search_text for marker in
                       ALREADY_OPEN_MARKERS):
                    _logger.info(
                        f"Checkbox: зміна вже відкрита "
                        f"({shift_resp.status_code}) для сесії {self.name}, "
                        f"продовжуємо."
                    )
                else:
                    # Якщо інша помилка 4xx, просто попереджаємо.
                    _logger.warning(
                        f"Checkbox: {shift_resp.status_code} при відкритті "
                        f"зміни для {self.name}: {body}. Продовжуємо."
                    )
            else:
                # Якщо статус відповіді непередбачуваний, генеруємо помилку.
                raise UserError(
                    f"Не вдалося відкрити зміну ПРРО Checkbox "
                    f"(HTTP {shift_resp.status_code}): {body}"
                )

        except requests.exceptions.HTTPError as e:
            # Обробка помилок HTTP (наприклад, 401 Unauthorized).
            error_body = e.response.json() if e.response.headers.get(
                'Content-Type', '').startswith(
                'application/json') else e.response.text
            message = error_body.get('message', str(
                error_body)) if isinstance(error_body, dict) else str(
                error_body)
            raise UserError(f"Помилка авторизації Checkbox: {message}")
        except requests.exceptions.RequestException as e:
            # Обробка помилок з'єднання (немає інтернету, DNS тощо).
            raise UserError(f"Помилка з'єднання з Checkbox: {e}")

    def action_pos_session_close(self, *args, **kwargs):
        """
        Перевизначення методу закриття сесії.
        """
        res = super().action_pos_session_close(*args, **kwargs)
        for session in self:
            # Якщо для конфігурації POS активована фіскалізація.
            if session.config_id.checkbox_license_key:
                session._checkbox_close_shift_and_signout()
        return res

    def _checkbox_close_shift_and_signout(self):
        """
        Основний метод для закриття зміни та виходу касира.
        """
        self.ensure_one()

        # Отримуємо свіжий токен перед важливими операціями.
        token = self._checkbox_get_fresh_token()
        if not token:
            self.sudo().write({'checkbox_access_token': False})
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "X-License-Key": self.config_id.checkbox_license_key,
        }

        try:
            # Крок 1: Закриття зміни.
            report_resp = requests.post(
                "https://api.checkbox.ua/api/v1/shifts/close",
                headers=headers,
                timeout=20,
            )

            if report_resp.status_code in [200, 201, 202]:
                _logger.info(f"Checkbox: зміну успішно закрито для сесії {self.name}.")

                # Крок 2: Викликаємо окремий метод для отримання Z-звіту
                self._checkbox_fetch_z_report(headers, report_resp.json())

            # ОБРОБКА ВИНЯТКУ: Якщо спрацювало автозакриття Checkbox (Fallback)
            elif report_resp.status_code in [400, 422] and "already_closed" in report_resp.text.lower():
                _logger.warning(
                    f"Checkbox: зміна вже закрита для сесії {self.name} (можливо, через автозакриття). "
                    f"Пропускаємо фіскальне закриття і продовжуємо закривати сесію в Odoo."
                )

            else:
                _logger.error(
                    f"Checkbox: помилка при закритті сесії {self.name}: {report_resp.text}"
                )

        except requests.exceptions.RequestException as e:
            _logger.error(f"Checkbox: критична помилка зв'язку при закритті зміни: {e}")

        # Крок 3: Вихід касира (Sign Out).
        # Цей блок завжди виконується, навіть якщо зміна вже була закрита
        signout_url = "https://api.checkbox.ua/api/v1/cashier/signout"
        try:
            signout_resp = requests.post(
                signout_url,
                headers=headers,
                json={},
                timeout=10
            )

            if signout_resp.ok:
                _logger.info(f"Checkbox: касир успішно вийшов з сесії {self.name}.")
            else:
                _logger.warning(
                    f"Checkbox: помилка при виході (HTTP {signout_resp.status_code}): {signout_resp.text}"
                )
        except Exception as e:
            _logger.error(f"Checkbox: помилка з'єднання при виході: {e}")
        finally:
            # Гарантуємо очищення токена
            self.sudo().write({'checkbox_access_token': False})

    def _checkbox_fetch_z_report(self, headers, shift_data):
        """
        Метод для завантаження текстового Z-звіту та прикріплення його до сесії.
        """
        import time
        try:
            z_report = shift_data.get('z_report', {})
            report_id = z_report.get('id')

            if not report_id:
                _logger.warning(f"Checkbox: Z-звіт не повернув ID для сесії {self.name}.")
                return

            # Пауза 1 секунда, щоб Checkbox встиг згенерувати звіт
            time.sleep(1)

            text_url = f"https://api.checkbox.ua/api/v1/reports/{report_id}/text"
            text_resp = requests.get(text_url, headers=headers, timeout=10)

            if text_resp.status_code == 200:
                report_content = text_resp.text
                encoded_content = base64.b64encode(report_content.encode('utf-8'))
                safe_name = self.name.replace('/', '_')

                self.env['ir.attachment'].create({
                    'name': f'Z_Report_{safe_name}.txt',
                    'type': 'binary',
                    'datas': encoded_content,
                    'res_model': 'pos.session',
                    'res_id': self.id,
                    'mimetype': 'text/plain'
                })
                _logger.info(f"Z-звіт успішно збережено як прикріплення до сесії {self.name}")
            else:
                _logger.warning(f"Не вдалося завантажити текст Z-звіту. HTTP {text_resp.status_code}: {text_resp.text}")

        except Exception as e:
            _logger.error(f"Помилка при збереженні Z-звіту як аттачменту: {e}")

    def _load_pos_data_fields(self, config_id):
        """
        Перевизначення методу для додавання наших полів у дані,
        що завантажуються в POS фронтенд.
        """
        result = super()._load_pos_data_fields(config_id)
        # Додаємо наше поле з токеном.
        result.append('checkbox_access_token')
        # Додаємо поля з ID та URL чека в модель замовлення.
        if 'pos.order' in result:
            result['pos.order'].extend(
                ['checkbox_receipt_id', 'checkbox_receipt_url'])
        return result

    @api.model
    def cron_close_overdue_sessions(self):
        """Метод, який викликається Кроном щоночі для закриття сесій"""
        _logger.info("Крон ПРРО: Початок перевірки відкритих сесій POS...")

        # Знаходимо всі сесії які зараз відкриті (status = 'opened')
        opened_sessions = self.search([('state', '=', 'opened')])

        for session in opened_sessions:
            _logger.info(f"Крон ПРРО: Автоматично закриваємо забуту сесію {session.name}")
            try:
                # Викликаємо наш стандартний метод закриття сесії Odoo, який всередині запускає фіскалізацію в Checkbox
                session.action_pos_session_close()

                if session.state == 'closed' and not session.stop_at:
                    session.stop_at = fields.Datetime.now()

                if session.state != 'closed':
                    session.action_pos_session_closing_control()
                    if not session.stop_at:
                        session.stop_at = fields.Datetime.now()

            except Exception as e:
                _logger.error(f"Крон ПРРО: Помилка закриття сесії {session.name}: {str(e)}")
