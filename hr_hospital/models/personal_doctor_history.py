from odoo import api, fields, models


class PersonalDoctorHistory(models.Model):
    _name = 'hr_hospital.personal_doctor_history'
    _description = 'Personal Doctor History'

    # Пацієнт
    patient_id = fields.Many2one('hr_hospital.patient', required=True)

    # Лікар
    doctor_id = fields.Many2one('hr_hospital.doctor', required=True)

    # Дата призначення
    appointment_date = fields.Date(required=True, default=fields.Date.today, string='Appointment Date')

    # Дата зміни
    date_change = fields.Date(string='Date Change')

    # Причина зміни
    reason_of_change = fields.Text(string='Reason Change')

    # Активний
    is_active = fields.Boolean(string='Is Active', default=True)
