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

    # Ім'я візиту, яке Оду підтягує замість випадкового ідентифікатора
    name = fields.Char(string='Visit', required=True, copy=False, readonly=True, default='New')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr_hospital.patient_visits.sequence') or 'New'

        return super(PatientVisits, self).create(vals_list)

    # Заплановані дата та час
    planned_date_and_time = fields.Datetime(string='Date and Time')

    # Фактичні дата та час
    actual_date_and_time = fields.Datetime(string='Actual Date and Time')
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
    diagnosis_ids = fields.One2many('hr_hospital.diagnosis', 'visit_id', string='Diagnosis')

    # Рекомендації
    recommendations = fields.Html(string='Recommendations')

    # Вартість візиту
    value_of_visit = fields.Monetary(string='Value')

    # Валюта
    currency_id = fields.Many2one('res.currency', required=True)
