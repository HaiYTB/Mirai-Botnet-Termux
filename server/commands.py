"""
Định nghĩa lệnh gửi tới bot và hàng đợi lệnh.

Mỗi bot có một hàng đợi lệnh riêng. CNC server enqueue lệnh,
bot poll và thực thi, gửi kết quả về.
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PendingCommand:
    cmd_id: str
    bot_id: str
    module: str
    params: dict
    created_at: float
    sent: bool = False


class CommandQueue:
    def __init__(self):
        self._queues: dict[str, list[PendingCommand]] = defaultdict(list)

    def enqueue(self, bot_id: str, module: str, params: dict) -> str:
        cmd_id = str(uuid.uuid4())[:8]
        cmd = PendingCommand(
            cmd_id=cmd_id,
            bot_id=bot_id,
            module=module,
            params=params,
            created_at=__import__("time").time(),
        )
        self._queues[bot_id].append(cmd)
        logger.info("Command enqueued: %s -> %s(%s)", bot_id, module, cmd_id)
        return cmd_id

    def dequeue(self, bot_id: str) -> PendingCommand | None:
        """Lấy lệnh tiếp theo chưa gửi cho bot."""
        queue = self._queues.get(bot_id, [])
        for cmd in queue:
            if not cmd.sent:
                cmd.sent = True
                return cmd
        return None

    def pending_count(self, bot_id: str) -> int:
        return sum(1 for c in self._queues.get(bot_id, []) if not c.sent)

    def remove_bot(self, bot_id: str):
        self._queues.pop(bot_id, None)
