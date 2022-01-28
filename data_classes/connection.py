from socket import socket

from dataclasses import dataclass


@dataclass
class Connection:
    socket: socket
    country_code: str
    asn: str
    device_id: str

    def __eq__(self, other):
        try:
            return self.socket == other.socket and self.country_code == other.country_code and self.asn == other.asn and self.device_id == other.device_id
        except:
            return False

    def __hash__(self):
        return hash((self.socket, self.country_code, self.asn, self.device_id))

    def __repr__(self) -> str:
        return f'{self.device_id}, {self.country_code}, {self.asn}, {self.socket}'
