from odoo import fields, models, api


class Patient(models.Model):
    _name = 'hr_hospital.patient'
    _description = 'Patient'
    _inherit = 'hr_hospital.abstract_person'
    _rec_name = 'full_name'

    # Персональний лікар
    personal_doctor_id = fields.Many2one('hr_hospital.doctor', string='Personal Doctor')

    # Паспортні дані
    passport_data = fields.Char(string='Passport Data', size=10)

    # Контактна особа
    contact_person_id = fields.Many2one('hr_hospital.contact_person', string='Contact Person')

    # Група крові
    blood_type = fields.Selection([
        ('o_plus', 'O(I) Rh+'),
        ('o_minus', 'O(I) Rh-'),
        ('a_plus', 'A(II) Rh+'),
        ('a_minus', 'A(II) Rh-'),
        ('b_plus', 'B(III) Rh+'),
        ('b_minus', 'B(III) Rh-'),
        ('ab_plus', 'AB(IV) Rh+'),
        ('ab_minus', 'AB(IV) Rh-'),
    ], string='Blood Type')

    # Алергії
    allergies = fields.Text(string='Allergies')

    # Страхова компанія
    insurance_company_id = fields.Many2one('res.partner', string='Insurance Company',
                                           domain=[('company_id', '=', True)])

    # Номер страхового поліса
    insurance_policy_number = fields.Char(string='Insurance Policy Number')

    # Історія персональних лікарів
    personal_doctor_history_ids = fields.One2many('hr_hospital.personal_doctor_history',
                                                  'doctor_id',
                                                  string='Personal Doctor History')
    # Зображення
    image = fields.Image(string='Image')

    # Картка пацієнта
    visit_count = fields.Integer(string='Visits Count', compute='_compute_visit_count')

    # Функція, яка рахує кількість візитів цього пацієнта в базі
    def _compute_visit_count(self):
        for record in self:
            record.visit_count = self.env['hr_hospital.patient_visits'].search_count([('patient_id', '=', record.id)])

    # Зв'язок з усіма візитами цього пацієнта
    visit_ids = fields.One2many('hr_hospital.patient_visits', 'patient_id', string='Visits')

    # Зв'язок з усіма діагнозами через візити
    diagnosis_ids = fields.Many2many('hr_hospital.diagnosis', string='Diagnosis History', compute='_compute_diagnoses')

    # Функція, яка збирає всі діагнози з усіх візитів пацієнта
    def _compute_diagnoses(self):
        for record in self:
            record.diagnosis_ids = record.visit_ids.mapped('diagnosis_ids')
