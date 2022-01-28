class NoAvailableConnection(Exception):
    def __init__(self, country: str, asn: str = None) -> None:
        self.country: str = country
        self.asn: str = asn

    def __repr__(self) -> str:
        return f"No port found for {self.country}{(', '+self.asn if self.asn is not None else '')}"
