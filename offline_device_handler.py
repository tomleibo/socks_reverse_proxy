from collections import Counter
from typing import List, Dict
from infrastructure.wrappers.fcm import Fcm, FcmResponse
from infrastructure.wrappers.infra_logger import Logger
from infrastructure.wrappers.mongo import Mongo
from data_classes.available_asn import AVAILABLE_ASN_COLLECTION_NAME, COUNTRY_CODE
from data_classes.commands_sent import CommandsSent
from data_classes.device_details import DeviceDetails
from dataplan_tracker import Collection as dataplanTracker


class OfflineDeviceHandler:
    """
    DeviceHandler - Communicate with peer device.
    When the app is turn-on the it's send the device id, device fcm token, and app version.
    Using the fcm token and device id we can send silent push commands to communicate with the device.

    Currently supported:
    3- Pop app to front screen if the app is at the background.
    4- Disable device Wifi.
    5- Enable device Wifi.
    """
    WAKE_UP_COMMAND_ORDINAL = 1
    AIRPLANE_COMMAND = 2
    APP_TO_FRONT = 3
    DISABLE_WIFI = 4
    ENABLE_WIFI = 5

    def __init__(self, db: Mongo, fcm_wrapper: Fcm) -> None:
        self.db: Mongo = db
        self.fcm: Fcm = fcm_wrapper
        self.logger = Logger("OfflineDeviceHandler")

    def disable_wifi_by_imei(self, imei) -> bool:
        """
        Disable device wifi by device id.
        :param imei: device id.
        :return: True if wifi is disable else False.
        """
        self.logger.info("Disabling WIFI on IMEI = {0}".format(imei))
        return self._disable_wifi_with_filter({DeviceDetails.IMEI: imei})

    def disable_wifi_by_country(self, country_code) -> bool:
        """
        Disable device wifi by country code.
        :param country_code: country code.
        :return: True if wifi is disable else False.
        """
        self.logger.info("Disabling WIFI in: {0}".format(country_code))
        return self._disable_wifi_with_filter({DeviceDetails.COUNTRY_CODE: country_code})

    def enable_wifi_by_imei(self, imei) -> bool:
        """
        Enable device wifi by device id.
        :param imei: device id.
        :return: True if wifi is enable else False.
        """
        self.logger.info("Enabling WIFI on IMEI = {0}".format(imei))
        return self._enable_wifi_with_filter({DeviceDetails.IMEI: imei})

    def enable_wifi_by_country(self, country_code) -> bool:
        """
        Enable device wifi by country code.
        :param country_code: country code.
        :return: True if wifi is enable else False.
        """
        self.logger.info("Enabling WIFI in: {0}".format(country_code))
        return self._enable_wifi_with_filter({DeviceDetails.COUNTRY_CODE: country_code})

    def app_to_front_by_imei(self, imei) -> bool:
        """
        Pop app to front if the app is at the background by device id.
        :param imei: device id.
        :return: True if successes else False.
        """
        self.logger.info("Popping up app to front on IMEI = {0}".format(imei))
        return self._app_to_front_with_filter({DeviceDetails.IMEI: imei})

    def app_to_front_by_country(self, country_code) -> bool:
        """
        Pop app to front if the app is at the background by country code.
        :param country_code: country code.
        :return: True if successes else False.
        """
        self.logger.info("Popping up app to front in: {0}".format(country_code))
        return self._app_to_front_with_filter({DeviceDetails.COUNTRY_CODE: country_code})

    def wakeup_peers_by_country(self, country_code) -> bool:
        self.logger.info(f'Waking up devices in {country_code}')
        return self._wakeup_peers_with_filter({DeviceDetails.COUNTRY_CODE: country_code})

    def wakeup_peer_by_imei(self, imei) -> bool:
        self.logger.info(f'Waking up device with IMEI = {imei}')
        return self._wakeup_peers_with_filter({DeviceDetails.IMEI: imei})

    def generate_new_ip(self, imei):
        self.logger.info(f'Switching airplane mode on and off for device with IMEI = {imei}')
        fcm_tokens = self._get_only_fcm_tokens({DeviceDetails.IMEI: imei})
        return self._send_command(OfflineDeviceHandler.AIRPLANE_COMMAND, fcm_tokens)

    def count_available_devices_by_country(self) -> Dict[str, int]:
        all_devices = self.db.find(DeviceDetails.COLLECTION_NAME)
        country_count = Counter(map(lambda x: x[DeviceDetails.COUNTRY_CODE], all_devices))
        return country_count

    def db_data_by_country_code(self, country_codes: List[str] = None, collection_name: str = None,
                                filters: Dict[str, int] = None, distinct=False, imei=False):
        return self.db.find(collection_name, self._get_filter_doc(imei, country_codes), filters, distinct=distinct)

    def get_available_asns_per_country(self, country_codes: List[str] = None, distinct=False):
        return self.db.find(AVAILABLE_ASN_COLLECTION_NAME, self._get_filter_doc(country_codes=country_codes), {'_id': 0}, distinct=distinct)

    @staticmethod
    def _get_filter_doc(imei=None, country_codes=None):
        if country_codes:
            return {COUNTRY_CODE: {'$in': country_codes}}
        elif imei:
            return {dataplanTracker.FIELD_DEVICE_ID: {'$in': imei}}
        return {}

    @staticmethod
    def _build_command_dict_from_ordinal(ordinal: int) -> Dict:
        return {'command': ordinal}

    def _app_to_front_with_filter(self, filter_doc) -> bool:
        fcm_tokens = self._get_only_fcm_tokens(filter_doc)
        command_ordinal = OfflineDeviceHandler.APP_TO_FRONT
        return self._send_command(command_ordinal, fcm_tokens)

    def _disable_wifi_with_filter(self, filter_doc) -> bool:
        fcm_tokens = self._get_only_fcm_tokens(filter_doc)
        command_ordinal = OfflineDeviceHandler.DISABLE_WIFI
        return self._send_command(command_ordinal, fcm_tokens)

    def _enable_wifi_with_filter(self, filter_doc) -> bool:
        fcm_tokens = self._get_only_fcm_tokens(filter_doc)
        command_ordinal = OfflineDeviceHandler.ENABLE_WIFI
        return self._send_command(command_ordinal, fcm_tokens)

    def _wakeup_peers_with_filter(self, filter_doc) -> bool:
        fcm_tokens = self._get_only_fcm_tokens(filter_doc)
        command_ordinal = OfflineDeviceHandler.WAKE_UP_COMMAND_ORDINAL
        return self._send_command(command_ordinal, fcm_tokens)

    def _get_only_fcm_tokens(self, filter_doc):
        projection_doc = {DeviceDetails.FCM_ID: 1, DeviceDetails.ID: 0}
        fcm_json_list = self.db.find(DeviceDetails.COLLECTION_NAME, filter_doc, projection_doc)
        fcm_tokens: List[str] = list(map(lambda x: x[DeviceDetails.FCM_ID], fcm_json_list))
        return fcm_tokens

    def _send_command(self, command_ordinal, fcm_tokens) -> bool:
        if len(fcm_tokens) == 0:
            return False
        try:
            fcm_response: FcmResponse = self.fcm.silent_push(fcm_tokens,
                                                             self._build_command_dict_from_ordinal(command_ordinal))
            command_sent_object = CommandsSent.build_from_fcm_response(fcm_response, fcm_tokens, command_ordinal)
            self.db.insert_one(CommandsSent.COLLECTION_NAME, command_sent_object)
            self.logger.info(
                f'Push number {str(command_ordinal)} sent to {len(fcm_tokens)} and succeeded for {fcm_response.success} of them')
            return fcm_response.success > 0
        except Exception as e:
            self.logger.error(f"fcm push failed {e!r}")
            command_sent_object = CommandsSent(fcm_tokens, command_ordinal, 0, len(fcm_tokens))
            self.db.insert_one(CommandsSent.COLLECTION_NAME, command_sent_object)
            return False
