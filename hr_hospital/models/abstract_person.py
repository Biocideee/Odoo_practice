from odoo import models, fields, api


class AbstractPerson(models.AbstractModel):
    _name = 'hr_hospital.abstract_person'
    _description = 'Person'
    _inherit = 'image.mixin'


# ПІБ
first_name = fields.Char(string='First Name', required=True)
last_name = fields.Char(string='Last Name', required=True)
middle_name = fields.Char(string='Middle Name')

# Контакти
phone_number = fields.Char(string='Phone Number')
email = fields.Char(string='Email Address')

# Особисті дані
gender = fields.Selection([('male', 'Male'), ('female', 'Female')], required=True)
date_of_birth = fields.Date(string='Date of Birth', required=True)

# Громадянство
country_id = fields.Many2one(comodel_name='res.country', string='Nationality')

# age = ..
# full_name = ..
#
