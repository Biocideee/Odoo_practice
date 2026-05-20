from odoo.tests.common import TransactionCase
from unittest.mock import patch, MagicMock

from odoo.exceptions import UserError
import requests


class TestCheckboxFlow(TransactionCase):

    def setUp(self):
        super(TestCheckboxFlow, self).setUp()
        self.PosConfig = self.env['pos.config']
        self.PosSession = self.env['pos.session']
        self.User = self.env['res.users']

        # Setup test data
        self.user = self.User.create({
            'name': 'Test Cashier',
            'login': 'test_cashier',
            'groups_id': [(6, 0, [self.env.ref('point_of_sale.group_pos_user').id])],
            'checkbox_login': 'test_cb_login',
            'checkbox_password': 'test_cb_password',
        })

        self.pos_config = self.PosConfig.create({
            'name': 'Test POS',
            'checkbox_license_key': 'test_license_key',
        })

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_01_session_open_success(self, mock_post):
        """Test successful session opening and shift initialization"""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {'access_token': 'test_token_123'}

        mock_shift_response = MagicMock()
        mock_shift_response.status_code = 201
        mock_post.side_effect = [mock_auth_response, mock_shift_response]

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })

        self.assertEqual(session.checkbox_access_token, 'test_token_123')
        self.assertEqual(mock_post.call_count, 2)

        auth_call_args, auth_call_kwargs = mock_post.call_args_list[0]
        self.assertEqual(auth_call_args[0], "https://api.checkbox.ua/api/v1/cashier/signin")
        self.assertEqual(auth_call_kwargs['json']['login'], 'test_cb_login')

        shift_call_args, shift_call_kwargs = mock_post.call_args_list[1]
        self.assertEqual(shift_call_args[0], "https://api.checkbox.ua/api/v1/shifts")
        self.assertEqual(shift_call_kwargs['headers']['Authorization'], 'Bearer test_token_123')

    def test_02_session_open_missing_credentials(self):
        """Test session opening failure due to missing Checkbox credentials"""
        self.user.write({'checkbox_login': False})
        with self.assertRaises(UserError):
            self.PosSession.create({
                'config_id': self.pos_config.id,
                'user_id': self.user.id
            })

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_03_session_open_auth_failure(self, mock_post):
        """Test session opening failure due to invalid Checkbox credentials"""
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 401
        # Need to simulate requests.exceptions.HTTPError, let's just make it raise a UserError
        # directly in the side effect since our code handles HTTPError by raising UserError
        mock_post.side_effect = requests.exceptions.RequestException('Auth Error')

        with self.assertRaises(UserError):
            self.PosSession.create({
                'config_id': self.pos_config.id,
                'user_id': self.user.id
            })

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_04_session_close_z_report(self, mock_post):
        """Test Z-report generation on session close"""
        # Create a session without triggering the _checkbox_init_and_open_shift logic
        # by creating it without the license key on the config, then writing the config
        # and token directly
        temp_config = self.PosConfig.create({'name': 'Temp POS'})
        session = self.PosSession.create({
            'config_id': temp_config.id,
            'user_id': self.user.id
        })
        session.write({
            'config_id': self.pos_config.id,
            'checkbox_access_token': 'dummy_token'
        })

        mock_report_response = MagicMock()
        mock_report_response.status_code = 201
        mock_post.return_value = mock_report_response

        session.action_pos_session_closing_control()

        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], "https://api.checkbox.ua/api/v1/reports")
        self.assertEqual(call_kwargs['headers']['Authorization'], 'Bearer dummy_token')
        self.assertFalse(session.checkbox_access_token)

    def test_05_get_pos_ui_models_for_loading(self):
        """Test if token is passed to frontend"""
        session = self.env['pos.session'].new({})
        models = session._get_pos_ui_models_for_loading()
        self.assertIn('checkbox_access_token', models.get('pos.session', {}).get('fields', []))
