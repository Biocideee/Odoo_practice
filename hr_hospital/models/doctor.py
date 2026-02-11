from odoo import fields, models, api


class Doctor(models.Model):
    _name = 'hr_hospital.doctor'
    _description = 'Doctor'
    _inherit = 'hr_hospital.abstract_person'


system_user_id = fields.Many2one(comodel_name='res.users', string='System User')
# specialty = fields.Many2one(comodel_name='hr.hospital.doctor.specialty', string='Specialty')
is_intern = fields.Boolean(string='Is Intern')
doctor_mentor_id = fields.Many2one(comodel_name='hr_hospital.doctor', string='Mentor Doctor')
license_number = fields.Char(string='Licence Number')
licence_date = fields.Date(string='Licence Date')
# experience  = today - license_number.date
rating = fields.Float(string='Rating', digits=(3, 2), default=0.0)
# work_graphic_id = fields.Many2one(comodel_name='hr.hospital.doctor.work.graphic', string='Work Graphic')
edu_country_id = fields.Many2one(comodel_name='res.country', string='Education country')
