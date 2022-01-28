import time
import unittest
from datetime import datetime, timedelta
from logging import Logger

from data_classes.available_asn import AVAILABLE_ASN_COLLECTION_NAME
from database import Database
from data_classes.device_details import DeviceDetails
from periodic_tasks import CleanDeviceTask, GenerateAvailableAsnLists


class TaskTests(unittest.TestCase):

    def setUp(self) -> None:
        self.db = Database('127.0.0.1', 'test2')

    def test_clean_devices_tasks(self):
        logger = Logger("test")
        coll = DeviceDetails.COLLECTION_NAME
        self.db.delete_many(coll, {})
        two_weeks_ago = (datetime.now() - timedelta(days=14)).timestamp()
        self.db.insert_one(coll, DeviceDetails('123', '123', '123', 'us', '1.2.3.4', two_weeks_ago))
        self.db.insert_one(coll, DeviceDetails('123', '123', '123', 'us', '1.2.3.4', time.time()))
        self.db.insert_one(coll, DeviceDetails('123', '123', '123', 'us', '1.2.3.4', time.time()))
        devices_removed = CleanDeviceTask(self.db, logger)._testable_clean_devices()
        self.assertEqual(devices_removed, 1)
        devices_found = len(self.db.find(coll, {}))
        self.assertEqual(devices_found, 2)

    def test_generate_asn_list_task(self):
        logger = Logger("test")
        task: GenerateAvailableAsnLists = GenerateAvailableAsnLists(self.db, logger)
        coll = DeviceDetails.COLLECTION_NAME
        self.db.delete_many(coll, {})
        self.db.insert_one(coll, DeviceDetails('123', '123', '123', 'us', '1.2.3.4', time.time()))
        self.db.insert_one(coll, DeviceDetails('123', '123', '456', 'us', '1.2.3.4', time.time()))
        self.db.insert_one(coll, DeviceDetails('123', '123', '789', 'uk', '1.2.3.4', time.time()))
        task.refresh_asn_lists()
        asns = self.db.find(AVAILABLE_ASN_COLLECTION_NAME, {})
        for asn in asns:
            if asn['country'] == 'us':
                self.assertEqual(asn['asns'], ['123', '456'])
            elif asn['country'] == 'uk':
                self.assertEqual(asn['asns'], ['789'])
