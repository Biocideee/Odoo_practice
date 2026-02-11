from odoo import fields, models, api

class Patient(models.Model):
    _name = 'hr.hospital.patient'
    _description = 'Patient'
    _inherit = 'hr.hospital.abstract.person'

