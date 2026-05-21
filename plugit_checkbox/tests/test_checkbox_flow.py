# -*- coding: utf-8 -*-

"""
Цей файл містить автоматизовані тести (unit tests) для перевірки
коректності роботи інтеграції Odoo POS з сервісом Checkbox.

Тести використовують бібліотеку `unittest.mock` для імітації
відповідей від API Checkbox, що дозволяє запускати їх без
реального з'єднання з інтернетом або дійсних облікових даних.
"""

from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCheckboxFlow(TransactionCase):
    """
    Клас, що містить набір тестів для перевірки основного потоку роботи
    (відкриття сесії, закриття сесії, обробка помилок).
    Успадковується від TransactionCase, що гарантує відкат змін у базі даних
    після завершення кожного тесту.
    """

    def setUp(self):
        """
        Метод, який виконується перед кожним тестом.
        Тут ми готуємо тестові дані: створюємо користувача-касира
        та конфігурацію POS.
        """
        super(TestCheckboxFlow, self).setUp()
        self.PosConfig = self.env['pos.config']
        self.PosSession = self.env['pos.session']
        self.User = self.env['res.users']

        # Створюємо тестового користувача з даними для Checkbox
        self.user = self.User.create({
            'name': 'Test Cashier',
            'login': 'test_cashier_123',
            'checkbox_login': 'test_cb_login',
            'checkbox_password': 'test_cb_password',
        })

        # Створюємо тестову конфігурацію POS з ключем ліцензії
        self.pos_config = self.PosConfig.create({
            'name': 'Test POS',
            'checkbox_license_key': 'test_license_key',
        })

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_01_session_open_success(self, mock_post):
        """
        Перевірка успішного відкриття зміни через метод set_opening_control.
        
        Очікуваний результат:
        - Виконується запит на авторизацію (signin).
        - Виконується запит на відкриття зміни (shifts).
        - Токен зберігається в сесії.
        """
        # Імітуємо успішну відповідь на запит авторизації
        mock_auth_response = MagicMock(status_code=200)
        mock_auth_response.json.return_value = {
            'access_token': 'test_token_123'
        }

        # Імітуємо успішну відповідь на запит відкриття зміни
        mock_shift_response = MagicMock(status_code=201)

        # Вказуємо, що `requests.post` повинен повертати ці дві відповіді
        # по черзі
        mock_post.side_effect = [mock_auth_response, mock_shift_response]

        # Створюємо сесію в Odoo
        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })

        # Симулюємо підтвердження відкриття зміни (введення початкової суми)
        session.set_opening_control(0.0, '')

        # Перевіряємо, що токен успішно зберігся
        self.assertEqual(session.checkbox_access_token, 'test_token_123')
        # Перевіряємо, що було зроблено два запити (signin та shifts)
        self.assertEqual(mock_post.call_count, 2)

    def test_02_session_open_missing_credentials(self):
        """
        Перевірка обробки ситуації, коли у касира не вказано логін ПРРО.
        
        Очікуваний результат:
        - При спробі відкрити зміну система повинна згенерувати помилку UserError.
        """
        # Видаляємо логін у тестового користувача
        self.user.write({'checkbox_login': False})

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        
        # Перевіряємо, що виклик `set_opening_control` викидає UserError
        with self.assertRaises(UserError):
            session.set_opening_control(0.0, '')

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_03_session_open_auth_failure(self, mock_post):
        """
        Перевірка обробки неправильного пароля від ПРРО (помилка 401).
        
        Очікуваний результат:
        - API Checkbox повертає помилку 401.
        - Система Odoo перехоплює цю помилку і генерує зрозумілий UserError.
        """
        # Імітуємо відповідь з помилкою 401 (Unauthorized)
        mock_auth_response = MagicMock(status_code=401)
        http_error = requests.exceptions.HTTPError()
        http_error.response = mock_auth_response
        http_error.response.json = lambda: {'message': 'Invalid credentials'}
        http_error.response.headers = {'Content-Type': 'application/json'}
        mock_auth_response.raise_for_status.side_effect = http_error

        # Вказуємо, що `requests.post` повинен повертати цю помилкову відповідь
        mock_post.return_value = mock_auth_response

        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        
        # Перевіряємо, що Odoo генерує UserError при невдалій авторизації
        with self.assertRaises(UserError):
            session.set_opening_control(0.0, '')

    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.get')
    @patch('odoo.addons.plugit_checkbox.models.pos_session.requests.post')
    def test_04_session_close_z_report_and_signout(self, mock_post, mock_get):
        """
        Комплексний тест процесу закриття зміни.
        
        Очікуваний результат:
        - Оновлення токена (signin).
        - Закриття зміни (створення Z-звіту).
        - Отримання тексту Z-звіту та збереження його як прикріплення.
        - Вихід касира (signout).
        - Очищення токена в Odoo.
        """
        # 1. Імітуємо отримання свіжого токена
        mock_auth = MagicMock(status_code=200)
        mock_auth.json.return_value = {'access_token': 'dummy_token'}

        # 2. Імітуємо успішне закриття зміни (створення звіту)
        mock_close = MagicMock(status_code=200)
        mock_close.json.return_value = {'z_report': {'id': 'rep_1'}}

        # 3. Імітуємо успішний вихід касира
        mock_signout = MagicMock(ok=True, status_code=204)

        # Налаштовуємо порядок повернення відповідей для POST запитів
        mock_post.side_effect = [mock_auth, mock_close, mock_signout]
        
        # Імітуємо отримання тексту Z-звіту (GET запит)
        mock_get.return_value = MagicMock(
            status_code=200, text="TEST_Z_REPORT"
        )

        # Створюємо сесію і вручну встановлюємо їй токен
        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        session.write({'checkbox_access_token': 'dummy_token'})

        # Симулюємо закриття сесії в Odoo
        session.action_pos_session_close()

        # Перевіряємо, що запит на Sign Out дійсно був відправлений
        self.assertTrue(
            any(call[0][0] == "https://api.checkbox.ua/api/v1/cashier/signout"
                for call in mock_post.call_args_list)
        )
        # Перевіряємо, що токен після закриття видалено
        self.assertFalse(session.checkbox_access_token)
        
        # Перевіряємо, що файл з Z-звітом був прикріплений до сесії
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'pos.session'),
            ('res_id', '=', session.id)
        ])
        self.assertTrue(attachment)
        self.assertIn("Z_Report", attachment.name)

    def test_05_get_pos_ui_models_for_loading(self):
        """
        Перевірка передачі даних (токена) на фронтенд POS.
        
        Очікуваний результат:
        - Метод `_load_pos_data_fields` повинен додати поле 
          `checkbox_access_token` до переліку полів, що завантажуються 
          на клієнтську частину (JS).
        """
        session = self.PosSession.create({
            'config_id': self.pos_config.id,
            'user_id': self.user.id
        })
        
        # Викликаємо метод, який формує список полів для завантаження
        fields = session._load_pos_data_fields(self.pos_config.id)
        
        # Перевіряємо, що наше поле присутнє в цьому списку
        self.assertIn('checkbox_access_token', fields)
