# -*- coding: utf-8 -*-
from odoo import fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    checkbox_login = fields.Char(string="Checkbox Логін", groups="point_of_sale.group_pos_manager")
    # encrypt='base64' забезпечує базове приховування пароля в БД Odoo
    checkbox_password = fields.Char(string="Checkbox Пароль", groups="point_of_sale.group_pos_manager")