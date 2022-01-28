import socket
import sys
from concurrent.futures.thread import ThreadPoolExecutor


class UnstableEchoServer:
    """
    Echoes every other packet.
    """

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.send_back = False
        self.thread_pool = ThreadPoolExecutor(max_workers=1)
        self.connection = None

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.host, self.port))
        s.listen(1)

        self.connection, addr = s.accept()
        print('Connected by', addr)
        try:
            while True:
                data = self.connection.recv(1024)
                if not data:
                    break
                if self.send_back:
                    self.connection.sendall(data)
                self.send_back = not self.send_back
        except InterruptedError:
            if not self.connection._closed:
                self.connection.close()

    def __enter__(self):
        self.thread_pool.submit(self.run)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.thread_pool.shutdown(False)
        if not self.connection._closed:
            self.connection.close()


if __name__ == '__main__':
    UnstableEchoServer(sys.argv[1], int(sys.argv[2]))
