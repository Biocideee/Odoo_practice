from odoo import models, fields, api


class AbstractPerson(models.AbstractModel):
    """
    This is a class which represents an abstract person and creates such common fields
    for all models who inherit this model as first_name, last_name, middle_name,
    phone_number, email, gender, date_of_birth.
    """
    _name = 'hr_hospital.abstract_person'
    _description = 'Abstract Person'
    _inherit = 'image.mixin'

    # ПІБ
    first_name = fields.Char(required=True)  # string parameter is not necessary
    last_name = fields.Char(required=True)
    middle_name = fields.Char()

    # Контакти
    phone_number = fields.Char(default="Не вказано", required=True)
    email = fields.Char()

    # Особисті дані
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], required=True)
    date_of_birth = fields.Date(required=True)

    # Громадянство
    country_id = fields.Many2one('res.country')

    # Поле для обчислення віку
    age = fields.Integer(compute='_compute_age', readonly=True, store=False, copy=False)

    @api.depends('date_of_birth')
    def _compute_age(self):
        for record in self:
            if record.date_of_birth:
                today = fields.Date.today()
                if today.strftime("%m%d") >= record.date_of_birth.strftime("%m%d"):
                    record.age = today.year - record.date_of_birth.year
                else:
                    record.age = today.year - record.date_of_birth.year - 1
            else:
                record.age = 0

    # Поле для обчислення повного імені
    full_name = fields.Char(store=True, compute='_compute_full_name')

    @api.depends('first_name', 'last_name', 'middle_name')
    def _compute_full_name(self):
        for record in self:
            parts = [record.last_name, record.first_name, record.middle_name]
            record.full_name = " ".join([part for part in parts if part])
