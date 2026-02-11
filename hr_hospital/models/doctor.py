from odoo import fields, models, api


class Doctor(models.Model):
    _name = 'hr.hospital.doctor'
    _description = 'Doctor'
    _inherit = 'hr.hospital.abstract.person'


system_user_id = fields.Many2one(comodel_name='res.users', string='System User')
# specialty = fields.Many2one(comodel_name='hr.hospital.doctor.specialty', string='Specialty')
is_intern = fields.Boolean(string='Is Intern')
doctor_mentor = fields.Many2one(comodel_name='hr.hospital.doctor', string='Doctor')
license_number = fields.Date(string='Licence Number')
# experience  = today - license_number.date
rating = fields.Float(string='Rating')
# work_graphic = fields.Many2one(comodel_name='hr.hospital.doctor.work.graphic', string='Work Graphic')
edu_country = fields.Many2one(comodel_name='res.country', string='Education country')
