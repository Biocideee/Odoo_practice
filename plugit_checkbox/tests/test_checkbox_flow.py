# -*- coding: utf-8 -*-

"""
Цей файл містить автоматизовані тести (unit tests) для перевірки
коректності роботи інтеграції Odoo POS з сервісом Checkbox.
"""

from unittest.mock import MagicMock, patch
import requests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCheckboxFlow(TransactionCase):

    def setUp(self):
        super(TestCheckboxFlow, self).setUp()
        self.PosConfig = self.env['pos.config']
        self.PosSession = self.env['pos.session']
        self.User = self.env['res.users']

        self.user = self.User.create({
            'name': 'Test Cashier',
            'login': 'test_cashier_123',
            'checkbox_login': 'test_cb_login',
            'checkbox_password': 'test_cb_password',
        })

        self.pos_config = self.PosConfig.create({
            'name': 'Test POS',
            'checkbox_license_key': 'test_license_key',
        })

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_01_session_open_success(self, mock_post):
        mock_auth_response = MagicMock(status_code=200)
        mock_auth_response.json.return_value = {'access_token': 'test_token_123'}

        mock_shift_response = MagicMock(status_code=201)
        mock_post.side_effect = [mock_auth_response, mock_shift_response]

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })

        session.set_opening_control(0.0, '')

        self.assertEqual(session.checkbox_access_token, 'test_token_123')
        self.assertEqual(mock_post.call_count, 2)

    def test_02_session_open_missing_credentials(self):
        self.user.write({'checkbox_login': False})
        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })

        with self.assertRaises(UserError):
            session.set_opening_control(0.0, '')

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_03_session_open_auth_failure(self, mock_post):
        mock_auth_response = MagicMock(status_code=401)
        http_error = requests.exceptions.HTTPError()
        http_error.response = mock_auth_response
        http_error.response.json = lambda: {'message': 'Invalid credentials'}
        mock_auth_response.raise_for_status.side_effect = http_error

        mock_post.return_value = mock_auth_response

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })

        with self.assertRaises(UserError):
            session.set_opening_control(0.0, '')

    @patch('time.sleep') # Глушимо sleep  # Глушимо sleep
    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.get')
    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_04_session_close_z_report_and_signout(self, mock_post, mock_get, mock_sleep):
        mock_auth = MagicMock(status_code=200)
        mock_auth.json.return_value = {'access_token': 'dummy_token'}

        mock_close = MagicMock(status_code=200)
        mock_close.json.return_value = {'z_report': {'id': 'rep_1'}}

        mock_signout = MagicMock(ok=True, status_code=204)

        mock_post.side_effect = [mock_auth, mock_close, mock_signout]

        mock_get.return_value = MagicMock(status_code=200, text="TEST_Z_REPORT")

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        session.write({'checkbox_access_token': 'dummy_token'})

        session.action_pos_session_close()

        self.assertTrue(
            any(call[0][0] == "https://api.checkbox.ua/api/v1/cashier/signout"
                for call in mock_post.call_args_list)
        )
        self.assertFalse(session.checkbox_access_token)

    def test_05_get_pos_ui_models_for_loading(self):
        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        fields = session._load_pos_data_fields(self.pos_config.id)
        self.assertIn('checkbox_access_token', fields)

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_06_already_closed_fallback(self, mock_post):
        """
        Перевірка Primary-Fallback: Якщо Checkbox повертає 422 (зміна вже закрита),
        система не повинна падати, а має спокійно продовжити роботу.
        """
        # Авторизація проходить успішно
        mock_auth = MagicMock(status_code=200)
        mock_auth.json.return_value = {'access_token': 'dummy_token'}

        # Запит на закриття повертає 422
        mock_close = MagicMock(status_code=422)
        http_error = requests.exceptions.HTTPError()
        http_error.response = mock_close
        http_error.response.json = lambda: {'message': 'Зміна вже закрита'}
        mock_close.raise_for_status.side_effect = http_error

        # Вихід касира успішний
        mock_signout = MagicMock(ok=True, status_code=204)

        mock_post.side_effect = [mock_auth, mock_close, mock_signout]

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        session.write({'checkbox_access_token': 'dummy_token'})

        # Якщо логіка правильна, код виконається без викидання UserError
        try:
            session.action_pos_session_close()
            success = True
        except Exception:
            success = False

        self.assertTrue(success, "Система впала при обробці помилки 422 замість того, щоб перехопити її.")
        self.assertFalse(session.checkbox_access_token, "Токен не був очищений після перехоплення помилки 422")