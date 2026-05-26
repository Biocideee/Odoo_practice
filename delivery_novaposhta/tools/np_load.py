import logging
import time

from odoo import models

from ..models.constants import NOVAPOSHTA
from .np_api import API

logger = logging.getLogger(__name__)


class NPLoader:
    """
    Get data from Novaposhta API and save it to the DB
    """

    env = None
    api = None

    def run(self, env, with_raise=False):
        self.env = env(su=True)
        delivery_carrier = self.env["delivery.carrier"].search([("delivery_type", "=", NOVAPOSHTA)], limit=1)
        if delivery_carrier is None:
            message = "Не знайдено відповідний спосіб доставки. Створіть спосіб доставки з типом Нова пошта"
            logging.warning(message)
            if with_raise:
                raise Exception(message)
            return False
        api_key = delivery_carrier.get_np_api_key()
        if not api_key:
            message = "Не заданий API ключ. Введіть ключ в формі відповідного способу доставки"
            logging.warning(message)
            if with_raise:
                raise Exception(message)
            return False
        self.api = API(api_key)
        try:
            self.load_all()
        except Exception as e:
            if with_raise:
                raise Exception("Помилка під час завантаження") from e

    def _filter_changes(self, record, values):
        filtered_values = {}
        for field_name, value in values.items():
            existing_value = getattr(record, field_name)
            if isinstance(existing_value, models.Model):
                existing_value = existing_value.id
            if existing_value != value:
                filtered_values[field_name] = value
        return filtered_values

    @staticmethod
    def status_info(update_info, create_info, record_type):
        logger.info(f"Updated {update_info} {record_type}")
        logger.info(f"Created {create_info} {record_type}")

    def load_settlement_types(self):
        data_to_create = []
        updated_records = 0
        record_type = "settlement types"

        response = self.api.make_request(model_name="Address", method="getSettlementTypes")
        settlement_type_db_dict = {record.ref: record for record in self.env["plugit.np_settlement_type"].search([])}

        for record_api in response["data"]:
            record_values = {"ref": record_api["Ref"], "name": record_api["Description"], "short_name": record_api["Code"]}
            record_db = settlement_type_db_dict.get(record_api["Ref"])
            if record_db:
                write_values = self._filter_changes(record_db, record_values)
                if write_values:
                    record_db.write(write_values)
                    updated_records += 1
            else:
                data_to_create.append(record_values)

        self.env["plugit.np_settlement_type"].create(data_to_create)

        self.status_info(updated_records, len(data_to_create), record_type)

    def load_warehouse_types(self):
        """This method loads all types of warehouses from NP API to DB
        If record is in the DB - record will be updated
        If record isn't in the DB - record will be created"""

        data_to_create = []
        updated_records = 0
        record_type = "warehouse types"

        response = self.api.make_request(model_name="Address", method="getWarehouseTypes")
        warehouse_type_db_dict = {record.ref: record for record in self.env["plugit.np_warehouse_type"].search([])}

        for record_api in response["data"]:
            np_target_type = False
            if "поштове" in record_api["Description"].lower() or "вантажне" in record_api["Description"].lower():
                np_target_type = "warehouse"
            elif "поштомат" in record_api["Description"].lower():
                np_target_type = "poshtomat"
            record_values = {"ref": record_api["Ref"], "name": record_api["Description"], "np_target_type": np_target_type}
            record_db = warehouse_type_db_dict.get(record_api["Ref"])
            if record_db:
                write_values = self._filter_changes(record_db, record_values)
                if write_values:
                    record_db.write(write_values)
                    updated_records += 1
            else:
                if record_api["Description"] != "Parcel Shop":
                    data_to_create.append(record_values)

        self.env["plugit.np_warehouse_type"].create(data_to_create)

        self.status_info(updated_records, len(data_to_create), record_type)

    def load_areas(self):
        """This method loads all areas from NP API to DB
        If record is in the DB - record will be updated
        If record isn't in the DB - record will be created"""

        data_to_create = []
        updated_records = 0
        record_type = "areas"

        areas_db_dict = {record.ref: record for record in self.env["plugit.np_area"].search([])}

        response = self.api.make_request(model_name="Address", method="getSettlementAreas")

        for record_api in response["data"]:
            record_values = {"ref": record_api["Ref"], "name": record_api["Description"], "type": record_api["RegionType"]}
            record_db = areas_db_dict.get(record_api["Ref"])
            if record_db:
                write_values = self._filter_changes(record_db, record_values)
                if write_values:
                    record_db.write(write_values)
                    updated_records += 1
            else:
                data_to_create.append(record_values)

        self.env["plugit.np_area"].create(data_to_create)

        self.status_info(updated_records, len(data_to_create), record_type)

    def load_regions(self):
        """This method loads all area's regions from NP API to DB
        If record is in the DB - record will be updated
        If record isn't in the DB - record will be created"""

        data_to_create = []
        updated_records = 0
        record_type = "regions"

        regions_db_dict = {record.ref: record for record in self.env["plugit.np_region"].search([])}
        areas_db_dict = {record.ref: record for record in self.env["plugit.np_area"].search([])}
        areas_ref_set = {ref for ref in areas_db_dict}

        for area_ref in areas_ref_set:
            response = self.api.make_request(model_name="Address", method="getSettlementCountryRegion", method_props={"AreaRef": area_ref})

            for record_api in response["data"]:
                record_db = regions_db_dict.get(record_api["Ref"])
                area_id = areas_db_dict.get(area_ref, False)
                record_values = {
                    "ref": record_api["Ref"],
                    "name": record_api["Description"],
                    "type": record_api["RegionType"],
                    "area_id": area_id.id,
                }

                if record_db:
                    write_values = self._filter_changes(record_db, record_values)
                    if write_values:
                        record_db.write(write_values)
                        updated_records += 1
                else:
                    data_to_create.append(record_values)

        self.env["plugit.np_region"].create(data_to_create)

        self.status_info(updated_records, len(data_to_create), record_type)

    def load_streets(self):
        """This method loads all company streets from NP API to DB
        If record is in the DB - record will be updated
        If record isn't in the DB - record will be created"""

        data_to_create = []
        updated_records = 0
        record_type = "streets"

        street_db_dict = {record.ref: record for record in self.env["plugit.np_street"].search([])}
        settlements_db_dict = {record.ref: record.id for record in self.env["plugit.np_settlement"].search([])}
        total_settlements = len(settlements_db_dict)

        for settlement_num, (settlement_ref, settlement_id) in enumerate(settlements_db_dict.items(), 1):
            page_counter = 1
            while True:
                response = self.api.make_request(
                    model_name="Address",
                    method="getSettlementStreets",
                    method_props={"Page": str(page_counter), "Limit": "500", "SettlementRef": settlement_ref},
                )
                if not response["data"]:
                    break
                else:
                    for record_api in response["data"]:
                        try:
                            record_values = {
                                "ref": record_api["Ref"],
                                "name": record_api["Present"],
                                "name_ru": record_api["DescriptionRu"],
                                "np_settlement_id": settlement_id,
                            }
                            record_db = street_db_dict.get(record_api["Ref"])
                            if record_db:
                                write_values = self._filter_changes(record_db, record_values)
                                if write_values:
                                    record_db.write(write_values)
                                    updated_records += 1
                            else:
                                data_to_create.append(record_values)
                        except Exception:
                            logger.exception("Exception while loading street")
                    logger.info(f"{page_counter} pages of streets were loaded for {settlement_num} settlement from {total_settlements}")
                    page_counter += 1
            time.sleep(0.2)
        self.env["plugit.np_street"].create(data_to_create)
        self.status_info(updated_records, len(data_to_create), record_type)

    def load_settlements(self):
        """This method loads all settlements from NP API to DB
        If record is in the DB - record will be updated
        If record isn't in the DB - record will be created"""

        data_to_create = []
        updated_records = 0
        page_counter = 1
        record_type = "settlements"

        settlements_db_dict = {record.ref: record for record in self.env["plugit.np_settlement"].search([])}
        regions_db_dict = {record.ref: record.id for record in self.env["plugit.np_region"].search([])}
        areas_db_dict = {record.ref: record.id for record in self.env["plugit.np_area"].search([])}
        settlement_types_db_dict = {record.ref: record.id for record in self.env["plugit.np_settlement_type"].search([])}

        while True:
            response = self.api.make_request(
                model_name="Address", method="getSettlements", method_props={"Page": str(page_counter), "Limit": "500"}
            )
            if not response["data"]:
                break
            else:
                for record_api in response["data"]:
                    area_id = areas_db_dict.get(record_api["Area"], False)
                    region_id = regions_db_dict.get(record_api["Region"], False)
                    settlement_type_id = settlement_types_db_dict.get(record_api["SettlementType"], False)
                    try:
                        record_values = {
                            "ref": record_api["Ref"],
                            "name": record_api["Description"],
                            "name_ru": record_api["DescriptionRu"],
                            "settlement_type_id": settlement_type_id,
                            "area_id": area_id,
                            "region_id": region_id,
                        }
                        record_db = settlements_db_dict.get(record_api["Ref"])
                        if record_db:
                            write_values = self._filter_changes(record_db, record_values)
                            if write_values:
                                record_db.write(write_values)
                                updated_records += 1
                        else:
                            data_to_create.append(record_values)
                    except Exception:
                        logger.error("Exception while loading settlements")
                logger.info(f"{page_counter} pages of settlements loaded")
                page_counter += 1
            time.sleep(0.5)

        self.env["plugit.np_settlement"].create(data_to_create)
        self.status_info(updated_records, len(data_to_create), record_type)

    def load_warehouses(self):
        """This method loads all warehouses from NP API to DB
        If record is in the DB - record will be updated
        If record isn't in the DB - record will be created"""

        created_records = 0
        updated_records = 0
        record_type = "warehouses"

        warehouses_db_dict = {record.ref: record for record in self.env["plugit.np_warehouse"].search([])}
        warehouse_type_db_dict = {record.ref: record.id for record in self.env["plugit.np_warehouse_type"].search([])}
        settlements_db_dict = {record.ref: record.id for record in self.env["plugit.np_settlement"].search([])}
        types_ref_set = {i for i in warehouse_type_db_dict}

        for type_ref in types_ref_set:
            page_counter = 1
            while True:
                response = self.api.make_request(
                    model_name="Address",
                    method="getWarehouses",
                    method_props={"Page": str(page_counter), "Limit": "500", "TypeOfWarehouseRef": type_ref},
                )
                if not response["data"]:
                    break
                else:
                    for record_api in response["data"]:
                        record_db = warehouses_db_dict.get(record_api["Ref"])
                        warehouse_type_id = warehouse_type_db_dict.get(record_api["TypeOfWarehouse"], False)

                        settlement_id = settlements_db_dict.get(record_api["SettlementRef"], False)
                        record_values = {}
                        try:
                            for remote_field, local_field in self.env["plugit.np_warehouse"].fields_mapping.items():
                                if remote_field == "TypeOfWarehouse":
                                    record_values["type_id"] = warehouse_type_id
                                elif remote_field == "SettlementId":
                                    record_values["settlement_id"] = settlement_id
                                elif remote_field == "DenyToSelect":
                                    record_values["deny_to_select"] = record_api["DenyToSelect"] == "1"
                                else:
                                    record_values[local_field] = record_api[remote_field]

                        except KeyError as exc:
                            logger.error(repr(exc))

                        if record_db:
                            write_values = self._filter_changes(record_db, record_values)
                            if write_values:
                                record_db.write(write_values)
                                updated_records += 1
                        else:
                            new = self.env["plugit.np_warehouse"].create(record_values)
                            warehouses_db_dict[new.ref] = new
                            created_records += 1
                    logger.info(f"{page_counter} pages of warehouses type {warehouse_type_db_dict[type_ref]} loaded")
                    page_counter += 1
                    time.sleep(3)
            time.sleep(5)

        self.status_info(updated_records, created_records, record_type)

    def load_all(self):
        """This method loads all areas, regions, company cities, company streets, warehouses types,
        settlements and warehouses from NP API to DB"""

        try:
            self.load_areas()
            self.env.cr.commit()

            self.load_regions()
            self.env.cr.commit()

            self.load_settlement_types()
            self.env.cr.commit()

            self.load_settlements()
            self.env.cr.commit()
            self.load_streets()
            self.load_warehouse_types()
            self.env.cr.commit()

            self.load_warehouses()
        except Exception:
            logging.exception("error in NP loading")
            raise
        finally:
            self.env.cr.commit()
