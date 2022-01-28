import socket
import time
import unittest

from connection_pool import ConnectionPool
from database import Database
from data_classes.device_details import DeviceDetails
from peer_server import PeerServer


class PeerServerTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUpClass()
        self.port = 8000
        self.pool = ConnectionPool()
        self.s1 = socket.socket()
        self.s2 = socket.socket()
        self.db = Database('localhost', 'test1')
        self.db.delete_many(DeviceDetails.COLLECTION_NAME, {})
        self.server = PeerServer(self.db, self.port, self.pool)
        self.imei = '353627071234564'
        self.fcm_id = 'sdjfhsdjkfhsdjkfhdskjfhdskjfhsdjkf'
        self.bytes_to_send = str.encode(','.join([self.imei, self.fcm_id]))

    def tearDown(self) -> None:
        super().tearDownClass()
        self.s1.close()
        self.s2.close()
        self.server.stop()

    def test_handle_connections(self):
        self.server.start()
        time.sleep(0.2)
        self.s1.connect(('127.0.0.1', self.port))
        bytes_sent = self.s1.send(self.bytes_to_send)
        self.assertEqual(len(self.bytes_to_send), bytes_sent)
        time.sleep(0.1)

        one = self.db.find_one(DeviceDetails.COLLECTION_NAME, {DeviceDetails.IMEI: self.imei})
        self.assertIsNotNone(one)
        self.assertEqual(one[DeviceDetails.FCM_ID], self.fcm_id)

    def test_update_db(self):
        server = PeerServer(self.db, 7000, ConnectionPool())
        dd = DeviceDetails('000070000700007', 'abcdefg', '123', 'us', '1.2.3.4')
        update_result = server._update_db(dd)
        self.assertTrue(update_result)

    def test_two_connections(self):
        self.server.start()
        time.sleep(0.2)
        self.s1.connect(('127.0.0.1', self.port))
        self.s2.connect(('127.0.0.1', self.port))
        sent = self.s1.send(self.bytes_to_send)
        self.assertEqual(sent, len(self.bytes_to_send))
        sent2 = self.s2.send(self.bytes_to_send)
        self.assertEqual(sent2, len(self.bytes_to_send))
