from odoo import fields, models


class DoctorSchedule(models.Model):
    _name = 'hr_hospital.doctor_schedule'
    _description = 'Doctor Schedule'

    # Лікар
    doctor = fields.Many2one('hr_hospital.doctor', required=True)

    # День тижня
    day_of_week = fields.Selection([('MON', 'Monday'),
                                    ('TUE', 'Tuesday'),
                                    ('WED', 'Wednesday'),
                                    ('THU', 'Thursday'),
                                    ('FRI', 'Friday'),
                                    ('SAT', 'Saturday'),
                                    ('SUN', 'Sunday'), ], string='Day of week')

    # Час початку
    begin_time = fields.Float(string='Begin Time')

    # Час закінчення
    end_time = fields.Float(string='End Time')

    # Тип
    type_of_schedule = fields.Selection([('working_day', 'Working day'),
                                         ('vacation', 'Vacation'),
                                         ('hospital', 'Hospital'),
                                         ('conference', 'Conference'), ])

    # Примітки
    notes = fields.Char(string='Notes')
