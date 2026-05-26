import logging

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from ..tools.up_ttn import UkrposhtaConnector

_logger = logging.getLogger(__name__)


class UkrposhtaLabelDownload(http.Controller):
    """
    Контролер для проксі-завантаження PDF-етикеток з УП.
    Без проксі браузер не зміг би передати Bearer-токен в URL.
    """

    @http.route(
        "/download/ukrposhta-label/<int:ttn_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def download_ukrposhta_label(self, ttn_id, page_format="A4", **kwargs):
        """
        Завантажити PDF-етикетку для ТТН Укрпошти.
        page_format=A4 (default) або Z (Zebra).
        """
        ttn = request.env["plugit.ukrposhta_ttn"].browse(ttn_id)
        if not ttn.exists():
            raise UserError("ТТН не знайдено.")
        if not ttn.ukrposhta_id:
            raise UserError("ТТН ще не зареєстрована в УП — нема UUID.")

        carrier = ttn.stock_picking_id.carrier_id
        if not carrier or carrier.delivery_type != "ukrposhta":
            raise UserError("Носій доставки не є Укрпоштою.")

        api_key, token, sandbox = carrier.sudo()._get_ukrposhta_credentials()
        if not api_key or not token:
            raise UserError("Не задано API ключ або token Укрпошти.")

        connector = UkrposhtaConnector(api_key, token, sandbox=sandbox)
        try:
            pdf_bytes = connector.get_ttn_label_pdf(ttn.ukrposhta_id, page_format=page_format)
        except Exception as exc:
            _logger.exception("Ukrposhta label download failed for ttn_id=%s", ttn_id)
            raise UserError(f"Не вдалось завантажити етикетку: {exc}")

        filename = f"ukrposhta-{ttn.ttn_number or ttn.ukrposhta_id}-{page_format}.pdf"
        return request.make_response(
            pdf_bytes,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", f'attachment; filename="{filename}"'),
                ("Content-Length", str(len(pdf_bytes))),
            ],
        )
