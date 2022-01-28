import socket
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Timer
from typing import List

from expiringdict import ExpiringDict
from infrastructure.wrappers.infra_logger import Logger

ESTIMATED_NUMBER_OF_SUPPORTED_CLOUD_PROVIDERS = 40

IPS_PER_CLOUD_PROVIDER = 10

IP_LIST_MAX_LENGTH = ESTIMATED_NUMBER_OF_SUPPORTED_CLOUD_PROVIDERS * IPS_PER_CLOUD_PROVIDER

CACHE_CLEANUP_MAX_INTERVALS = 10


def resolve_ipv4(address) -> str:
    try:
        ipv4_tcp_result = socket.getaddrinfo(address, 0, socket.AddressFamily.AF_INET, socket.SocketKind.SOCK_STREAM, 0)
        return ipv4_tcp_result[0][-1][0]
    except:
        return ''


class DnsResolver:

    def __init__(self, address_list: List[str], interval_seconds: float):
        self.address_list: List[str] = address_list
        self.thread_pool: ThreadPoolExecutor = ThreadPoolExecutor(len(address_list))
        self.interval: float = interval_seconds
        self.ips = ExpiringDict(max_len=IP_LIST_MAX_LENGTH * len(address_list), max_age_seconds=interval_seconds * CACHE_CLEANUP_MAX_INTERVALS)
        self.thread_pool.submit(self.launch_resolution_threads)
        self.logger = Logger('DnsResolver')

    def launch_resolution_threads(self) -> None:
        for address in self.address_list:
            self.thread_pool.submit(lambda: self.resolve_and_save(address))
        Timer(self.interval, self.launch_resolution_threads)

    def resolve_and_save(self, address) -> None:
        self.logger.info(f"resolving {address}")
        ip = resolve_ipv4(address)
        if ip is not None and ip != '':
            self.ips[ip] = address

    def check_ip_accurately(self, ip) -> bool:
        return self.ips.get(ip) is not None

    def check_ips_subnet_exists(self, ip_to_check) -> bool:
        for ip in self.ips.keys():
            ip_octets = ip.split(r'.')
            ip_to_check_octets = ip_to_check.split(r'.')
            for i in range(3):
                if ip_octets[i] == ip_to_check_octets[i]:
                    if i == 2:
                        return True
                else:
                    break
        return False
