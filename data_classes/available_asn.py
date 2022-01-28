from typing import List

from dataclasses import dataclass

AVAILABLE_ASN_COLLECTION_NAME = 'AvailableAsns'
COUNTRY_CODE = 'country_code'
ASNS = 'asns'


@dataclass
class AvailableAsn:
    country_code: str
    asns: List[str]
