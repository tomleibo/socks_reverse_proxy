import socket
import time
import unittest
from threading import Thread

from connection_pool import ConnectionPool
from data_classes.connection import Connection
from utils.no_available_connection_exception import NoAvailableConnection
from utils.unstable_echo_server import UnstableEchoServer


class ConnPoolTests(unittest.TestCase):

    def setUp(self) -> None:
        super().setUpClass()
        self.pool = ConnectionPool()
        self.s1 = socket.socket()
        self.s2 = socket.socket()
        self.s3 = socket.socket()
        self.s4 = socket.socket()
        self.con1 = Connection(self.s1, 'us', '1234', '1234')
        self.con2 = Connection(self.s2, 'us', '12345', '12345')
        self.con3 = Connection(self.s3, 'uk', '345', '345')
        self.con4 = Connection(self.s4, 'us', '789', '789')

    def tearDown(self) -> None:
        super().tearDownClass()
        self.s1.close()
        self.s2.close()
        self.s3.close()
        self.s4.close()

    def test_pop_and_insert(self):
        self.pool.insert(self.con1)
        self.pool.insert(self.con2)
        self.pool.insert(self.con3)
        self.pool.insert(self.con4)
        conn = self.pool.pop_connection_by_country("uk")
        self.assertEqual(conn.asn, '345')
        try:
            self.pool.pop_connection_by_country('uk')
            self.assertTrue(False)
        except NoAvailableConnection:
            pass
        conn = self.pool.pop_connection_by_country_and_asn('us', '1234')
        self.assertEqual(conn.asn, '1234')
        self.assertRaises(NoAvailableConnection, self.pool.pop_connection_by_country_and_asn, 'us', '1234')
        self.assertEqual(2, len(self.pool.used_connections))

    def test_send_keep_alive_packet(self):
        host = '127.0.0.1'
        port = 2000
        # socket should fail sending before its open
        alive = self.pool._send_keep_alive_packet_and_check_response(self.s1)
        self.assertFalse(alive)
        run_echo_server(host, port)
        self.s1.connect((host, port))
        self.s1.settimeout(1)
        # first packet should not be sent, therefore no keep alive is sent back
        alive = self.pool._send_keep_alive_packet_and_check_response(self.s1)
        self.assertFalse(alive)
        # second packet should be sent
        alive = self.pool._send_keep_alive_packet_and_check_response(self.s1)
        self.assertTrue(alive)

    def test_is_connection_alive(self):
        host = '127.0.0.1'
        port = 3000
        run_echo_server(host, port)
        self.s1.connect((host, port))
        self.s1.settimeout(1)
        alive = self.pool._is_connection_alive(Connection(self.s1, '_', '_', '_'))
        self.assertTrue(alive)

    def test_no_lock_starvation(self):
        host = '127.0.0.1'
        ports = 4000, 5000, 6000, 7000
        sockets = self.s1, self.s2, self.s3, self.s4
        country_codes = 'uk', 'us', 'ge', 'fr'
        asns = '1', '2', '3', '4'
        for socket, port, cc, asn in zip(sockets, ports, country_codes, asns):
            self.pool.insert(Connection(socket, cc, asn, asn))
            run_echo_server(host, port)
            socket.connect((host, port))
        start_time = time.time()
        Thread(target=self.pool._test_all_available_connections_are_alive).start()
        for cc in reversed(country_codes):
            self.pool.pop_connection_by_country(cc)
        print(f'it took {time.time() - start_time} seconds to finish')
        self.assertLess(time.time() - start_time,
                        1 + ConnectionPool.SLEEP_TIME_BETWEEN_KEEP_ALIVE_PACKETS + ConnectionPool.SOCKET_TIMEOUT_SECONDS)

    def test_country_mapping(self):
        self.pool.insert(self.con1)
        self.pool.insert(self.con2)
        self.pool.insert(self.con3)
        self.pool.insert(self.con4)
        by_country = self.pool.count_connections_by_country()
        self.assertEqual(by_country['us'], 3)
        self.assertEqual(by_country['uk'], 1)


def run_echo_server(host: str, port: int):
    server = UnstableEchoServer(host, port)
    thread = Thread(target=server.run)
    thread.start()
    # let socket connect
    time.sleep(0.2)
