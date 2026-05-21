# -*- coding: utf-8 -*-

"""
Цей файл розширює стандартну модель користувача (res.users)
для збереження облікових даних доступу до сервісу Checkbox.

Пароль зберігається у зашифрованому вигляді в базі даних Odoo,
використовуючи алгоритм Fernet з бібліотеки cryptography.
Ключ шифрування береться з файлу конфігурації odoo.conf (checkbox_encryption_key).
"""

import logging

from cryptography.fernet import Fernet

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Отримуємо ключ шифрування з конфігурації.
ENCRYPTION_KEY = config.get('checkbox_encryption_key')

# Ініціалізуємо об'єкт шифрування.
cipher = None
if ENCRYPTION_KEY:
    try:
        # Fernet вимагає ключ у байтовому форматі.
        cipher = Fernet(ENCRYPTION_KEY.encode())
    except Exception as e:
        _logger.critical(
            f"Помилка ініціалізації Fernet ключа: {e}"
        )
else:
    # Якщо ключа немає, виводимо попередження, але не блокуємо роботу модуля.
    _logger.warning(
        "Ключ checkbox_encryption_key не знайдено в odoo.conf! "
        "Паролі не будуть зашифровані."
    )


class ResUsers(models.Model):
    """
    Розширення моделі користувача.
    """
    _inherit = 'res.users'

    # Логін для доступу до Checkbox.
    # Поле доступне лише менеджерам POS та адміністраторам системи.
    checkbox_login = fields.Char(
        string="Checkbox Логін",
        groups="point_of_sale.group_pos_manager,base.group_erp_manager"
    )

    # Приховане поле, в якому зберігається зашифрований пароль.
    _encrypted_checkbox_password = fields.Char(
        string="Зашифрований Checkbox Пароль"
    )

    # Віртуальне поле для введення/перегляду пароля в інтерфейсі.
    # Воно обчислюється на льоту (_compute) та зашифровується перед
    # збереженням (_inverse).
    checkbox_password = fields.Char(
        string="Checkbox Пароль",
        compute="_compute_checkbox_password",
        inverse="_inverse_checkbox_password",
        groups="point_of_sale.group_pos_manager,base.group_erp_manager"
    )

    @api.depends('_encrypted_checkbox_password')
    def _compute_checkbox_password(self):
        """
        Метод для розшифрування пароля.
        Викликається, коли система або користувач звертається до
        поля `checkbox_password`.
        """
        for rec in self:
            if rec._encrypted_checkbox_password and cipher:
                try:
                    # Розшифровуємо і перетворюємо назад у рядок.
                    rec.checkbox_password = cipher.decrypt(
                        rec._encrypted_checkbox_password.encode()
                    ).decode()
                except Exception as e:
                    _logger.error(
                        f"Не вдалося розшифрувати пароль для {rec.name}: {e}"
                    )
                    rec.checkbox_password = False
            else:
                # Якщо шифратор не ініціалізовано, повертаємо як є.
                rec.checkbox_password = rec._encrypted_checkbox_password

    def _inverse_checkbox_password(self):
        """
        Метод для шифрування пароля перед збереженням.
        Викликається, коли користувач змінює значення поля
        `checkbox_password`.
        """
        for rec in self:
            if rec.checkbox_password and cipher:
                # Шифруємо і зберігаємо як рядок.
                rec._encrypted_checkbox_password = cipher.encrypt(
                    rec.checkbox_password.encode()
                ).decode()
            else:
                # Якщо шифратор не ініціалізовано, зберігаємо як є.
                rec._encrypted_checkbox_password = rec.checkbox_password
