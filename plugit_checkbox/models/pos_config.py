from odoo import fields, models

class PosConfig(models.Model):
    _inherit = 'pos.config'

    checkbox_license_key = fields.Char(string="Ключ ліцензії каси Checkbox")