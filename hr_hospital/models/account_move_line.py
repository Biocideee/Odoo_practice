from odoo import fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_storno = fields.Boolean(string="Storno", default=False)
