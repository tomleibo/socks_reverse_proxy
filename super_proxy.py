import selectors
import sys, errno
from concurrent.futures.thread import ThreadPoolExecutor
from socket import socket, SOL_SOCKET, SO_REUSEADDR
from threading import Lock
from typing import Dict, List, Tuple
from config import config

from infrastructure.wrappers.infra_logger import Logger

from connection_pool import ConnectionPool
from database import Database
from dataplan_tracker import DataplanTracker
from protocol_monitor import ProtocolMonitor
from super_proxy_plugin import ConnectionInvalid
from utils.no_available_connection_exception import NoAvailableConnection
from data_classes.connection import Connection

SOCKET_READ_SIZE = 1024
CLOSING_PACKET = b'9TS0JUUL8HARDIP8JS9LFMH1UIRECWOQX109KF' \
                 b'1GZFUV6N4RH68QM5SFDL1I6ORGDZ071OA85460HGY' \
                 b'T8M2K134Y367XRAE5FDSU8YSUA09DQMO7KI61VIL6' \
                 b'45DYCXE3'
MAX_BACKLOG_CONNECTIONS_PER_COUNTRY = 10


class SuperProxy:

    def __init__(self, country_to_port_configuration: Dict[str, int], pool: ConnectionPool, db: Database, thread_pool_workers=100):
        self.logger = Logger('SuperProxy', level=config['log_level'])
        self.conn_pool = pool
        self.thread_pool = ThreadPoolExecutor(max_workers=thread_pool_workers)
        self.selector = selectors.DefaultSelector()
        self.mutex = Lock()
        self.used_peer_sockets: Dict[socket, str] = {}
        self.plugins = [ProtocolMonitor(db), DataplanTracker(db)]
        self.sockets = []
        for country, port in country_to_port_configuration.items():
            self.sockets.append(self._configure_port(country, port))
        self.thread_pool.submit(self._loop_selector)

    def get_active_sockets(self) -> List[Tuple[socket, str]]:
        return [(k, v) for (k, v) in self.used_peer_sockets.items()]

    def shutdown(self):
        for sock in self.sockets:
            sock.close()

    def _configure_port(self, country_code, port):
        sock: socket = self._create_storm_socket(port)
        self.selector.register(sock, selectors.EVENT_READ, lambda conn, _: self._accept(conn, country_code))
        self.logger.info(f'Opened port {str(port)} for reaching devices in {country_code}')
        return sock

    def _get_peer_socket_in_country(self, country_code) -> Connection:
        connection = self.conn_pool.pop_connection_by_country(country_code)
        if connection.socket is None:
            raise NoAvailableConnection(country_code)
        with self.mutex:
            self.used_peer_sockets[connection.socket] = country_code
        return connection

    @staticmethod
    def _create_storm_socket(port: int) -> socket:
        storm_socket = socket()
        try:
            storm_socket.bind(('0.0.0.0', port))
        except OSError as e:
            print(f'port {port} is already in use. Exception thrown: {e!r}. Exiting')
            sys.exit(1)
        storm_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        storm_socket.listen(MAX_BACKLOG_CONNECTIONS_PER_COUNTRY)
        return storm_socket

    def _accept(self, country_socket: socket, country_code: str):
        self.logger.info(f'received accept event on port: {country_socket.getsockname()[1]} which is configured to cc: {country_code}')
        yogurt_socket, remote_address = country_socket.accept()
        try:
            connection = self._get_peer_socket_in_country(country_code)
            peer_socket: socket = connection.socket
        except NoAvailableConnection as e:
            self.logger.error("NoAvailableConnection: {0}".format(e))
            yogurt_socket.close()
            return
        yogurt_socket.setblocking(False)
        peer_socket.setblocking(False)
        for plugin in self.plugins:
            plugin.register(yogurt_socket, peer_socket, connection.device_id)
        self.selector.register(peer_socket, selectors.EVENT_READ, lambda conn, _: self._transmit(conn, yogurt_socket, peer_socket))
        self.selector.register(yogurt_socket, selectors.EVENT_READ, lambda conn, _: self._transmit(conn, yogurt_socket, peer_socket))

    def _transmit(self, conn: socket, yogurt_socket: socket, peer_socket: socket):
        self.logger.debug(f'received transmit event on port {conn.getsockname()[1]}')
        conn.settimeout(2)
        try:
            data = conn.recv(SOCKET_READ_SIZE)
            if data:
                self._send_packet_to_target_socket(conn, data, peer_socket, yogurt_socket)
                return
        except ConnectionInvalid as e:
            self.logger.error("Socks socket is in invalid state. {0}".format(e))
        self._close_sockets(conn, peer_socket, yogurt_socket)

    def _send_packet_to_target_socket(self, conn, data, peer_socket, yogurt_socket):
        self.logger.debug(f'Received packet on port {conn.getsockname()[1]}:  {data!r}')
        source_socket, target_socket = ((yogurt_socket, peer_socket) if conn == yogurt_socket else (peer_socket, yogurt_socket))
        target_socket.sendall(data)
        for plugin in self.plugins:
            plugin.packet_transmitted(source_socket, target_socket, data)

    def _close_sockets(self, conn, peer_socket, yogurt_socket):
        self.logger.debug("Sending closing packet to port: {0}".format(conn.getsockname()[1]))
        try:
            peer_socket.sendall(CLOSING_PACKET)
        except:
            # sending a packet might not be possible as the socket might be already closed.
            pass
        self.logger.debug(f"Closed connection on port: {conn.getsockname()[1]}")
        try:
            self.selector.unregister(peer_socket)
            self.selector.unregister(yogurt_socket)
        except:
            self.logger.error("Failed to unregister sockets from selector")
        try:
            yogurt_socket.close()
            peer_socket.close()
        except:
            self.logger.error("Failed to close sockets in _close_sockets()")
        for plugin in self.plugins:
            plugin.unregister(conn)
        with self.mutex:
            del self.used_peer_sockets[peer_socket]

    def _loop_selector(self):
        while True:
            try:
                events = self.selector.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
            except IOError as e:
                if e.errno == errno.EPIPE:
                    self.logger.debug("Broken pipe in _loop_selector")
                    self.logger.error(str(e.__dict__))
            except Exception as e:
                self.logger.error("exception in loop_selectors", exc_info=e)
