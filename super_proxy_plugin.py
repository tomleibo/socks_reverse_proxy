import socket
from abc import abstractmethod


class SuperProxyPlugin:
    @abstractmethod
    def register(self, yogurt_socket: socket, peer_socket: socket, peer_id: str):
        pass

    @abstractmethod
    def unregister(self, any_socket: socket):
        pass

    @abstractmethod
    def packet_transmitted(self, source: socket, target: socket, data: bytes):
        pass


class ConnectionInvalid(Exception):
    pass
