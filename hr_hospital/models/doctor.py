from odoo import fields, models, api
from datetime import date
from dateutil.relativedelta import relativedelta


class Doctor(models.Model):
    _name = 'hr_hospital.doctor'
    _description = 'Doctor'
    _inherit = 'hr_hospital.abstract_person'


# Користувач системи
system_user_id = fields.Many2one(comodel_name='res.users', string='System User')

# Спеціальність
specialty_id = fields.Many2one(comodel_name='hr_hospital.doctor_specialty', string='Specialty')

# Інтерн
is_intern = fields.Boolean(string='Is Intern')

# Лікар-ментор
doctor_mentor_id = fields.Many2one(comodel_name='hr_hospital.doctor', string='Mentor Doctor')

# Ліцензійний номер
license_number = fields.Char(string='Licence Number')

# Дата видачі ліцензії
licence_date = fields.Date(string='Licence Date')

# Досвід роботи
experience = fields.Integer(string='Experience', compute='_compute_licence_date')


# Обчислення досвіду роботи на основі отриманих даних дати видачі ліцензії
@api.depends('licence_date')
def _compute_licence_date(self):
    for rec in self:
        if rec.license_date:
            today = date.today()

            delta = relativedelta(today, rec.license_date)

            rec.experience = delta.years
        else:
            rec.experience = 0


# Рейтинг
rating = fields.Float(string='Rating', digits=(3, 2), default=0.0)

# Графік роботи
work_graphic_ids = fields.One2many(comodel_name='hr_hospital.doctor_work_graphic', string='Work Graphic')

# Країна навчання
edu_country_id = fields.Many2one(comodel_name='res.country', string='Education country')
