from dataclasses import dataclass


@dataclass
class PortMapping:
    country_code: str
    local_port: int
    remote_ip: str
