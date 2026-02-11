from odoo import fields, models, api

class Patient(models.Model):
    _name = 'hr_hospital.patient'
    _description = 'Patient'
    _inherit = 'hr_hospital.abstract_person'

personal_doctor_id = fields.Many2one(comodel_name='hr_hospital.doctor', string='Personal Doctor')
passport_data = fields.Char(string='Passport Data', size=10)
# ..