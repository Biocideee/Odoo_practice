import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # JS-фронтенд сюди запише посилання.
    checkbox_receipt_url = fields.Char(string="Посилання на чек Checkbox", readonly=True, copy=False)
