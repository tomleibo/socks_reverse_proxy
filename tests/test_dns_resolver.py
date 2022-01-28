import time
import unittest

from utils.dns_resolver import DnsResolver, resolve_ipv4

ADDRESSES = ['www.google.com', 'www.ipinfo.io']


class TestDnsResolver(unittest.TestCase):
    def setUp(self) -> None:
        self.dns_resolver = DnsResolver(ADDRESSES, 60)

    def test_accurate_check(self):
        time.sleep(2)
        ip = resolve_ipv4(ADDRESSES[0])
        self.assertTrue(self.dns_resolver.check_ip_accurately(ip))
        changed_ip = self.change_ip_by_one(ip)
        self.assertFalse(self.dns_resolver.check_ip_accurately(changed_ip))

    def test_subnet_check(self):
        time.sleep(2)
        ip = resolve_ipv4(ADDRESSES[0])
        new_ip = self.change_ip_by_one(ip)
        self.assertTrue(self.dns_resolver.check_ips_subnet_exists(new_ip))
        far_ip = self.change_ip_by_one(ip, 0)
        self.assertFalse(self.dns_resolver.check_ips_subnet_exists(far_ip))

    @staticmethod
    def change_ip_by_one(ip, location=-1):
        ip_as_list = list(ip)
        ip_as_list[location] = str(int(ip[location]) - 1)
        new_ip = "".join(ip_as_list)
        return new_ip
