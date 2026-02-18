from odoo import fields, models
from odoo.addons.hr_hospital.models.patient_visits import doctor_id


class DoctorSchedule(models.Model):
    _name = 'hr_hospital.doctor_schedule'
    _description = 'Doctor Schedule'


# Лікар
doctor = fields.Many2one(comodel_name='hr_hospital.doctor', required=True)

# День тижня
day_of_week = fields.Selection([('MON', 'Monday'),
                                ('TUE', 'Tuesday'),
                                ('WED', 'Wednesday'),
                                ('THU', 'Thursday'),
                                ('FRI', 'Friday'),
                                ('SAT', 'Saturday'),
                                ('SUN', 'Sunday'),], string='Day of week')

