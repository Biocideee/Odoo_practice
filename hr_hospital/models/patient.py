from odoo import fields, models, api


class Patient(models.Model):
    _name = 'hr_hospital.patient'
    _description = 'Patient'
    _inherit = 'hr_hospital.abstract_person'


# Персональний лікар
personal_doctor_id = fields.Many2one(comodel_name='hr_hospital.doctor', string='Personal Doctor')

# Паспортні дані
passport_data = fields.Char(string='Passport Data', size=10)

# Контактна особа
contact_person_id = fields.Many2one(comodel_name='hr_hospital.contact_person', string='Contact Person')

# Група крові
blood_type = fields.Selection([
    ('o_plus', 'O(I) Rh+'),
    ('o_minus', 'O(I) Rh-'),
    ('a_plus', 'A(II) Rh+'),
    ('a_minus', 'A(II) Rh-'),
    ('b_plus', 'B(III) Rh+'),
    ('b_minus', 'B(III) Rh-'),
    ('ab_plus', 'AB(IV) Rh+'),
    ('ab_minus', 'AB(IV) Rh-'),
], string='Blood Type')

# Алергії
allergies = fields.Text(string='Allergies')

# Страхова компанія
insurance_company_id = fields.Many2one(comodel_name='res.partner', string='Insurance Company',
                                       domain=[('company_id', '=', True)])

# Номер страхового поліса
insurance_policy_number = fields.Char(string='Insurance Policy Number')

# Історія персональних лікарів
personal_doctor_history_ids = fields.One2many(comodel_name='hr_hospital.doctor', )
