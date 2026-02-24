from odoo import fields, models


class Desease(models.Model):
    _name = 'hr_hospital.disease'
    _description = 'Disease'

    # Батьківська хвороба
    parental_disease_id = fields.Many2one('hr_hospital.disease', string='Parental Disease')

    # Дочірня хвороба
    child_disease_ids = fields.One2many('hr_hospital.disease', string='Child Disease')

    # Код МКХ-10
    ICD_10_code = fields.Char(string='ICD 10', size=10)

    # Ступінь небезпеки
    degree_of_danger = fields.Selection([('mild', 'Mild'),
                                         ('moderate', 'Moderate'),
                                         ('high', 'High'),
                                         ('critical', 'Critical')])

    # Заразна
    is_infectious = fields.Boolean(string='Is infectious')

    # Симптоми
    symptoms = fields.Text(string='Symptoms')

    # Регіон поширення
    destribution_region_ids = fields.Many2many('res.country', string='Destribution Regions')
