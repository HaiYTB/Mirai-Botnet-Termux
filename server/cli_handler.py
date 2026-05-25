"""
Shared CLI command handler — dùng chung cho TCP CLI và SSH interface.
"""


from server.db import Database
from server.commands import CommandQueue


class CLICommandHandler:
    """Xử lý command dispatch cho cả TCP CLI và SSH."""

    def __init__(self, db: Database, cmd_queue: CommandQueue):
        self._db = db
        self._cmd_queue = cmd_queue

    async def handle_action(self, action: str, req: dict) -> dict:
        """Dispatch một action và trả về response dict."""

        if action == "bots_list":
            bots = await self._db.list_bots()
            return {"ok": True, "data": bots}

        elif action == "bots_count":
            counts = await self._db.count_bots()
            return {"ok": True, "data": counts}

        elif action == "bot_info":
            bot_id = req.get("bot_id", "")
            bot = await self._db.get_bot(bot_id)
            if not bot:
                try:
                    bot = await self._db.get_bot_by_db_id(int(bot_id))
                except ValueError:
                    pass
            if bot:
                return {"ok": True, "data": bot}
            return {"ok": False, "error": "Bot not found"}

        elif action == "cmd_send":
            bot_id = req.get("bot_id", "")
            module = req.get("module", "")
            params = req.get("params", {})
            cmd_id = self._cmd_queue.enqueue(bot_id, module, params)
            return {"ok": True, "cmd_id": cmd_id}

        elif action == "cmd_broadcast":
            module = req.get("module", "")
            params = req.get("params", {})
            bots = await self._db.list_bots()
            online_bot_ids = [b["bot_id"] for b in bots if b["status"] == "online"]
            results = self._cmd_queue.enqueue_all(online_bot_ids, module, params)
            return {
                "ok": True,
                "sent_to": len(results),
                "bot_ids": [bid for bid, _ in results],
            }

        elif action == "cmd_status":
            cmd_id = req.get("cmd_id", "")
            cmd = await self._db.get_command(cmd_id)
            if cmd:
                return {"ok": True, "data": cmd}
            return {"ok": False, "error": "Command not found"}

        elif action == "ping":
            return {"ok": True}

        else:
            return {"ok": False, "error": f"Unknown action: {action}"}
