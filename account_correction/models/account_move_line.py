from odoo import fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_correction_line = fields.Boolean(string="Correction Line", default=False)
