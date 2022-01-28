import unittest

from infrastructure.wrappers.mongo import Mongo

from connection_pool import ConnectionPool
from data_classes.device_details import DeviceDetails
from peer_server import PeerServer


class DBTests(unittest.TestCase):

    def setUp(self) -> None:
        self.mongo = Mongo("localhost", "test1")
        self.pool = ConnectionPool()
        self.peer_port = 7000
        self.mongo.delete_many(DeviceDetails.COLLECTION_NAME, {})

    def test_geoip_db(self):
        peer = PeerServer(self.mongo, self.peer_port, ConnectionPool())
        res = peer._check_geoip_db([peer.ASN_DB_PATH, peer.CITY_DB_PATH, peer.COUNTRY_DB_PATH])
        self.assertTrue(res)
