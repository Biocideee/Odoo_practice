from odoo import http
from odoo.http import request


class TTNLableDownloadController(http.Controller):
    @http.route("/download/ttn-label/<int:record_id>", type="http", auth="user")
    def download_custom_file(self, record_id, **kwargs):
        page_format = kwargs.get("page_format", "A4")
        record = request.env["plugit.novaposhta_ttn"].browse(record_id).ensure_one()
        file_content = record.get_label(page_format)
        filename = f"A4_{record.ttn_number}.pdf"
        headers = [
            ("Content-Disposition", f'inline; filename="{filename}"'),
            ("Content-Type", "application/pdf"),  # Adjust the content type as needed
        ]
        return request.make_response(file_content, headers=headers)
