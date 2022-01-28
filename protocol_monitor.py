import enum
import re
import socket
from typing import Dict, Set, Callable, List

from infrastructure.wrappers.infra_logger import Logger

from config import config
from database import Database
from super_proxy_plugin import SuperProxyPlugin, ConnectionInvalid
from utils.dns_resolver import DnsResolver

WHITELIST_DNS_RESOLUTION_INTERVAL_SECONDS = 15

HTTPS_CONNECT_METHOD = "CONNECT"

NAGIOS_ALERT_PROTOCOL_ANOMALY = "ALERT-PROTOCOL"

NAGIOS_ALERT_IP_NOT_IN_WHITELIST = "ALERT-IP"

CONFIG_WHITELIST_FEATURE_FLAG = 'service_whitelist_enabled'

CONFIG_SERVICE_WHITELIST = 'service_whitelist'

LOGGER_NAME = "SocksMonitor"

STANDARD_PORTS = [80, 443]


class SocksErrors:
    """
    Socks and HTTPS error types
    """
    ERROR_PACKET_NOT_EXPECTED = "Packet is not expected in this state from this socket"
    SOCKS_VERSION_INVALID = "Socks packet didn't start with 0x05"
    IP_NOT_IN_WHITELIST = "Target IP is not associated with any of the addresses provided in the whitelist"
    RESPONSE_FAILURE = "Socks response was not successful. Expected \\x00 received {}"
    NON_STANDARD_PORT = "Port is not in standard ports"
    NOT_IPV4 = "Address type is not supported. (IPv6 or DNS)"
    RESERVED_BYTE_INVALID = "Reserve byte is invalid (!= 0x00)"
    NON_SUPPORTED_CONNECTION_TYPE = "Connection type is not 'connect' (0x01)"
    NOT_NO_AUTH = "Authentication method chosen is not NO_AUTH (0x00)"
    AUTHENTICATION_METHODS_LENGTH = "Packet length does not match number of authentication methods"
    NOT_CONNECT = "First HTTPS packet should start with CONNECT"
    NO_ADDRESS_FOUND = "First HTTPS packet should hold the ip and port to connect to"


class CloudConnectionsCollection:
    COLLECTION_NAME = "cloudConnection"
    FIELD_DEVICE_ID = 'device_id'
    FIELD_TARGET_PORT = 'target_port'
    FIELD_TARGET_IP = 'target_ip'


class ConnectionState(enum.IntEnum):
    UNCLASSIFIED = 0
    SOCKS_INITIAL = 1
    SOCKS_AUTH_METHODS_SENT = 2
    SOCKS_NEGOTIATION_COMPLETE = 3
    SOCKS_CONNECT_REQUEST_SENT = 4
    HTTPS_INITIAL = 5
    HTTPS_CONNECT_SENT = 6
    CONNECTION_COMPLETE = 7


class Connection:
    def __init__(self, peer_socket: socket, yogurt_socket: socket, peer_id: str):
        self.peer_socket: socket = peer_socket
        self.yogurt_socket: socket = yogurt_socket
        self.state: ConnectionState = ConnectionState.UNCLASSIFIED
        self.peer_id: str = peer_id
        self.target_ip: str = ""
        self.target_port: int = 0

    def __repr__(self):
        return f"Connection [{self.yogurt_socket!r} -> {self.peer_socket!r}]. State = {self.state.name}"


