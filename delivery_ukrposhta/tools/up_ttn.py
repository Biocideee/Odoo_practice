import logging

from odoo.exceptions import UserError

from .exceptions import UkrposhtaAPIException
from .up_api import API

logger = logging.getLogger(__name__)

EXTERNAL_ID_PREFIX = "id-"

# Мапа простих полів-адреси: ключ — атрибут партнера, значення — поле у payload УП.
# Поле region береться через state_id.name окремо (бо це related-many2one).
ADDRESS_FIELDS_MAP = {
    "zip": "postcode",
    "ukrposhta_district": "district",
    "city": "city",
    "street": "street",
    "house_number": "houseNumber",
    "apart_number": "apartmentNumber",
}

# Опціональні UI-поля моделі TTN, які треба пробрасувати в API,
# якщо вони заповнені.
TTN_OPTIONAL_FLAGS = {
    "fragile": "fragile",
    "sms": "smsRecipient",
    "transfer_post_pay_to_bank_account": "transferPostPayToBankAccount",
}


class UkrposhtaConnector:
    """
    Бізнес-логіка обертів навколо REST API Укрпошти.

    Об'єкт створюється один раз для пари (api_key, token) і
    повторно використовується для всіх викликів у межах однієї дії.
    """

    def __init__(self, api_key, token, sandbox=False):
        self.api_key = api_key
        self.token = token
        self.sandbox = sandbox
        # Зберігає останній запит/відповідь, щоб carrier міг логувати їх
        # через self.log_xml(...) — для debug-режиму.
        self.last_request_payload = None
        self.last_response_payload = None

    def _api(self):
        return API(api_key=self.api_key, sandbox=self.sandbox)

    def _params(self, **extra):
        params = {"token": self.token}
        params.update(extra)
        return params

    # --- Адреси --------------------------------------------------------

    def create_address(self, data):
        return self._api().make_request(method="post", path="/addresses", params=self._params(), data=data)

    def get_address(self, address_id):
        return self._api().make_request(method="get", path=f"/addresses/{address_id}", params=self._params())

    def get_client_all_addresses(self, uuid):
        return self._api().make_request(
            method="get",
            path="/client-addresses",
            params=self._params(clientUuid=uuid),
        )

    # --- Клієнти -------------------------------------------------------

    def get_client(self, partner):
        external_id = f"{EXTERNAL_ID_PREFIX}{partner.id}"
        return self._api().make_request(
            method="get",
            path=f"/clients/external-id/{external_id}",
            params=self._params(),
        )

    def create_client(self, data):
        return self._api().make_request(method="post", path="/clients", params=self._params(), data=data)

    def edit_client(self, uuid, data):
        return self._api().make_request(method="put", path=f"/clients/{uuid}", params=self._params(), data=data)

    def client_address(self, client, partner):
        """
        Знайти серед адрес клієнта ту, що повністю відповідає партнерові.
        Повертає dict-адресу або None.

        У старій версії return стояв всередині внутрішнього циклу і виходив
        на першому ж збігу одного поля — невірно. Тут перевіряємо адреси
        повністю: тільки якщо ВСІ поля збіглися — повертаємо.
        """
        client_uuid = client.get("uuid") if isinstance(client, dict) else None
        if not client_uuid:
            return None
        all_addresses = self.get_client_all_addresses(uuid=client_uuid) or []
        partner_region = (partner.state_id and partner.state_id.name) or ""
        for entry in all_addresses:
            address = entry.get("address") or {}
            simple_match = all(
                (address.get(api_key) or "") == (getattr(partner, attr, "") or "")
                for attr, api_key in ADDRESS_FIELDS_MAP.items()
            )
            region_match = (address.get("region") or "") == partner_region
            if simple_match and region_match:
                return entry
        return None

    def _partner_address_payload(self, partner):
        return {
            "postcode": partner.zip or "",
            "country": "UA",
            "region": (partner.state_id and partner.state_id.name) or "",
            "city": partner.city or "",
            "district": getattr(partner, "ukrposhta_district", "") or "",
            "street": partner.street or "",
            "houseNumber": partner.house_number or "",
            "apartmentNumber": partner.apart_number or "",
        }

    def _build_client_payload(self, partner, address_id):
        if not partner.phone:
            raise UserError(f"Будь ласка, додайте номер телефона користувачу {partner.display_name}")

        external_id = f"{EXTERNAL_ID_PREFIX}{partner.id}"
        if partner.company_type == "company":
            return {
                "type": "COMPANY",
                "name": partner.commercial_company_name or partner.company_name or partner.name,
                "addressId": address_id,
                "phoneNumber": partner.phone,
                "email": partner.email or "",
                "edrpou": partner.company_registry or "",
                "externalId": external_id,
            }
        return {
            "type": "INDIVIDUAL",
            "name": f"{partner.contact_person_name or ''} {partner.contact_person_surname or ''}".strip()
            or partner.name,
            "firstName": partner.contact_person_name or "",
            "lastName": partner.contact_person_surname or "",
            "middleName": getattr(partner, "contact_middle_name", "") or "",
            "phoneNumber": partner.phone,
            "email": partner.email or "",
            "addressId": address_id,
            "externalId": external_id,
        }

    def get_or_create_client(self, partner):
        """
        Повертає dict-клієнта Укрпошти: або існуючого (за externalId), або щойно створеного.
        У випадку існуючого — якщо адреса партнера змінилася (немає такої серед client-addresses),
        додає її через edit_client.
        """
        client = None
        try:
            client = self.get_client(partner)
        except UkrposhtaAPIException as exc:
            # 404 = клієнта ще не існує — це нормально. Інші помилки — пробрасуємо.
            if exc.status_code != 404:
                raise
        except Exception:
            logger.exception("get_client failed for partner_id=%s", partner.id)
            client = None

        if client:
            existing_address = self.client_address(client, partner)
            if not existing_address:
                address_response = self.create_address(data=self._partner_address_payload(partner))
                self.edit_client(client["uuid"], data={"addressId": address_response["id"]})
                # Перечитати клієнта, щоб мати свіжий стан.
                client = self.get_client(partner)
            return client

        address_response = self.create_address(data=self._partner_address_payload(partner))
        client_data = self._build_client_payload(partner, address_response["id"])
        return self.create_client(client_data)

    # --- ТТН -----------------------------------------------------------

    @staticmethod
    def _kg_to_grams(weight_kg):
        """
        УП API оперує вагою у ГРАМАХ (integer), а Odoo зберігає у кг (float).
        Якщо ваги нема — повертаємо 0 (на боці create_ttn буде валідовано).
        Інакше — int(kg * 1000), щоб гарантувати ціле число для JSON-serialization.
        """
        return int(round((weight_kg or 0) * 1000))

    @staticmethod
    def _to_cm_int(value):
        """Габарити — теж integer (см)."""
        return int(round(value or 0))

    def _build_parcels_payload(self, parcels):
        """
        УП API чекає parcelNumber = 1, 2, 3... (наскрізна нумерація з 1).
        Odoo-шний sequence використовується лише для UI-сортування (drag-handle),
        у БД він зазвичай 10, 20, 30 за дефолтом — не підходить для API.
        Тому беремо порядковий номер через enumerate, але рядки впорядковуємо
        за sequence — щоб користувач міг змінювати порядок drag-handle'ом.

        Вага конвертується кг→грами, габарити — округлені см як integer.
        """
        payload = []
        sorted_parcels = parcels.sorted(key=lambda p: (p.sequence or 0, p.id))
        for idx, parcel in enumerate(sorted_parcels, start=1):
            payload.append({
                "parcelNumber": idx,
                "weight": self._kg_to_grams(parcel.weight),
                "length": self._to_cm_int(parcel.length),
                "width": self._to_cm_int(getattr(parcel, "width", 0)),
                "height": self._to_cm_int(parcel.height),
                "description": parcel.description or "",
                "declaredPrice": parcel.declared_price or 0,
            })
        return payload

    def _shipment_dimensions(self, parcels):
        """
        УП API на /shipments окрім списку parcels вимагає shipment-level
        weight, length, width, height — для обрахунку об'ємної ваги.
        Берем:
          * weight (грами) — сума ваги усіх парселів,
          * length/width/height (см) — максимальні значення.
        Усі числа — integer.
        """
        if not parcels:
            return {"weight": 0, "length": 0, "width": 0, "height": 0}
        total_weight_kg = sum((p.weight or 0) for p in parcels)
        return {
            "weight": self._kg_to_grams(total_weight_kg),
            "length": self._to_cm_int(max((p.length or 0) for p in parcels)),
            "width": self._to_cm_int(max((getattr(p, "width", 0) or 0) for p in parcels)),
            "height": self._to_cm_int(max((p.height or 0) for p in parcels)),
        }

    def create_ttn(self, sender_partner, ttn):
        """
        sender_partner — res.partner, відправник.
        ttn — recordset plugit.ukrposhta_ttn (одного запису), звідки беремо
        тип доставки, прапори, парсели та одержувача.
        """
        if not sender_partner:
            raise UserError("Не задано відправника для відправки Укрпоштою.")
        ttn.ensure_one()
        recipient_partner = ttn.stock_picking_id.partner_id
        if not recipient_partner:
            raise UserError("Не задано отримувача для відправки Укрпоштою.")

        sender = self.get_or_create_client(sender_partner)
        recipient = self.get_or_create_client(recipient_partner)
        parcels_payload = self._build_parcels_payload(ttn.parcel_ids)
        if not parcels_payload:
            raise UserError("Додайте принаймні одне місце (parcel) до ТТН.")

        # Нормалізація: API УП очікує enum-значення UPPERCASE (STANDARD, EXPRESS, ...).
        # Захист на випадок старих записів у БД зі значенням "Standard"/"Express".
        shipment_type = (ttn.type or "STANDARD").upper()
        delivery_type = (ttn.delivery_type or "W2W").upper()
        shipment_dims = self._shipment_dimensions(ttn.parcel_ids)
        data = {
            "sender": {"uuid": sender["uuid"]},
            "recipient": {"uuid": recipient["uuid"]},
            "deliveryType": delivery_type,
            "type": shipment_type,
            "paidByRecipient": bool(ttn.paid_by_recipient),
            "parcels": parcels_payload,
            # shipment-level габарити для розрахунку об'ємної ваги
            "weight": shipment_dims["weight"],
            "length": shipment_dims["length"],
            "width": shipment_dims["width"],
            "height": shipment_dims["height"],
        }
        if ttn.post_pay:
            data["postPay"] = float(ttn.post_pay)
        for field_name, api_key in TTN_OPTIONAL_FLAGS.items():
            value = getattr(ttn, field_name, False)
            if value:
                data[api_key] = bool(value)

        self.last_request_payload = data
        response = self._api().make_request(method="post", path="/shipments", params=self._params(), data=data)
        self.last_response_payload = response
        return response

    def check_ttn_status(self, ttn_uuid):
        return self._api().make_request(
            method="get",
            path=f"/shipments/{ttn_uuid}",
            params=self._params(),
        )

    def cancel_ttn(self, ttn_uuid):
        """
        Скасування ТТН в УП. Працює тільки якщо посилка ще не була відправлена
        фізично. Повертає dict-відповідь сервера (зазвичай — оновлений статус).
        """
        self.last_request_payload = {"action": "cancel", "uuid": ttn_uuid}
        response = self._api().make_request(
            method="delete",
            path=f"/shipments/{ttn_uuid}",
            params=self._params(),
        )
        self.last_response_payload = response
        return response

    def get_ttn_label_pdf(self, ttn_uuid, page_format="A4"):
        """
        Завантажити PDF-етикетку (Sticker) для ТТН.

        page_format:
          * "A4" — повноформатна сторінка A4 (стандарт)
          * "Z" — формат Zebra-стікера (термопринтер)

        Повертає bytes — вміст PDF-файлу. Бо це бінарний контент, не json.
        """
        import requests as _requests  # імпортуємо локально, щоб не дублювати з up_api
        api = self._api()
        url = api.create_link(f"/shipments/{ttn_uuid}/sticker", url_type="forms")
        params = self._params(format=page_format)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/pdf",
        }
        try:
            response = _requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
        except _requests.exceptions.RequestException as exc:
            logger.error("Ukrposhta PDF label download failed: %s", exc)
            raise UkrposhtaAPIException(
                message=f"Не вдалось завантажити PDF-етикетку: {exc}",
                status_code=getattr(getattr(exc, "response", None), "status_code", None),
            )
        return response.content
