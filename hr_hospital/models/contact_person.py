from odoo import models, fields, api

class ContactPerson(models.Model):
    _name = 'hr_hospital.contact_person'
    _description = 'Contact Person'
    _inherit = 'hr_hospital.abstract_person'