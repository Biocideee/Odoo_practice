from odoo import fields, models, Command


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_create_correction(self):
        self.ensure_one()

        new_lines = []

        for line in self.invoice_line_ids:
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
                'is_storno': True,
            }

            new_lines.append(Command.create(storno_line))

        new_invoice = self.create({
            'move_type' : self.move_type,
            'partner_id' : self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': new_lines,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': new_invoice.id,
            'view_mode': 'form',
            'target': 'new',
        }