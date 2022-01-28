import time
from typing import List

from infrastructure.wrappers.fcm import FcmResponse


class CommandsSent:

    COLLECTION_NAME = "CommandsSent"
    TIMESTAMP = "timestamp"
    COMMAND_TYPE = "command_type"
    FCM_IDS = "fcm_ids"
    SUCCESS_COUNT = "success_count"
    FAILURE_COUNT = "failure_count"

    def __init__(self, fcm_ids: List[str], command_type: int, success_count: int, failure_count: int, timestamp: float = None) -> None:
        self.fcm_ids: List[str] = fcm_ids
        self.command_type: int = command_type
        self.success_count: int = success_count
        self.failure_count: int = failure_count
        if timestamp:
            self.timestamp: float = timestamp
        else:
            self.timestamp: float = time.time()

    @classmethod
    def build_from_fcm_response(cls, fcm_response: FcmResponse, tokens: List[str], command_type: int):
        return CommandsSent(tokens, command_type, fcm_response.success, fcm_response.failure)
