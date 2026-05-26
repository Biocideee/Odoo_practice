import logging

import requests
from requests.exceptions import RequestException, HTTPError, Timeout, ConnectionError as RequestsConnectionError

from .exceptions import DeliveryAPIException, UkrposhtaAPIException

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # секунди — захист крон-задачі від зависання


class API:
    """
    HTTP-обгортка для REST API Укрпошти.

    Документація: https://dev.ukrposhta.ua/documentation/web-services/

    Авторизація в Укрпошти двокомпонентна:
      * `api_key` (Bearer-токен) — ідентифікує застосунок-інтегратора.
      * `token` — токен партнера, передається query-параметром.

    `token` додається на рівні UkrposhtaConnector у `params=`, тут лише
    Bearer-хедер, щоб не дублювати параметри авторизації.
    """

    APP_NAME = "ecom/0.0.1"
    BASE_API_URL = "https://www.ukrposhta.ua/"
    BASE_FORMS_URL = "https://www.ukrposhta.ua/forms/"
    SANDBOX_API_URL = "https://dev.ukrposhta.ua/"
    SANDBOX_FORMS_URL = "https://dev.ukrposhta.ua/forms/"

    def __init__(self, api_key, sandbox=False):
        self.api_key = api_key
        self.sandbox = sandbox

    def _api_root(self):
        return self.SANDBOX_API_URL if self.sandbox else self.BASE_API_URL

    def _forms_root(self):
        return self.SANDBOX_FORMS_URL if self.sandbox else self.BASE_FORMS_URL

    def create_link(self, path, url_type="api"):
        root = self._api_root() if url_type == "api" else self._forms_root()
        # APP_NAME без додаткового слешу — за документацією шлях — наприклад
        # https://www.ukrposhta.ua/ecom/0.0.1/clients
        return f"{root}{self.APP_NAME}{path}"

    def make_request(self, method, path, params=None, data=None, url_type="api"):
        data = data or {}
        params = params or {}
        url = self.create_link(path, url_type)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            response = requests.request(
                method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except Timeout as exc:
            logger.error("Timeout calling Ukrposhta %s %s: %s", method, url, exc)
            raise DeliveryAPIException(f"Ukrposhta timeout: {exc}") from exc
        except RequestsConnectionError as exc:
            logger.error("Connection error calling Ukrposhta %s %s: %s", method, url, exc)
            raise DeliveryAPIException(f"Ukrposhta connection error: {exc}") from exc
        except RequestException as exc:
            logger.error("Request error calling Ukrposhta %s %s: %s", method, url, exc)
            raise DeliveryAPIException(f"Ukrposhta request error: {exc}") from exc

        if response.status_code >= 400:
            payload = None
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            logger.error(
                "Ukrposhta API error %s on %s %s: %s",
                response.status_code, method, url, payload,
            )
            message = self._extract_error_message(payload) or response.reason or "Unknown error"
            raise UkrposhtaAPIException(
                message=message,
                status_code=response.status_code,
                payload=payload,
            )

        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def _extract_error_message(payload):
        """Витягнути зрозумілий текст помилки з відповіді сервера."""
        if isinstance(payload, dict):
            for key in ("message", "errorMessage", "error", "description", "detail"):
                if payload.get(key):
                    return str(payload[key])
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                return API._extract_error_message(first)
            return str(first)
        if isinstance(payload, str):
            return payload
        return None
