from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_storno = fields.Boolean(
        string='Storno',
        default=False,
        help="Indicates if this line is a storno (reversal) line"
    )

    @api.model
    def create(self, vals):
        # Check if this is a storno line based on context or other criteria
        if 'is_storno' not in vals:
            # You can add logic here to determine if this is a storno line
            # For example, check if there's a specific context or if the move type is 'out_refund'
            move_id = vals.get('move_id')
            if move_id:
                move = self.env['account.move'].browse(move_id)
                if move.move_type in ['out_refund', 'in_refund']:
                    vals['is_storno'] = True
        
        return super(AccountMoveLine, self).create(vals)

    def write(self, vals):
        # Prevent editing price fields if line is marked as storno
        if self.is_storno and any(field in vals for field in ['price_unit', 'price_subtotal', 'price_total']):
            raise models.UserError('Cannot edit price fields on storno lines!')
        return super(AccountMoveLine, self).write(vals)
