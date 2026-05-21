# -*- coding: utf-8 -*-

"""
Цей файл розширює стандартну модель замовлення Point of Sale (pos.order)
для збереження інформації про фіскалізований чек.
"""

from odoo import fields, models, api


class PosOrder(models.Model):
    """
    Розширення моделі замовлення POS.
    """
    _inherit = 'pos.order'

    # Поле для зберігання публічного посилання на фіскалізований чек.
    # Це посилання генерується на фронтенді (в JS) після успішної фіскалізації
    # і записується сюди при збереженні замовлення.
    # Поле `readonly=True` запобігає ручному редагуванню посилання.
    # `copy=False` означає, що при дублюванні замовлення посилання не скопіюється.
    checkbox_receipt_url = fields.Char(
        string="Посилання на чек Checkbox",
        readonly=True,
        copy=False
    )

    # Поле для ID чека, без нього чек не виведеться на друк після перезавантаження сторінки
    checkbox_receipt_id = fields.Char(
        string="ID чека Checkbox",
        readonly=True,
        copy=False
    )

    @api.model
    def _order_fields(self, ui_order):
        """Перехоплюємо масив даних з фронтенду та записуємо в базу даних"""
        res = super(PosOrder, self)._order_fields(ui_order)
        res['checkbox_receipt_id'] = ui_order.get('checkbox_receipt_id')
        res['checkbox_receipt_url'] = ui_order.get('checkbox_receipt_url')
        return res
