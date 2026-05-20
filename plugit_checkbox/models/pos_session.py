import requests
import logging
import base64  # НОВЕ: бібліотека для кодування файлів
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

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
    _inherit = 'pos.session'

    checkbox_access_token = fields.Char(string="Checkbox JWT Токен", copy=False)

    def action_pos_session_open(self):
        res = super().action_pos_session_open()
        for session in self:
            if session.state == 'opened' and session.config_id.checkbox_license_key and not session.checkbox_access_token:
                try:
                    session._checkbox_init_and_open_shift()
                except UserError as e:
                    _logger.error(f"Checkbox: помилка відкриття зміни для сесії {session.name}: {e}")
                    raise
        return res

    def set_opening_control(self, *args, **kwargs):
        res = super().set_opening_control(*args, **kwargs)
        for session in self:
            if session.config_id.checkbox_license_key and not session.checkbox_access_token:
                try:
                    session._checkbox_init_and_open_shift()
                except UserError as e:
                    _logger.error(f"Checkbox: помилка відкриття зміни для сесії {session.name}: {e}")
                    raise
        return res

    def _checkbox_get_fresh_token(self):
        self.ensure_one()
        user = self.user_id
        if not user.checkbox_login or not user.checkbox_password:
            return None
        try:
            response = requests.post(
                "https://api.checkbox.ua/api/v1/cashier/signin",
                json={"login": user.checkbox_login, "password": user.checkbox_password},
                timeout=10,
            )
            response.raise_for_status()
            token = response.json().get('access_token')
            if token:
                self.sudo().write({'checkbox_access_token': token})
            return token
        except Exception as e:
            _logger.error(f"Checkbox: не вдалося оновити токен для {self.name}: {e}")
            return None

    def _checkbox_init_and_open_shift(self):
        # ... (Цей метод залишається без змін, такий самий як у тебе був) ...
        self.ensure_one()
        user = self.user_id
        if not user.checkbox_login or not user.checkbox_password:
            raise UserError("У вашому профілі користувача не налаштовано логін/пароль Checkbox!")

        try:
            response = requests.post(
                "https://api.checkbox.ua/api/v1/cashier/signin",
                json={"login": user.checkbox_login, "password": user.checkbox_password},
                timeout=10,
            )
            response.raise_for_status()
            token = response.json().get('access_token')
            if not token:
                raise UserError("Checkbox не повернув токен авторизації. Перевірте логін/пароль.")
            self.sudo().write({'checkbox_access_token': token})

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

            if shift_resp.status_code in [200, 201, 202]:
                _logger.info(f"Checkbox: зміну успішно відкрито для сесії {self.name}.")
            elif shift_resp.status_code in [400, 422]:
                search_text = body
                try:
                    json_body = shift_resp.json()
                    search_text += json_body.get('code', '') + json_body.get('message', '')
                except Exception:
                    pass

                if any(marker in search_text for marker in ALREADY_OPEN_MARKERS):
                    _logger.info(
                        f"Checkbox: зміна вже відкрита ({shift_resp.status_code}) для сесії {self.name}, продовжуємо.")
                else:
                    _logger.warning(
                        f"Checkbox: {shift_resp.status_code} при відкритті зміни для {self.name}: {body}. Продовжуємо.")
            else:
                raise UserError(f"Не вдалося відкрити зміну ПРРО Checkbox (HTTP {shift_resp.status_code}): {body}")

        except requests.exceptions.HTTPError as e:
            error_body = e.response.json() if e.response.headers.get('Content-Type', '').startswith(
                'application/json') else e.response.text
            message = error_body.get('message', str(error_body)) if isinstance(error_body, dict) else str(error_body)
            raise UserError(f"Помилка авторизації Checkbox: {message}")
        except requests.exceptions.RequestException as e:
            raise UserError(f"Помилка з'єднання з Checkbox: {e}")

    def action_pos_session_close(self, *args, **kwargs):
        res = super().action_pos_session_close(*args, **kwargs)
        for session in self:
            if session.config_id.checkbox_license_key:
                session._checkbox_close_shift_and_signout()
        return res

    def _checkbox_close_shift_and_signout(self):
        """Закриття зміни, збереження Z-звіту як аттачменту та Sign Out"""
        self.ensure_one()

        token = self._checkbox_get_fresh_token()
        if not token:
            self.sudo().write({'checkbox_access_token': False})
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "X-License-Key": self.config_id.checkbox_license_key,
        }

        try:
            # 1. Закриття зміни (Z-звіт)
            report_resp = requests.post(
                "https://api.checkbox.ua/api/v1/shifts/close",
                headers=headers,
                timeout=20,
            )
            if report_resp.status_code in [200, 201, 202]:
                _logger.info(f"Checkbox: зміну успішно закрито для сесії {self.name}.")

                # Завантаження та збереження Z-звіту
                try:
                    shift_data = report_resp.json()
                    z_report = shift_data.get('z_report', {})
                    report_id = z_report.get('id')

                    if report_id:
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
                            _logger.info(f"Z-звіт збережено як прикріплення до сесії {self.name}")
                        else:
                            _logger.warning(f"Не вдалося завантажити текст Z-звіту. HTTP {text_resp.status_code}")
                except Exception as e:
                    _logger.error(f"Помилка при збереженні Z-звіту як аттачменту: {e}")

            else:
                _logger.error(f"Checkbox: помилка при закритті сесії {self.name}: {report_resp.text}")

            # ========================================================
            # НОВИЙ БЛОК: SIGN OUT КАСИРА
            # ========================================================
            signout_url = "https://api.checkbox.ua/api/v1/cashier/signout"
            try:
                signout_resp = requests.post(signout_url, headers=headers, json={}, timeout=10)

                # signout_resp.ok перевіряє всі успішні коди (200, 201, 204 тощо)
                if signout_resp.ok:
                    _logger.info(f"Checkbox: касир успішно вийшов (Sign Out) для сесії {self.name}.")
                else:
                    _logger.warning(
                        f"Checkbox: помилка при Sign Out (HTTP {signout_resp.status_code}): {signout_resp.text}")
            except Exception as e:
                _logger.error(f"Checkbox: помилка з'єднання при Sign Out: {e}")

        except requests.exceptions.RequestException as e:
            _logger.error(f"Checkbox: критична помилка зв'язку: {e}")
        finally:
            # Незалежно від того, чи вдався Sign Out, стираємо токен в Odoo
            self.sudo().write({'checkbox_access_token': False})

    def _load_pos_data_fields(self, config_id):
        result = super()._load_pos_data_fields(config_id)
        result.append('checkbox_access_token')
        if 'pos.order' in result:
            result['pos.order'].extend(['checkbox_receipt_id', 'checkbox_receipt_url'])
        return result
