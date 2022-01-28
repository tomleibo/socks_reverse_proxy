from infrastructure.wrappers.mongo import Mongo

from data_classes.device_details import DeviceDetails


class Database(Mongo):
    def __init__(self, host, db):
        super().__init__(host, db)
        self.create_index(DeviceDetails.COLLECTION_NAME, DeviceDetails.COUNTRY_CODE)
        self.create_index(DeviceDetails.COLLECTION_NAME, DeviceDetails.IMEI)
