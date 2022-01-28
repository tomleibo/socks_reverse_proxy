import os
import subprocess
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from socket import socket, SOL_SOCKET, SO_REUSEADDR
from typing import Tuple
from utils import utils

import geoip2.database
from infrastructure.wrappers.infra_logger import Logger
from infrastructure.wrappers.mongo import Mongo

from data_classes.connection import Connection
from connection_pool import ConnectionPool
from data_classes.device_details import DeviceDetails


class PeerServer:
    """
    Peer Server which handle and manage all peers (devices) socket connections.
    The server create sockets and bind them to configuration port and listen for new connection.
    Once we have new connection the server extract ASN and country code from it remote address.
    Handle and manage the exfilitrate data from the device and save the connection at Connection Pool and at the DB.
    """
    FCM_ID_LENGTH = 250
    IMEI_LENGTH = 32
    APP_VERSION = 4
    MAX_BACKLOG_CONNECTIONS = 1
    LISTENING_PORTS_LEN = 100
    GEO_IP_DIR = os.getcwd() + '/geoip/' if 'test' not in os.getcwd() else \
        os.path.join(os.path.abspath(os.path.join(os.getcwd(), '..')), 'geoip/')
    ASN_DB_PATH = GEO_IP_DIR + 'GeoLite2-ASN.mmdb'
    CITY_DB_PATH = GEO_IP_DIR + 'GeoLite2-City.mmdb'
    COUNTRY_DB_PATH = GEO_IP_DIR + 'GeoLite2-Country.mmdb'
    NOT_AVAILABLE = "N/A"
    MAX_WORKERS = 1

    def __init__(self, db: Mongo, listening_port: int, connection_pool: ConnectionPool) -> None:
        self.should_stop: bool = False
        self.listening_port: int = listening_port
        self.thread_pool = ThreadPoolExecutor(max_workers=PeerServer.MAX_WORKERS)
        self.connection_pool: ConnectionPool = connection_pool
        self.db = db
        self.logger = Logger("PeerServer")
        self._check_geoip_db([PeerServer.ASN_DB_PATH, PeerServer.CITY_DB_PATH, PeerServer.COUNTRY_DB_PATH])

    def start(self) -> None:
        self.thread_pool.submit(self._listen, self.listening_port)

    def stop(self):
        self.should_stop = True
        self.thread_pool.shutdown(False)

    def _check_connection(self, ip) -> bool:
        """
        Check the connection source ip and decided if allow the connection or not.
        :param ip: source ip.
        :return: True is connection allow, else False.
        """
        return self._blacklist(ip)

    def _listen(self, port: int) -> None:
        """
        Create new socket and listen to new connection.
        :param port: Listening port.
        :return: None
        """
        server_socket = socket()
        server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(PeerServer.MAX_BACKLOG_CONNECTIONS)
        while not self.should_stop:
            self.logger.debug(f'listening for peers on port {port}')
            peer_socket, remote_address = server_socket.accept()
            if self._check_connection(remote_address):
                self.logger.info(f'Received new connection from {remote_address}')
                try:
                    self._handle_new_connection(peer_socket, remote_address)
                except Exception as e:
                    self.logger.error("exception raised while parsing or saving new connection: ", exc_info=e)
                    peer_socket.close()
            else:
                self.logger.error(f'Invalid connection from {remote_address}')

    def _handle_new_connection(self, peer_socket, remote_address):
        """
        Handle and mange new connection to backend.
        Extract country and asn from remote address and save the connection at ConnectionPool and at the DB.
        :param peer_socket: output socket.
        :param remote_address: source ip.
        :return:
        """
        try:
            country, asn = self._ip_to_cc_asn(remote_address[0])
        except Exception as e:
            self.logger.warn(f"Failed to find country and/or asn for {remote_address}. {e!r}")
            country = PeerServer.NOT_AVAILABLE
            asn = PeerServer.NOT_AVAILABLE
        try:
            device_details: DeviceDetails = self._create_device_details(peer_socket, country, asn, remote_address)
        except ValueError as e:
            self.logger.error('First packet should be in the form of IMEI, FCM_ID, APP_VERSION', exc_info=e)
            raise e
        self._save_connection_in_pool(peer_socket, country, asn, device_details.imei)
        if not self._update_db(device_details):
            error_msg = "Failed to update data with device_details"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    def _save_connection_in_pool(self, peer_socket: socket, country, asn, device_id):
        """
        Save new connection at ConnectionPool.
        :param peer_socket: output socket.
        :param country: country.
        :param asn: Provider.
        :param device_id: device_id.
        :return:
        """
        connection = Connection(peer_socket, country, asn, device_id)
        self.connection_pool.insert(connection)

    def _create_device_details(self, peer_socket: socket, country_code: str, asn: str, remote_address):
        packet_size = PeerServer.IMEI_LENGTH + PeerServer.FCM_ID_LENGTH + PeerServer.APP_VERSION + 1
        delimiter = ','
        packet: bytes = peer_socket.recv(packet_size)
        data = packet.decode("utf-8")
        imei, *fcm_id = data.split(delimiter)
        app_version = fcm_id[1] if len(fcm_id) > 1 else "0"
        fcm_id = fcm_id[0]
        if not utils.regex_check("all", [imei, fcm_id]):
            self.logger.error("Protocol Anomalies alert: receive unexpected Device Details:"
                              " IMEI: {0}.  FCM_ID: {1}".format(imei, fcm_id))
            raise ValueError
        return DeviceDetails(imei=imei, fcm_id=fcm_id, asn=asn, country_code=country_code,
                             ip=remote_address, app_version=app_version)

    def _update_db(self, device_details) -> bool:
        device = self.db.find_one(DeviceDetails.COLLECTION_NAME, {DeviceDetails.IMEI: device_details.imei})
        if device:
            write_result = self.db.update_one(DeviceDetails.COLLECTION_NAME, device[DeviceDetails.ID], device_details.__dict__)
        else:
            write_result = self.db.insert_one(DeviceDetails.COLLECTION_NAME, device_details)
        return write_result

    def _check_geoip_db(self, geoip_db_list: list):
        for db in geoip_db_list:
            if not os.path.exists(db) or os.stat(db).st_size == 0:
                status = self._get_geoip_db()
                if not status:
                    raise Exception("Couldn't install geoip2 data")
        return True

    @staticmethod
    def _ip_to_cc_asn(ip) -> Tuple[str, str]:
        with geoip2.database.Reader(PeerServer.ASN_DB_PATH) as reader:
            response = reader.asn(ip)
            asn = response.autonomous_system_number
        with geoip2.database.Reader(PeerServer.CITY_DB_PATH) as reader:
            response = reader.city(ip)
            country = response.country.iso_code
        return country, str(asn)

    @staticmethod
    def _blacklist(ip) -> bool:
        blacklist = []
        return True

    @staticmethod
    def _get_geoip_db() -> bool:
        command = "geoipupdate -d {0} -f /etc/GeoIP.conf –v".format(PeerServer.GEO_IP_DIR)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return not proc.returncode
