import pytest


@pytest.mark.asyncio
class TestDatabase:
    async def test_add_and_list_bots(self, db):
        await db.add_bot("bot-1", "10.0.0.1", 5555, "Linux", "Ubuntu 22.04", "x86_64", "5.15.0", "pc1", "sess1")
        await db.add_bot("bot-2", "10.0.0.2", 5555, "Linux", "Debian 11", "aarch64", "5.10.0", "rpi", "sess2")

        bots = await db.list_bots()
        assert len(bots) == 2
        assert bots[0]["bot_id"] == "bot-2"  # sorted by last_seen DESC
        assert bots[1]["bot_id"] == "bot-1"

    async def test_get_bot(self, db):
        await db.add_bot("bot-x", "1.2.3.4", 9999, os_name="Linux", hostname="test")
        bot = await db.get_bot("bot-x")
        assert bot["ip"] == "1.2.3.4"
        assert bot["hostname"] == "test"
        assert bot["status"] == "online"

    async def test_get_nonexistent_bot(self, db):
        bot = await db.get_bot("nonexistent")
        assert bot is None

    async def test_count_bots(self, db):
        await db.add_bot("b1", "10.0.0.1", 1, "Linux", "Ubuntu", "x86_64", "", "h1", "")
        await db.add_bot("b2", "10.0.0.2", 2, "Linux", "Debian", "arm", "", "h2", "")
        await db.add_bot("b3", "10.0.0.3", 3, "Linux", "Ubuntu", "x86_64", "", "h3", "")

        counts = await db.count_bots()
        assert counts["total"] == 3
        assert counts["online"] == 3
        assert counts["offline"] == 0
        assert len(counts["by_os"]) >= 2  # Ubuntu + Debian

    async def test_mark_bot_offline(self, db):
        await db.add_bot("bot", "10.0.0.1", 1)
        await db.mark_bot_offline("bot")
        counts = await db.count_bots()
        assert counts["offline"] == 1
        assert counts["online"] == 0

    async def test_update_bot_last_seen(self, db):
        await db.add_bot("bot", "10.0.0.1", 1)
        await db.mark_bot_offline("bot")
        await db.update_bot_last_seen("bot")
        bot = await db.get_bot("bot")
        assert bot["status"] == "online"

    async def test_get_offline_bots(self, db):
        await db.add_bot("bot", "10.0.0.1", 1)
        # Bot vừa thêm sẽ online, không nằm trong danh sách offline
        offline = await db.get_offline_bots(90)
        assert len(offline) == 0

    async def test_commands_crud(self, db):
        await db.add_command("cmd-1", "bot-1", "shell", {"cmd": "ls"})
        await db.update_command("cmd-1", "file1\nfile2\n", 0)
        cmd = await db.get_command("cmd-1")
        assert cmd["module"] == "shell"
        assert cmd["exit_code"] == 0
        assert "file1" in cmd["output"]

    async def test_nonces(self, db):
        assert not await db.is_nonce_used("abc123")
        await db.mark_nonce("abc123")
        assert await db.is_nonce_used("abc123")
        assert not await db.is_nonce_used("xyz789")

    async def test_cleanup_old_nonces(self, db):
        await db.mark_nonce("old")
        await db.cleanup_old_nonces(max_age=0)  # Xoá tất cả
        # Nonce cũ đã bị xoá
        assert not await db.is_nonce_used("old")
