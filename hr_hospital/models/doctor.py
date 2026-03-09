from odoo import fields, models, api
from datetime import date
from dateutil.relativedelta import relativedelta


class Doctor(models.Model):
    _name = 'hr_hospital.doctor'
    _description = 'Doctor'
    _inherit = 'hr_hospital.abstract_person'
    _rec_name = 'full_name'

    # Користувач системи
    user_id = fields.Many2one('res.users', string='System User')

    # Спеціальність
    specialty_id = fields.Many2one('hr_hospital.doctor_specialty', string='Specialty')

    # Інтерн
    is_intern = fields.Boolean(string='Is Intern')

    # Лікар-ментор
    doctor_mentor_id = fields.Many2one('hr_hospital.doctor', string='Mentor Doctor', domain=[('is_intern', '=', False)])

    # Список інтернів, які прив'язані до лікаря
    intern_ids = fields.One2many('hr_hospital.doctor', 'doctor_mentor_id', string='Interns')

    # Ліцензійний номер
    license_number = fields.Char(string='Licence Number', copy=False)

    # Дата видачі ліцензії
    licence_date = fields.Date(string='Licence Date')

    # Досвід роботи
    experience = fields.Integer(string='Experience', compute='_compute_licence_date')

    # Обчислення досвіду роботи на основі отриманих даних дати видачі ліцензії
    @api.depends('licence_date')
    def _compute_licence_date(self):
        for rec in self:
            if rec.licence_date:
                today = date.today()

                delta = relativedelta(today, rec.licence_date)

                rec.experience = delta.years
            else:
                rec.experience = 0

    # Рейтинг
    rating = fields.Float(string='Rating', digits=(3, 2), default=0.0)

    # Графік роботи
    work_schedule_ids = fields.One2many('hr_hospital.doctor_schedule', 'doctor_id', string='Work Schedule')

    # Країна навчання
    edu_country_id = fields.Many2one('res.country', string='Education country')
