from socket import socket


class TempSocketTimeoutSetter:
    def __init__(self, _socket: socket, timeout: float):
        # _socket instead of socket is to prevent shadows
        self.socket = _socket
        self.previous_timeout = None
        self.temp_timeout = timeout

    def __enter__(self):
        self.previous_timeout = self.socket.gettimeout()
        self.socket.settimeout(self.temp_timeout)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.socket = self.previous_timeout
