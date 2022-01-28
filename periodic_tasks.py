import time
from collections import defaultdict
from threading import Timer
from typing import Dict, List

from infrastructure.wrappers.infra_logger import Logger

from data_classes.available_asn import AVAILABLE_ASN_COLLECTION_NAME
from database import Database
from data_classes.device_details import DeviceDetails

HOUR_IN_SECONDS = 60 * 60
DAY_IN_SECONDS = HOUR_IN_SECONDS * 24


class PeriodicTasks:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.logger = Logger("Tasks")
        self.tasks = [CleanDeviceTask, GenerateAvailableAsnLists]

    def start(self):
        for task_init in self.tasks:
            task = task_init(self.db, self.logger)
            task.start()


class CleanDeviceTask(Timer):
    """
    Monitor and clean inactive devices.
    """
    TASK_INTERVAL_SECONDS = float(12 * HOUR_IN_SECONDS)
    DISCONNECTED_TIME_REMOVAL_THRESHOLD = 7 * DAY_IN_SECONDS

    def __init__(self, db: Database, logger: Logger) -> None:
        super().__init__(CleanDeviceTask.TASK_INTERVAL_SECONDS, self.clean_devices)
        self.db = db
        self.logger = logger

    def clean_devices(self):
        """
        Remove device that not communicate with backend more than X.
        """
        self.logger.info('Started clean devices task')
        try:
            devices_removed = self._testable_clean_devices()
            self.logger.info(f'CleanDevicesTask removed {devices_removed} devices '
                             f'that didn\'t connect for over {CleanDeviceTask.DISCONNECTED_TIME_REMOVAL_THRESHOLD} seconds')
        except Exception as e:
            self.logger.error(f'CleanDeviceTask failed because of {e!r}')

    def _testable_clean_devices(self) -> int:
        filter_doc = {DeviceDetails.LAST_CONNECT_TIMESTAMP: {"$lt": time.time() - CleanDeviceTask.DISCONNECTED_TIME_REMOVAL_THRESHOLD}}
        devices_removed = self.db.delete_many(DeviceDetails.COLLECTION_NAME, filter_doc)
        return devices_removed


class GenerateAvailableAsnLists(Timer):
    TASK_INTERVAL_SECONDS = float(HOUR_IN_SECONDS)

    def __init__(self, db: Database, logger: Logger) -> None:
        super().__init__(GenerateAvailableAsnLists.TASK_INTERVAL_SECONDS, self.refresh_asn_lists)
        self.db = db
        self.logger = logger

    def refresh_asn_lists(self):
        self.logger.info('Started refresh asn list task')
        country_to_asn_list: Dict[str, List[str]] = self._create_new_asn_list()
        document_list = self._transform_dictionary_to_document_list(country_to_asn_list)
        no_filter_query = {}
        self.db.delete_many(AVAILABLE_ASN_COLLECTION_NAME, no_filter_query)
        documents_inserted = self.db.insert_many(AVAILABLE_ASN_COLLECTION_NAME, document_list)
        if documents_inserted == len(country_to_asn_list):
            self.logger.info(f'GenerateAvailableAsnLists created new Asn list collection. containing {len(country_to_asn_list)} countries')
        else:
            self.logger.error(f'GenerateAvailableAsnLists failed to insert new asn lists')

    def _create_new_asn_list(self) -> Dict[str, List[str]]:
        country_to_asn_list: Dict[str, List[str]] = defaultdict(list)
        all_devices = self.db.find(DeviceDetails.COLLECTION_NAME)
        for device_dict in all_devices:
            device: DeviceDetails = DeviceDetails(**device_dict)
            country_to_asn_list[device.country_code].append(device.asn)
        return country_to_asn_list

    @staticmethod
    def _transform_dictionary_to_document_list(country_to_asn_list: Dict[str, List[str]]):
        return list(map(lambda x: {'country': x[0], 'asns': x[1]}, country_to_asn_list.items()))
