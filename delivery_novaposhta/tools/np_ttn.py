import logging
from datetime import datetime

import phonenumbers

from odoo.addons.delivery_novaposhta.models.res_partner import TargetTypes
from odoo.addons.delivery_novaposhta.tools.np_api import API

logger = logging.getLogger(__name__)


class NovaposhtaConnector:
    api = None

    def __init__(self, api_key):
        self.api = API(api_key)
        self.options = None
        self.sender = None

    def create_counterparty_address(self, partner_id):
        props = {
            "SettlementRef": partner_id.np_settlement_id.ref,
            "ContactPersonRef": partner_id.np_contact_person_ref,
        }

        if partner_id.np_target_type == TargetTypes.courier:
            additional_props = {
                "AddressRef": partner_id.np_street_id.ref,
                "BuildingNumber": partner_id.house_number,
                "Flat": partner_id.apart_number or "",
                "AddressType": "Doors",
            }
        else:
            additional_props = {"AddressRef": partner_id.np_warehouse_id.ref, "AddressType": "Warehouse"}

        props.update(additional_props)

        response = self.api.make_request(
            model_name="AddressContactPersonGeneral",
            method="save",
            method_props=props,
        )
        return response["data"][0]

    def get_counterparty(self, counterparty_property="Sender"):
        response = self.api.make_request(
            model_name="Counterparty",
            method="getCounterparties",
            method_props={
                "CounterpartyProperty": counterparty_property,
            },
        )
        return response["data"]

    def get_counterparty_all_addresses(self, partner_id):
        response = self.api.make_request(
            model_name="CounterpartyGeneral",
            method="getCounterpartyAddresses",
            method_props={"Ref": partner_id.np_counterparty_ref, "CounterpartyProperty": "Sender"},
        )
        return response

    def _partner_is_private(self, partner_id):
        return not partner_id.parent_id.is_company

    def create_counterparty(self, partner_id):
        counterparty_type = "Recipient"
        if self._partner_is_private(partner_id):
            response = self.api.make_request(
                model_name="Counterparty",
                method="save",
                method_props={
                    "FirstName": partner_id.contact_person_name,
                    "MiddleName": partner_id.contact_middle_name,
                    "LastName": partner_id.contact_person_surname,
                    "Phone": partner_id.phone,
                    "Email": partner_id.email or "",
                    "CounterpartyType": "PrivatePerson",
                    "CounterpartyProperty": counterparty_type,
                },
            )
            return response["data"][0]
        else:
            response = self.api.make_request(
                model_name="Counterparty",
                method="save",
                method_props={
                    "CounterpartyType": "Organization",
                    "CounterpartyProperty": counterparty_type,
                    "EDRPOU": partner_id.parent_id.company_registry,
                },
            )

            data = response["data"][0]
            partner_id.np_counterparty_ref = data["Ref"]
            return data

    def get_or_create_contact_person(self, partner_id, counterparty_type: str):
        partner_phone_formatted = phonenumbers.parse(partner_id.phone, "UA").national_number
        contact_list = self.get_counterparty_contact_persons(partner_id, counterparty_type)
        for contact in contact_list:
            contact_phone = contact["Phones"]
            contact_phone_formatted = phonenumbers.parse(contact_phone, "UA").national_number
            if (
                contact["FirstName"] == partner_id.contact_person_name
                and contact["LastName"] == partner_id.contact_person_surname
                and contact_phone_formatted == partner_phone_formatted
            ):
                return contact
        else:
            return self.create_contact_person(partner_id)

    def get_counterparty_contact_persons(self, partner_id, counterparty_type: str):
        response = self.api.make_request(
            model_name="ContactPersonGeneral",
            method="getContactPersonsList",
            method_props={
                "CounterpartyRef": partner_id.np_counterparty_ref,
                "CounterpartyProperty": counterparty_type,
            },
        )
        return response["data"]

    def create_contact_person(self, partner_id):
        response = self.api.make_request(
            model_name="ContactPersonGeneral",
            method="save",
            method_props={
                "CounterpartyRef": partner_id.np_counterparty_ref,
                "FirstName": partner_id.contact_person_name,
                "LastName": partner_id.contact_person_surname,
                "MiddleName": partner_id.contact_middle_name,
                "Phone": partner_id.phone,
            },
        )
        return response["data"][0]

    def update_sender_counterparty_data(self, sender_id):
        if not sender_id.np_counterparty_ref:
            sender_id.np_counterparty_ref = sender_id.carrier_id.novaposhta_sender_ref

        if not sender_id.np_contact_person_ref:
            if sender_id.carrier_id.novaposhta_sender_type == "PrivatePerson":
                contact_data = self.get_counterparty_contact_persons(sender_id, "Sender")[0]
                sender_id.np_contact_person_ref = contact_data["Ref"]
            else:
                contact_data = self.get_or_create_contact_person(sender_id, "Sender")
                sender_id.np_contact_person_ref = contact_data["Ref"]

        if not sender_id.np_address_ref:
            address_data = self.create_counterparty_address(sender_id)
            sender_id.np_address_ref = address_data["Ref"]

    def update_recipient_counterparty_data(self, partner_id):
        if not partner_id.np_counterparty_ref:
            if self._partner_is_private(partner_id):
                partner_id.np_counterparty_ref = partner_id.carrier_id.novaposhta_private_recipient_ref
            else:
                counterparty_data = self.create_counterparty(partner_id)
                partner_id.np_counterparty_ref = counterparty_data["Ref"]

        if not partner_id.np_contact_person_ref:
            contact_data = self.get_or_create_contact_person(partner_id, "Recipient")
            partner_id.np_contact_person_ref = contact_data["Ref"]

        if not partner_id.np_address_ref:
            address_data = self.create_counterparty_address(partner_id)
            partner_id.np_address_ref = address_data["Ref"]

    def ensure_options(self):
        if not self.options:
            response = self.api.make_request(
                model_name="Counterparty",
                method="getCounterpartyOptions",
                method_props={
                    "Ref": self.sender.np_counterparty_ref,
                },
            )
            self.options = response["data"][0]

    @property
    def can_afterpayment_on_goods_cost(self):
        self.ensure_options()
        return self.options.get("CanAfterpaymentOnGoodsCost")

    def create_ttn(self, stock_picking):
        ttn = stock_picking.np_ttn_id
        self.sender = ttn.sender_id
        self.update_sender_counterparty_data(ttn.sender_id)

        self.update_recipient_counterparty_data(ttn.partner_id)

        delivery_date = ttn.delivery_date if ttn.delivery_date else datetime.today()
        delivery_date_str = datetime.strftime(delivery_date, "%d.%m.%Y")
        seats = ttn.seat_ids
        seats_data = []
        weight = str(sum([seat.weight for seat in seats]))
        for seat in seats:
            seat = {
                "volumetricVolume": str(seat.volume),
                "volumetricWidth": str(seat.width),
                "volumetricLength": str(seat.length),
                "volumetricHeight": str(seat.height),
                "weight": str(seat.weight),
            }
            seats_data.append(seat)

        data = {
            "PayerType": ttn.novaposhta_payment_side,
            "PaymentMethod": ttn.novaposhta_payment_type,
            "DateTime": delivery_date_str,
            "CargoType": "Parcel",
            "Weight": weight,
            "ServiceType": ttn.service_type,
            "SeatsAmount": len(ttn.seat_ids),
            "Description": ttn.description,
            "Cost": ttn.cost,
            "OptionsSeat": seats_data,
            "Sender": ttn.sender_id.np_counterparty_ref,
            "CitySender": ttn.sender_id.np_settlement_id.ref,
            "SenderAddress": ttn.sender_id.np_address_ref,
            "ContactSender": ttn.sender_id.np_contact_person_ref,
            "SendersPhone": ttn.sender_id.phone,
            "Recipient": ttn.partner_id.np_counterparty_ref,
            "CityRecipient": ttn.partner_id.np_settlement_id.ref,
            "RecipientAddress": ttn.partner_id.np_address_ref,
            "ContactRecipient": ttn.partner_id.np_contact_person_ref,
            "RecipientsPhone": ttn.partner_id.phone,
        }
        if ttn.back_payment:
            if self.can_afterpayment_on_goods_cost:
                data["AfterpaymentOnGoodsCost"] = str(ttn.cost)
            else:
                data["BackwardDeliveryData"] = [
                    {
                        "PayerType": "Recipient",
                        "CargoType": "Money",
                        "RedeliveryString": ttn.cost,
                    }
                ]

        response = self.api.make_request(model_name="InternetDocument", method="save", method_props=data)
        return response["data"][0]

    def track_ttn(self, docs):
        response = self.api.make_request(
            model_name="TrackingDocumentGeneral",
            method="getStatusDocuments",
            method_props={"Documents": [{"DocumentNumber": ttn_number, "Phone": phone} for ttn_number, phone in docs]},
        )
        return response

    def get_ttn_print(self, ttn_list: list[str], page_format: str):
        """
        print_type in "Marking_100x100", "A4"
        """
        props = {
            "DocumentRefs": ttn_list,
            "Type": "pdf",
        }
        if page_format == "A4":
            props.update(
                {
                    "printForm": "Document_new",
                    "Position": 1,
                    "Copies": 1,
                    "PageFormat": "A4",
                }
            )
        else:
            props.update({"printForm": "Marking_100x100", "Position": ""})

        response = self.api.make_request(model_name="InternetDocument", method="printFull", method_props=props)
        return response
