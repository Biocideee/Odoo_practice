from odoo import fields, models, api


class DoctorSpecialty(models.Model):
    _name = 'hr_hospital.doctor_specialty'
    _description = 'Doctor Specialty'

    # Назва
    title = fields.Char(string='Title', required=True)

    # Код спеціальності
    specialty_code = fields.Char(string='Specialty Code', required=True, size=10)

    # Опис
    description = fields.Text(string='Description')

    # Активна
    is_active = fields.Boolean(string='Active', default=True)

    # Лікарі
    doctor_ids = fields.One2many('hr_hospital.doctor', 'specialty_id', string='Doctors')
