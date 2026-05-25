"""Test command queue"""


class TestCommandQueue:
    def test_enqueue_dequeue(self, cmd_queue):
        cmd_id = cmd_queue.enqueue("bot-1", "shell", {"cmd": "whoami"})
        assert len(cmd_id) == 8

        cmd = cmd_queue.dequeue("bot-1")
        assert cmd is not None
        assert cmd.module == "shell"
        assert cmd.params == {"cmd": "whoami"}
        assert cmd.sent is True

    def test_dequeue_only_once(self, cmd_queue):
        cmd_queue.enqueue("bot-1", "shell", {"cmd": "ls"})
        assert cmd_queue.dequeue("bot-1") is not None
        assert cmd_queue.dequeue("bot-1") is None  # Đã sent

    def test_multiple_commands(self, cmd_queue):
        cmd_queue.enqueue("bot-1", "shell", {"cmd": "a"})
        cmd_queue.enqueue("bot-1", "flood", {"type": "udp"})
        cmd_queue.enqueue("bot-1", "recon", {"type": "system"})

        c1 = cmd_queue.dequeue("bot-1")
        c2 = cmd_queue.dequeue("bot-1")
        c3 = cmd_queue.dequeue("bot-1")
        c4 = cmd_queue.dequeue("bot-1")

        assert c1.module == "shell"
        assert c2.module == "flood"
        assert c3.module == "recon"
        assert c4 is None

    def test_pending_count(self, cmd_queue):
        assert cmd_queue.pending_count("bot-1") == 0
        cmd_queue.enqueue("bot-1", "shell", {})
        assert cmd_queue.pending_count("bot-1") == 1
        cmd_queue.enqueue("bot-1", "flood", {})
        assert cmd_queue.pending_count("bot-1") == 2
        cmd_queue.dequeue("bot-1")
        assert cmd_queue.pending_count("bot-1") == 1

    def test_remove_bot(self, cmd_queue):
        cmd_queue.enqueue("bot-1", "shell", {})
        cmd_queue.remove_bot("bot-1")
        assert cmd_queue.pending_count("bot-1") == 0