class ProtocolMonitor(SuperProxyPlugin):
    """
    Monitoring and Alerts on every abnormal protocol behavior.
    """
    BIG_ENDIAN_BYTE_ORDER = "big"

    def __init__(self, db):
        self.socket_to_connection: Dict[socket, Connection] = {}
        self.connected_services: Set[str] = set()
        self.db: Database = db
        self.logger = Logger(LOGGER_NAME)
        if config.get(CONFIG_WHITELIST_FEATURE_FLAG) and config.get(CONFIG_SERVICE_WHITELIST):
            self.dns_resolver = DnsResolver(config.get(CONFIG_SERVICE_WHITELIST), WHITELIST_DNS_RESOLUTION_INTERVAL_SECONDS)
        self.state_to_validation_functions: Dict[ConnectionState, List[Callable]] = {
            ConnectionState.UNCLASSIFIED: [self._check_protocol_and_transition_state],
            ConnectionState.SOCKS_INITIAL: [self._socks_validate_first_byte, self._socks_validate_initial_request],
            ConnectionState.SOCKS_AUTH_METHODS_SENT: [self._socks_validate_first_byte,
                                                      self._socks_validate_connection_methods],
            ConnectionState.SOCKS_NEGOTIATION_COMPLETE: [self._socks_validate_first_byte,
                                                         self._socks_validate_connection_type,
                                                         self._socks_validate_reserve_byte,
                                                         self._socks_validate_address_type,
                                                         self._socks_validate_port,
                                                         self._socks_validate_target],
            ConnectionState.SOCKS_CONNECT_REQUEST_SENT: [self._socks_validate_first_byte,
                                                         self._socks_validate_response_success,
                                                         self._socks_validate_reserve_byte,
                                                         self._socks_validate_address_type,
                                                         self._socks_validate_port],
            ConnectionState.HTTPS_INITIAL: [self._https_validate_connect, self._https_validate_target],
            ConnectionState.HTTPS_CONNECT_SENT: [],
            ConnectionState.CONNECTION_COMPLETE: []
        }
        self.state_transitions: Dict[ConnectionState, ConnectionState] = {ConnectionState.SOCKS_CONNECT_REQUEST_SENT: ConnectionState.CONNECTION_COMPLETE,
                                                                          ConnectionState.CONNECTION_COMPLETE: ConnectionState.CONNECTION_COMPLETE}

    def register(self, yogurt_socket: socket, peer_socket: socket, peer_id: str):
        connection = Connection(peer_socket, yogurt_socket, peer_id)
        self.socket_to_connection[peer_socket] = connection
        self.socket_to_connection[yogurt_socket] = connection

    def unregister(self, any_socket: socket):
        try:
            connection = self.socket_to_connection[any_socket]
            del self.socket_to_connection[connection.peer_socket]
            del self.socket_to_connection[connection.yogurt_socket]
            self.connected_services.remove(connection.target_ip)
        except KeyError:
            pass

    def packet_transmitted(self, source: socket, target: socket, data: bytes):
        connection = self.socket_to_connection[source]
        if not self._is_packet_expected_from_this_socket(connection, source):
            self._state_invalid(SocksErrors.ERROR_PACKET_NOT_EXPECTED, connection)
        self._verify_data_is_valid_for_current_state(connection, data, source)
        self._transition_to_next_step(connection)

    def _transition_to_next_step(self, connection):
        new_state = self.state_transitions.get(connection.state.value)
        if new_state is None:
            new_state = ConnectionState(connection.state.value + 1)
        connection.state = new_state

    @staticmethod
    def _is_packet_expected_from_this_socket(connection, source):
        state = connection.state
        """State number is odd if and only if the packet originates in Yogurt"""
        packet_parity_fits_socket = (state.value % 2 == 1) == (source == connection.yogurt_socket)
        first_packet = source == connection.yogurt_socket and state == ConnectionState.UNCLASSIFIED
        protocol_negotiation_complete = state == ConnectionState.CONNECTION_COMPLETE
        return packet_parity_fits_socket or protocol_negotiation_complete or first_packet

    def _verify_data_is_valid_for_current_state(self, connection, data, source):
        try:
            functions = self.state_to_validation_functions[connection.state]
        except KeyError:
            return
        for func in functions:
            error_msg = func(data, connection, source)
            if error_msg:
                self._state_invalid(error_msg, connection)

    def _check_protocol_and_transition_state(self, data, connection, source):
        if data[0] == 5:
            state = ConnectionState.SOCKS_INITIAL
        else:
            state = ConnectionState.HTTPS_INITIAL
        connection.state = state
        self._verify_data_is_valid_for_current_state(connection, data, source)

    @staticmethod
    def _socks_validate_first_byte(data, *_):
        if data[0] != 5:
            return SocksErrors.SOCKS_VERSION_INVALID

    @staticmethod
    def _socks_validate_initial_request(data, *_):
        if len(data) != int(data[1]) + 2:
            return SocksErrors.AUTHENTICATION_METHODS_LENGTH

    @staticmethod
    def _socks_validate_connection_methods(data, *_):
        if data[1] != 0:
            return SocksErrors.NOT_NO_AUTH

    @staticmethod
    def _socks_validate_connection_type(data, *_):
        if data[1] != 1:
            return SocksErrors.NON_SUPPORTED_CONNECTION_TYPE

    @staticmethod
    def _socks_validate_reserve_byte(data, *_):
        if data[2] != 0:
            return SocksErrors.RESERVED_BYTE_INVALID

    @staticmethod
    def _socks_validate_address_type(data, *_):
        if data[3] != 1:
            return SocksErrors.NOT_IPV4

    def _socks_validate_port(self, data, connection: Connection, *_):
        port = int.from_bytes(data[-2:], ProtocolMonitor.BIG_ENDIAN_BYTE_ORDER)
        if port not in STANDARD_PORTS:
            self._state_warn(SocksErrors.NON_STANDARD_PORT, connection, 'port: ', port)
        connection.target_port = port

    @staticmethod
    def _socks_validate_response_success(data, *_):
        if data[1] != 0:
            return SocksErrors.RESPONSE_FAILURE.format({str(data[1])})

    def _socks_validate_target(self, data, connection: Connection, *_):
        ip = str(socket.inet_ntoa(data[4:-2]))
        port = int.from_bytes(data[-2:], ProtocolMonitor.BIG_ENDIAN_BYTE_ORDER)
        self._process_new_target(connection, ip, port)

    @staticmethod
    def _https_validate_connect(data, *_):
        if not str(data).startswith(HTTPS_CONNECT_METHOD):
            return SocksErrors.NOT_CONNECT

    def _https_validate_target(self, data, connection, *_):
        connect_string = str(data)
        matches = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)", connect_string)
        ip = matches[1]
        port = matches[2]
        self._process_new_target(connection, ip, port)

    def _process_new_target(self, connection, ip, port):
        connection.target_ip = ip
        self.connected_services.add(ip)
        self.logger.info(f'Socks connection to a new IP. {connection} --> {ip}')
        self._validate_ip_is_in_whitelist(ip, connection)
        self.db.insert_one(CloudConnectionsCollection.COLLECTION_NAME, {CloudConnectionsCollection.FIELD_TARGET_IP: ip,
                                                                        CloudConnectionsCollection.FIELD_TARGET_PORT: port,
                                                                        CloudConnectionsCollection.FIELD_DEVICE_ID: connection.peer_id})

    def _state_invalid(self, state_msg: str, connection: Connection, alert_type=NAGIOS_ALERT_PROTOCOL_ANOMALY):
        error_msg = alert_type + f" - invalid state occurred on {connection!r}"
        self.logger.error(error_msg + " " + state_msg)
        raise ConnectionInvalid(error_msg)

    def _state_warn(self, warn_msg: str, connection: Connection, *extra_info):
        self.logger.warning(warn_msg + connection.__repr__(), extra_info)

    def _validate_ip_is_in_whitelist(self, ip, connection):
        if not config.get(CONFIG_WHITELIST_FEATURE_FLAG) or not config.get(CONFIG_SERVICE_WHITELIST):
            return
        if not self.dns_resolver.check_ips_subnet_exists(ip):
            self._state_warn(SocksErrors.IP_NOT_IN_WHITELIST, connection, NAGIOS_ALERT_IP_NOT_IN_WHITELIST)
