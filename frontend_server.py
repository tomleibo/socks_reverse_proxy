import json
from collections import Counter
from socket import socket
from typing import List, Dict, Tuple

from flask import Flask, request
from waitress import serve
from connection_pool import ConnectionPool
from offline_device_handler import OfflineDeviceHandler
from super_proxy import SuperProxy
from utils.utils import merge_dicts


class FrontendServer:
    def __init__(self, port, pool: ConnectionPool, device_handler: OfflineDeviceHandler, super_proxy: SuperProxy, country_to_port) -> None:
        self.pool = pool
        self.device_handler = device_handler
        self.super_proxy = super_proxy
        self.port = port
        self.country_to_port = country_to_port
        self.app = Flask(__name__)
        self._set_flask_routes()

    def _set_flask_routes(self):
        self.app.add_url_rule('/map', 'map', self.get_map_data, methods=['GET'])
        self.app.add_url_rule('/wakeup', 'wakeup', self.wakeup_devices, methods=['POST'])
        self.app.add_url_rule('/airplane', 'airplane', self.airplane_mode, methods=['POST'])
        self.app.add_url_rule('/connected_imeis', 'connected_imeis', self.get_pending_devices, methods=['GET'])
        self.app.add_url_rule('/active_connections', 'active_connections', self.get_active_connections, methods=['GET'])
        self.app.add_url_rule('/available_asns_per_country', 'available_asns_per_country', self.get_available_asns_per_country, methods=['GET'])
        self.app.add_url_rule('/country_to_port', 'country_to_port', self.get_country_port_conf, methods=['GET'])

    def start(self):
        serve(self.app, port=self.port)

    def get_map_data(self):
        all_devices = self.device_handler.count_available_devices_by_country()
        connected_device = self.pool.count_connections_by_country()
        used_ports = self._convert_port_mapping_list_to_country_count_dict(self.super_proxy.get_active_sockets())
        data = merge_dicts(['all', 'awaiting_peers', 'used_ports'], all_devices, connected_device, used_ports)
        json_string = json.dumps(data)
        return json_string

    def wakeup_devices(self):
        country_code = request.args.get("cc")
        imei = request.args.get("imei")
        if country_code:
            success = self.device_handler.wakeup_peers_by_country(country_code)
        elif imei:
            success = self.device_handler.wakeup_peer_by_imei(imei)
        else:
            return 'imei or cc should be sent as request args', 400
        return 'Push sent' if success else 'Push failed', 200

    def airplane_mode(self):
        ip = request.args.get("ip")
        if not ip:
            return "ip is expected as request argument"
        result = self.device_handler.generate_new_ip(ip)
        return 'Success' if result else 'Failed', 200

    def get_active_connections(self):
        used_ports: List[Tuple[socket, str]] = self.super_proxy.get_active_sockets()
        return json.dumps(used_ports), 200

    def get_available_asns_per_country(self):
        json_string = json.dumps(self.device_handler.get_available_asns_per_country())
        return json_string, 200

    def get_pending_devices(self):
        json_string = json.dumps(self.pool.get_all_device_ids())
        return json_string, 200

    def get_country_port_conf(self):
        json_string = json.dumps(self.country_to_port)
        return json_string, 200

    @staticmethod
    def _convert_port_mapping_list_to_country_count_dict(port_mappings: List[Tuple[socket, str]]) -> Dict[str, int]:
        return Counter(map(lambda k, v: v, port_mappings))
