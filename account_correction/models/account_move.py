from odoo import fields, models, Command
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_create_correction(self):
        for move in self:
            if any(line.is_correction_line for line in move.invoice_line_ids):
                raise UserError("Цей рахунок вже відкориговано")
            new_lines = []

            for line in move.invoice_line_ids:
                if line.is_correction_line:
                    continue
                
                copy_line = {
                    'name': line.name,
                    'price_unit': line.price_unit,
                    'quantity': line.quantity,
                }

                new_lines.append(Command.create(copy_line))

                storno_line = {
                    'name': line.name,
                    'price_unit': line.price_unit,
                    'quantity': -line.quantity,
                    'is_correction_line': True,
                }

                new_lines.append(Command.create(storno_line))

            new_invoice = self.create({
                'move_type' : move.move_type,
                'partner_id' : move.partner_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': new_lines,
            })

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': new_invoice.id,
                'view_mode': 'form',
                'target': 'current',
            }