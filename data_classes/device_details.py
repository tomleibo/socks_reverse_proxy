import time


class DeviceDetails:

    ID = "_id"
    COLLECTION_NAME = 'DeviceDetails'
    IMEI = 'imei'
    FCM_ID = 'fcm_id'
    ASN = 'asn'
    COUNTRY_CODE = 'country_code'
    IP = 'ip'
    LAST_CONNECT_TIMESTAMP = 'last_connect_timestamp'
    APP_VERSION = 'app_version'

    def __init__(self, imei: str = None, fcm_id: str = None, asn: str = None, country_code: str = None, ip: str = None,
                 app_version: str = None, last_connect_timestamp: float = None, _id: str = None) -> None:
        self.imei = imei
        self.fcm_id = fcm_id
        self.asn = asn
        self.country_code = country_code
        self.ip = ip
        self.app_version = app_version
        if last_connect_timestamp is None:
            self.last_connect_timestamp = time.time()
        else:
            self.last_connect_timestamp = last_connect_timestamp
        if _id is not None:
            self._id = _id

    def __repr__(self) -> str:
        return f"DeviceDetails for {self.imei}"
