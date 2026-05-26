import json
import logging
import time

import requests
from requests import ReadTimeout
from requests.exceptions import HTTPError, RequestException

from odoo.addons.delivery_novaposhta.models.constants import API_URL

from .exceptions import NovaposhtaAPIException

logger = logging.getLogger(__name__)


class API:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = API_URL

    @property
    def session(self):
        if not hasattr(self, "_session"):
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "Content-Type": "application/json",
                }
            )
        return self._session

    def make_request(self, model_name, method, method_props=None):
        timeout = (30, 5)

        query = {
            "modelName": model_name,
            "calledMethod": method,
            "methodProperties": method_props or {},
            "apiKey": self.api_key,
        }
        attempts = 1
        while attempts <= 5:
            query_log = {key: value for key, value in query.items() if key != "apiKey"}
            try:
                response = self.session.post(self.base_url, json.dumps(query), timeout=timeout)
                response.raise_for_status()
            except HTTPError as exc:
                logger.error(
                    f"{exc.response.status_code}, {exc.response.text} while making API request: "
                    f"{json.dumps(query_log, indent=2, ensure_ascii=False)}"
                )
                raise NovaposhtaAPIException() from exc
            except (ConnectionError, TimeoutError, ReadTimeout) as exc:
                logger.error(f"Timeout exceeded while making API request: {json.dumps(query_log, indent=2, ensure_ascii=False)}")
                if attempts == 5:
                    raise NovaposhtaAPIException() from exc
                else:
                    logger.warning("waiting 3 seconds")
                    time.sleep(3)
                    logger.warning(f"Timeout (attempt #{attempts}): {repr(exc)}")
                    attempts += 1
                    continue
            except RuntimeError as exc:
                logger.error(
                    f"Caught an error while making API request, {repr(exc)}: {json.dumps(query_log, indent=2, ensure_ascii=False)}"
                )
                raise NovaposhtaAPIException() from exc
            except RequestException as exc:
                logger.error(
                    f"Unhandled exception {repr(exc)} while making API request: {json.dumps(query_log, indent=2, ensure_ascii=False)}"
                )
                raise NovaposhtaAPIException() from exc
            else:
                break

        content_type = response.headers["content-type"]
        if content_type == "application/json":
            response_data = response.json()
            errors = response_data.get("errors")
            if errors:
                errors = "\n".join(errors)
                logger.error(f'Request: method="{method}", props={method_props}, response={response_data}')

                raise NovaposhtaAPIException(errors)
        elif content_type == "application/pdf":
            response_data = response.content
        else:
            logger.error(f"Returned unsupported content type {content_type}")
            raise NovaposhtaAPIException()

        return response_data
