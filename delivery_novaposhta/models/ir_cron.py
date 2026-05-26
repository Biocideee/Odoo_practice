import logging

from odoo import fields, models
from odoo.exceptions import LockError, UserError

_logger = logging.getLogger(__name__)


class IrCronPlugit(models.Model):
    _inherit = "ir.cron"

    allow_async = fields.Boolean(default=False)

    def _try_lock(self):
        try:
            self.lock_for_update(allow_referencing=True)
        except LockError:
            raise UserError(
                self.env._(
                    "Record cannot be modified right now: "
                    "This cron task is currently being executed and may not be modified "
                    "Please try again in a few minutes"
                )
            ) from None

    def method_direct_trigger(self):
        self.ensure_one()
        self.browse().check_access("write")
        self._try_lock()
        _logger.info("Job %r (%s) started manually", self.name, self.id)
        self, _ = self.with_user(self.user_id).with_context(manually=True, lastcall=self.lastcall)._add_progress()  # noqa: PLW0642
        self.ir_actions_server_id.run()
        self.lastcall = fields.Datetime.now()
        self.env.flush_all()
        _logger.info("Job %r (%s) done", self.name, self.id)

        if self.allow_async:
            message = "Задача виконується в фоні"
        else:
            message = "Задача завершена"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": False,
                "message": message,
            },
        }
