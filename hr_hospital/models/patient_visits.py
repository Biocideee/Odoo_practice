from odoo import fields, models, api


class PatientVisits(models.Model):
    _name = 'hr_hospital.patient_visits'
    _description = 'Patient Visits'

    # Статус візиту
    visit_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('didnt_appear', 'Did not appear'),
    ], string='Patient Visits Status')

    # Заплановані дата та час
    Planned_Date_and_time = fields.Datetime(string='Date and Time')

    # Фактичні дата та час
    Actual_Date_and_time = fields.Datetime(string='Actual Date and Time',
                                           readonly=True if visit_status == 'Completed' or visit_status == 'completed' else False)
    # Лікар
    doctor_id = fields.Many2one('hr_hospital.doctor', required=True)

    # Пацієнт
    patient_id = fields.Many2one('hr_hospital.patient', required=True)

    # Тип візиту
    type_of_visit = fields.Selection([('initial', 'Initial'),
                                      ('secondary', 'Secondary'),
                                      ('preventive', 'Preventive'),
                                      ('urgent', 'Urgent')])

    # Діагнози
    diagnosis_ids = fields.One2many('hr_hospital.diagnosis', string='Diagnosis')

    # Рекомендації
    recommendations = fields.Html(string='Recommendations')

    # Вартість візиту
    value_of_visit = fields.Monetary(currency_field='Гривні', string='Value')

    # Валюта
    currency_id = fields.Many2one('res.currency', required=True)
