from odoo import fields, models


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    partner_ids = fields.Many2many("res.partner", string="Адреси провайдерів", check_company=True)
    company_partner_id = fields.Many2one(related="company_id.partner_id")
