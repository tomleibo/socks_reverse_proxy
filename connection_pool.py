import time
from collections import defaultdict
from concurrent.futures.thread import ThreadPoolExecutor
from functools import reduce
import struct
from threading import Timer
from typing import Dict, List
import socket
from infrastructure.wrappers.infra_logger import Logger

from data_classes.connection import Connection
from utils.no_available_connection_exception import NoAvailableConnection
from utils.temp_socket_timeout_setter import TempSocketTimeoutSetter

MAX_THREADS_FOR_PARALLEL_FILTER = 25


class ConnectionPool:
    """
    Connection-handling pool. Connections are ordered and can be fetched by country and ASN for later use by a socks server.
    Connections are constantly kept alive and filtered out. Every FULL_KEEP_ALIVE_INTERVAL seconds, it sends a keep alive packet to each socket.
    Sockets that don't respond KEEP_ALIVE_ATTEMPTS times within SOCKET_TIMEOUT_SECONDS are considered disconnected and are removed from the pool.
    API:
    1. insert - When a new peer is connected to a socket, its IP should be resolved into CC and asn, then wrapped in a Connection object and inserted.
    2. pop_connection_by_country - get an alive connection using only its country code.
    3. pop_connection_by_country_and_asn - get an alive connection using country code and ASN.
    4. count_connections_by_country - returns a dict in the form {country: #}
    """
    TCP_SOCKET_STATE_CONNECTED = 1
    SLEEP_TIME_BETWEEN_KEEP_ALIVE_PACKETS = 1
    SOCKET_TIMEOUT_SECONDS = 2
    KEEP_ALIVE_ATTEMPTS = 3
    SLEEP_TIME_BETWEEN_ASN_KEEP_ALIVES = 0.2
    FULL_KEEP_ALIVE_INTERVAL = 60*15
    CLEAN_USED_CONNECTIONS_INTERVAL = 120
    KEEP_ALIVE_PACKET_DATA: str = "KEAL"
    WIFI_WARN_PACKET_DATA = 'waaxbkceuvmmonqxtxbequkjvarqkehqjzzetfvyagr' \
                            'kwafqujqiiqxuautddwfsobmegzaygdcawwdvjoodpr' \
                            'foexyonvygplshecndoysfajaapenheqbssehlpnvf'

    DEBUGGER_WARN_PACKET_DATA = 'SPZ4SOCCHFIH23VFF00KCQNIZ4QKUKG5VG283AMJK' \
                                '7AFC2NUPDTYC7MBRX4VHHBDQT9TTRXQYD0SZ8TXGU7OUT' \
                                'GL3TQUWOQ2ONKHYA12KWWZDDG9ZLYTS0FR1NT5OKLM'

    def __init__(self) -> None:
        self.available_connections: Dict[str, Dict[str, List[Connection]]] = defaultdict(lambda: defaultdict(list))
        self.used_connections: List[Connection] = []
        self.logger = Logger('C-pool')
        Timer(ConnectionPool.FULL_KEEP_ALIVE_INTERVAL, self._test_all_available_connections_are_alive).start()
        Timer(ConnectionPool.CLEAN_USED_CONNECTIONS_INTERVAL, self._clean_used_connections).start()

    def insert(self, connection: Connection) -> None:
        """
        When a new peer is connected to a socket, its IP should be resolved into CC and asn,
        then wrapped in a Connection object and inserted.
        :param connection: new peer
        :return: None.
        """
        self.logger.info(f'New Peer: {connection.country_code}/{connection.asn}')
        self.available_connections[connection.country_code][connection.asn].append(connection)

    def pop_connection_by_country(self, country_code: str) -> Connection:
        """
        get an alive connection using only its country code.
        :param country_code: country code to look for available connection.
        :return: Available peer.
        """
        self.logger.info(f'Trying to pop connection from {country_code}')
        if country_code not in self.available_connections.keys():
            raise NoAvailableConnection(country_code)
        asn_lists = self.available_connections[country_code].values()
        self.logger.debug("ASN Lists: ", asn_lists)
        if not asn_lists:
            self.logger.error("No Available ASN at {0}".format(country_code))
        for asn_list in asn_lists:
            connection = self._pop_if_list_not_empty(asn_list)
            if not connection:
                self.logger.error("Connection list in empty")
                continue
            self.logger.info(f'Popping connection from {country_code}')
            return connection
        raise NoAvailableConnection(country_code)

    def pop_connection_by_country_and_asn(self, country_code: str, asn: str) -> Connection:
        """
        get an alive connection using country code and ASN.
        :param country_code: country code to look for available connection.
        :param asn: Provider to look for available connection.
        :return: Available peer.
        """
        self.logger.info(f'Popping connection from {country_code}/{asn}')
        connection_list = self.available_connections[country_code][asn]
        connection = self._pop_if_list_not_empty(connection_list)
        if connection:
            return connection
        raise NoAvailableConnection(country_code, asn)

    def count_connections_by_country(self) -> Dict[str, int]:
        """
        Check how many available connections we have per country.
        :return: Number of connection per country
        """
        country_count = {}
        for country, asn_dict in self.available_connections.items():
            country_count[country] = reduce(lambda x, y: len(y) + x, asn_dict.values(), 0)
        return country_count

    def get_all_device_ids(self, distinct=False):
        """
        Get all available device ids.
        :param distinct: unique results or not.
        :return: List of all available device ids.
        """
        device_ids = []
        for asn_dict in self.available_connections.values():
            for connection_list in asn_dict.values():
                for connection in connection_list:
                    device_ids.append(connection.device_id)
        device_ids.append([c.device_id for c in self.used_connections])
        if distinct:
            return list(set(device_ids))
        return device_ids

    def close_all_connections(self):
        for asn_dict in self.available_connections.values():
            for connection_list in asn_dict.values():
                for connection in connection_list:
                    connection.socket.close()
        for connection in self.used_connections:
            connection.socket.close()

    def _pop_if_list_not_empty(self, list_to_check: list) -> Connection:
        if len(list_to_check) > 0:
            connection: Connection = list_to_check.pop()
            self._use_connection(connection)
            return connection

    def _test_all_available_connections_are_alive(self) -> None:
        self.logger.info(f'Starting keep alive cycle')
        for country, asn_dict in self.available_connections.items():
            for asn, connection_list in asn_dict.items():
                try:
                    alive_connections = list(self.parallel_filter(lambda c: self._is_connection_alive(c) and self._is_tcp_state_ok(c), connection_list))
                    dead_connections = list(set(connection_list) - set(alive_connections))
                    for c in dead_connections:
                        c.socket.close()
                    connection_list[:] = alive_connections
                    self.logger.info(
                        f'Keep alive check on {country}/{asn} removed {len(dead_connections)} connections. \n'
                        f'{len(alive_connections)} devices are still connected in {country}/{asn}.')
                except Exception as e:
                    self.logger.error("keep alive was interrupted due to exception: ", exc_info=e)
        Timer(ConnectionPool.FULL_KEEP_ALIVE_INTERVAL, self._test_all_available_connections_are_alive).start()

    def _is_connection_alive(self, connection: Connection) -> bool:
        _socket = connection.socket
        with TempSocketTimeoutSetter(_socket, self.SOCKET_TIMEOUT_SECONDS):
            alive = False
            for _ in range(self.KEEP_ALIVE_ATTEMPTS):
                alive = self._send_keep_alive_packet_and_check_response(_socket)
                if alive:
                    break
                time.sleep(self.SLEEP_TIME_BETWEEN_KEEP_ALIVE_PACKETS)
        return alive

    def _send_keep_alive_packet_and_check_response(self, _socket) -> bool:
        bytes_to_send = bytes(ConnectionPool.KEEP_ALIVE_PACKET_DATA, 'utf-8')
        wifi_warn = bytes(ConnectionPool.WIFI_WARN_PACKET_DATA, 'utf-8')
        debugger_warn = bytes(ConnectionPool.DEBUGGER_WARN_PACKET_DATA, 'utf-8')
        try:
            bytes_sent = _socket.send(bytes_to_send)
            if bytes_sent != len(bytes_to_send):
                return False
            response = _socket.recv(bytes_sent)
        except Exception:
            return False
        if response.hex() == wifi_warn.hex():
            self.logger.error("Wifi connection has been detected")
            return False
        if response.hex() == debugger_warn.hex():
            self.logger.error("Debugger connection has been detected")
            return False
        elif len(response) == 0:
            return False
        elif response.hex() == bytes_to_send.hex():
            return True
        else:
            self.logger.error("Protocol Anomalies alert: receive unexpected response: {0}".format(response.hex()))
            return False

    def _use_connection(self, connection):
        self.used_connections.append(connection)

    def _clean_used_connections(self):
        alive_connections = list(self.parallel_filter(self._is_tcp_state_ok, self.used_connections))
        self.used_connections[:] = alive_connections
        Timer(ConnectionPool.CLEAN_USED_CONNECTIONS_INTERVAL, self._clean_used_connections).start()

    def _is_tcp_state_ok(self, connection):
        s = connection.socket
        return self.get_socket_state(s) == ConnectionPool.TCP_SOCKET_STATE_CONNECTED

    @staticmethod
    def parallel_filter(func, candidates):
        pool = ThreadPoolExecutor(len(candidates) if len(candidates) < MAX_THREADS_FOR_PARALLEL_FILTER else MAX_THREADS_FOR_PARALLEL_FILTER)
        filtered_list = [c for c, keep in zip(candidates, pool.map(func, candidates)) if keep]
        pool.shutdown(True)
        return filtered_list

    @staticmethod
    def get_socket_state(s):
        fmt = "B" * 7 + "I" * 21
        return struct.unpack(fmt, s.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 92))[0]

    def __len__(self):
        return reduce(lambda x, asn_dict: x + reduce(lambda y, con_list: y + len(con_list), asn_dict.values(), 0),
                      self.available_connections.values(), 0)
