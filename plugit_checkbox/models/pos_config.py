# -*- coding: utf-8 -*-

"""
Цей файл розширює стандартну модель налаштувань Point of Sale (pos.config)
для додавання поля з ключем ліцензії каси від сервісу Checkbox.
"""

from odoo import fields, models


class PosConfig(models.Model):
    """
    Розширення моделі налаштувань POS.
    """
    _inherit = 'pos.config'

    # Нове поле для зберігання ключа ліцензії каси Checkbox.
    # Цей ключ є унікальним для кожної віртуальної каси, зареєстрованої в ДПС.
    # `copy=False` запобігає копіюванню цього значення при дублюванні
    # конфігурації POS, оскільки кожна нова каса повинна мати свій унікальний ключ.
    checkbox_license_key = fields.Char(
        string="Ключ ліцензії каси Checkbox",
        copy=False
    )
