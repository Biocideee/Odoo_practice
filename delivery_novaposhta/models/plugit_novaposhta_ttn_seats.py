from odoo import fields, models
from odoo.api import depends


class NovaposhtaTtnSeats(models.Model):
    _name = "plugit.novaposhta_ttn_seats"
    _description = "Місця в ТТН Нової Пошти"

    novaposhta_ttn_id = fields.Many2one("plugit.novaposhta_ttn", string="ТТН")
    sequence = fields.Integer(string="Номер місця")
    weight = fields.Float(string="Вага (кг)", required=True)
    width = fields.Float(string="Ширина (см)", required=True)
    length = fields.Float(string="Длина (см)", required=True)
    height = fields.Float(string="Висота (см)", required=True)
    volume = fields.Float(string="Об'ємна вага", compute="_compute_volume")
    description = fields.Char(string="Нотатки")

    @depends("width", "length", "height")
    def _compute_volume(self):
        for rec in self:
            rec.volume = (rec.width * rec.length * rec.height) / 4000
