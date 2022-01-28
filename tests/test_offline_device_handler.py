import time
import unittest

from infrastructure.wrappers.fcm import Fcm

from data_classes.available_asn import AVAILABLE_ASN_COLLECTION_NAME, AvailableAsn, COUNTRY_CODE, ASNS
from data_classes.commands_sent import CommandsSent
from database import Database
from data_classes.device_details import DeviceDetails
from offline_device_handler import OfflineDeviceHandler

push_api_key = "AAAAxmVRCn8:APA91bGZePpz2m_uwtJeacLbDsV2-HLARvnha5S" \
               "-AsQDp2kKzBqjLIfaedHIgjuKGkPGFeF8iLkiJa1OVOKkgKkEUdFPfa" \
               "fmA76Vt9-t3888xqT2fsbwNx9ugLbTm5AlHFpm9Yyj57Eh"


class OfflineDeviceHandlerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.db = Database('127.0.0.1', 'test2')
        self.db.delete_many(DeviceDetails.COLLECTION_NAME, {})
        self.db.drop(CommandsSent.COLLECTION_NAME)
        self.db.drop(AVAILABLE_ASN_COLLECTION_NAME)
        self.handler = OfflineDeviceHandler(self.db, Fcm(push_api_key))
        self.countries = ['uk', 'us', 'fr', 'es', 'es', 'uk', 'us', 'es', 'us', 'us']

    def test_group_devices_by_country(self):
        for index, cc in enumerate(self.countries):
            self.db.insert_one(DeviceDetails.COLLECTION_NAME, DeviceDetails('_', '_', cc + str(index), cc, '1.1.1.1'))
        country_dict = self.handler.count_available_devices_by_country()
        self.assertEqual(country_dict['us'], 4)
        self.assertEqual(country_dict['es'], 3)
        self.assertEqual(country_dict['uk'], 2)
        self.assertEqual(country_dict['fr'], 1)

    def test_wakeup_device(self):
        imei = '123'
        self.db.insert_one(DeviceDetails.COLLECTION_NAME, DeviceDetails(imei, "fcm_id", '123', 'fr', '12.23.34.45'))
        timestamp = time.time()
        self.handler.wakeup_peer_by_imei(imei)
        one = self.db.find_one(CommandsSent.COLLECTION_NAME, {'fcm_ids': 'fcm_id'})
        self.assertLess(timestamp, one[CommandsSent.TIMESTAMP])

    def test_get_available_asns_per_country(self):
        us_asns = ['123', '1234']
        uk_asns = ['456', '4567']
        data = {'es': ['678'], 'us': us_asns, 'uk': uk_asns}
        for cc, asns in data.items():
            self.db.insert_one(AVAILABLE_ASN_COLLECTION_NAME, AvailableAsn(cc, asns))
        asns_per_country = self.handler.get_available_asns_per_country(['uk', 'us'])
        for asns in asns_per_country:
            if asns[COUNTRY_CODE] == 'us':
                self.assertEqual(asns[ASNS], us_asns)
            elif asns[COUNTRY_CODE] == 'uk':
                self.assertEqual(asns[ASNS], uk_asns)
            else:
                self.fail()
        asns_per_country = self.handler.get_available_asns_per_country()
        self.assertEqual(len(asns_per_country), 3)
