from odoo import fields, models


class Diagnosis(models.Model):
    _name = 'hr_hospital.diagnosis'
    _description = 'Diagnosis'

    # Візит
    visit_id = fields.Many2one('hr_hospital.patient_visits', ondelete='cascade')

    # Хвороба
    disease_id = fields.Many2one('hr_hospital.disease', string='Disease')

    # Опис діагнозу
    description_of_diagnosis = fields.Text(string='Description of Diagnosis')

    # Призначене лікування
    prescribed_treatment = fields.Html(string='Prescribed Treatment')

    # Затверджено
    approved = fields.Boolean(string='Approved', default=False)

    # Лікар, що затвердив
    doctor_who_approved_id = fields.Many2one('hr_hospital.doctor', readonly=True)

    # Дата затвердження
    approval_date = fields.Datetime(string='Approval Date', readonly=True)

    # Ступінь тяжкості
    severity = fields.Selection([('mild', 'Mild'),
                                 ('moderate', 'Moderate'),
                                 ('severe', 'Severe'),
                                 ('critical', 'Critical')])
