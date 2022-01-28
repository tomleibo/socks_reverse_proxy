import socket
import time
import unittest

import requests
from infrastructure.wrappers.mongo import Mongo

from connection_pool import ConnectionPool
from database import Database
from peer_server import PeerServer
from super_proxy import SuperProxy


class SuperProxyTests(unittest.TestCase):

    def setUp(self) -> None:
        self.port = 8555
        self.peer_port = 8000
        self.host = '127.0.0.1'
        self.mongo = Database("localhost", "test1")
        self.pool = ConnectionPool()
        self.super_proxy = SuperProxy({'GB': 1234, PeerServer.NOT_AVAILABLE: 5678}, self.pool, db=self.mongo)
        self.peer_server = PeerServer(self.mongo, self.peer_port, self.pool)
        self.peer_server.start()
        time.sleep(0.2)

    def tearDown(self) -> None:
        self.peer_server.stop()

    def test_communication_in_both_directions(self):
        # Connect peer to PeerServer
        peer_socket = socket.socket()
        country = PeerServer.NOT_AVAILABLE
        peer_socket.connect(('127.0.0.1', self.peer_port))
        string_to_send = '35362707123456413536270712345641,askhdgashdgashjdkhjkd'.encode()
        peer_socket.sendall(string_to_send)
        time.sleep(0.4)
        mapping = self.pool.count_connections_by_country()
        self.assertEqual(mapping[country], 1)

        # Send a string to the api socket and recv the same string on the peer socket
        client_socket = socket.socket()
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client_socket.connect(('127.0.0.1', 5678))
        string_to_send = "This Is A Test".encode()
        client_socket.sendall(string_to_send)
        string_received = peer_socket.recv(len(string_to_send))
        self.assertEqual(string_received, string_to_send)

        # Other way. First unregister sockets to recv the data here.
        string_to_send = 'Test 2'.encode()
        client_socket.setblocking(False)
        client_socket.settimeout(2)
        peer_socket.sendall(string_to_send)
        string_received = client_socket.recv(len(string_to_send))
        self.assertEqual(string_received, string_to_send)

    @staticmethod
    def _send_request(port, req_type, param, value):
        return requests.get('http://127.0.0.1:{0}/{1}?{2}={3}'.format(port, req_type, param, value))
