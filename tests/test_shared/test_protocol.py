"""Test protocol message serialization"""
import time

from shared.protocol import (
    Message,
    MessageType,
    create_auth,
    create_auth_ack,
    create_cmd,
    create_error,
    create_heartbeat,
    create_info,
    create_result,
    deserialize,
    serialize,
)


class TestMessage:
    def test_message_defaults(self):
        msg = Message(type=MessageType.HEARTBEAT)
        assert msg.type == "heartbeat"
        assert len(msg.id) > 0
        assert msg.timestamp > 0
        assert len(msg.nonce) == 32  # 16 bytes hex
        assert msg.data == {}

    def test_message_to_from_json(self):
        msg = Message(type="test", data={"key": "value"})
        raw = msg.to_json()
        restored = Message.from_json(raw)
        assert restored.type == msg.type
        assert restored.id == msg.id
        assert restored.data == msg.data


class TestSerializeRoundtrip:
    def test_auth_message(self, crypto):
        msg = create_auth("bot-007", "abc123hash")
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.AUTH
        assert restored.data["bot_id"] == "bot-007"
        assert restored.data["key_hash"] == "abc123hash"

    def test_auth_ack_message(self, crypto):
        msg = create_auth_ack("ok", "session-xyz")
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.AUTH_ACK
        assert restored.data["status"] == "ok"
        assert restored.data["session_id"] == "session-xyz"

    def test_info_message(self, crypto):
        msg = create_info("Linux", "Debian 11", "aarch64", "5.10.0", "raspberry")
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.INFO
        assert restored.data["hostname"] == "raspberry"
        assert restored.data["arch"] == "aarch64"

    def test_cmd_message(self, crypto):
        msg = create_cmd("cmd-001", "shell", {"cmd": "whoami"})
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.CMD
        assert restored.data["module"] == "shell"
        assert restored.data["params"]["cmd"] == "whoami"

    def test_result_message(self, crypto):
        msg = create_result("cmd-001", "root\n", 0)
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.RESULT
        assert restored.data["output"] == "root\n"
        assert restored.data["exit_code"] == 0

    def test_heartbeat_message(self, crypto):
        msg = create_heartbeat()
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.HEARTBEAT

    def test_error_message(self, crypto):
        msg = create_error("AUTH_FAIL", "Invalid key")
        wire = serialize(msg, crypto)
        restored = deserialize(wire, crypto)
        assert restored.type == MessageType.ERROR
        assert restored.data["code"] == "AUTH_FAIL"


class TestReplayProtection:
    def test_unique_nonce_per_message(self):
        msg1 = create_heartbeat()
        msg2 = create_heartbeat()
        assert msg1.nonce != msg2.nonce

    def test_unique_id_per_message(self):
        msg1 = create_heartbeat()
        msg2 = create_heartbeat()
        assert msg1.id != msg2.id

    def test_timestamp_is_recent(self):
        msg = create_heartbeat()
        assert abs(msg.timestamp - time.time()) < 1.0
