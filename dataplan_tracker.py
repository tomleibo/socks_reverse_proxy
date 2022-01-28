import socket
from typing import Dict

from dataclasses import dataclass
from infrastructure.wrappers.infra_logger import Logger

from database import Database
from super_proxy_plugin import SuperProxyPlugin

LOGGER_NAME = 'Dataplan_tracker'


class Collection:
    COLLECTION_NAME = "dataplanTracker"
    FIELD_AMOUNT = 'amount'
    FIELD_DIRECTION = 'direction'
    FIELD_DEVICE_ID = 'device_id'
    DIRECTION_DOWNLOAD = 'download'
    DIRECTION_UPLOAD = 'upload'


@dataclass
class Device:
    device_id: str
    download_socket: socket
    upload_socket: socket
    download_count: int
    upload_count: int

    def aggregate_packet_size(self, source_socket: socket, packet_size: int):
        if source_socket == self.download_socket:
            self.download_count += packet_size
        elif source_socket == self.upload_socket:
            self.upload_count += packet_size


class DataplanTracker(SuperProxyPlugin):
    """
    This class aggregates download and upload amounts and allows for later querying.
    e.g.:
    db.dataplanTracker.aggregate([
        {$group:
            {
                _id: {id: "$device_id", direction: "$direction"},
                total: { $sum: "$amount"}
            }
        }
    ])

    """
    def __init__(self, db: Database):
        self.db: Database = db
        self.socket_to_device: Dict[socket, Device] = {}
        self.logger = Logger(LOGGER_NAME)

    def register(self, yogurt_socket: socket, peer_socket: socket, peer_id: str):
        device: Device = Device(peer_id, yogurt_socket, peer_socket, 0, 0)
        self.socket_to_device[yogurt_socket] = device
        self.socket_to_device[peer_socket] = device

    def unregister(self, any_socket: socket):
        device = self.socket_to_device.get(any_socket)
        if not device:
            self.logger.error("unregister:: device was not found in socket_to_device dict")
            return
        self.logger.info(f"unregister:: updating dataplanTracker collection for {device.device_id}. "
                         f"Download = {device.download_count}. Upload = {device.upload_count}")
        self.db.insert_one(Collection.COLLECTION_NAME, {Collection.FIELD_DEVICE_ID: device.device_id, Collection.FIELD_DIRECTION: Collection.DIRECTION_DOWNLOAD,
                                                        Collection.FIELD_AMOUNT: device.download_count})
        self.db.insert_one(Collection.COLLECTION_NAME, {Collection.FIELD_DEVICE_ID: device.device_id, Collection.FIELD_DIRECTION: Collection.DIRECTION_UPLOAD,
                                                        Collection.FIELD_AMOUNT: device.upload_count})
        try:
            del self.socket_to_device[device.download_socket]
            del self.socket_to_device[device.upload_socket]
        except KeyError:
            self.logger.error("unregister:: socket was not in socket_to_device dict")

    def packet_transmitted(self, source: socket, _, data: bytes):
        device: Device = self.socket_to_device.get(source)
        if not device:
            self.logger.error("packet_transmitted:: device was not found in socket_to_device dict")
            return
        device.aggregate_packet_size(source, len(data))
