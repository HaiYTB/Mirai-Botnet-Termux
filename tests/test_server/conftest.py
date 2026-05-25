"""Test fixtures cho server module"""
import pytest
from server.db import Database
from server.commands import CommandQueue


@pytest.fixture
async def db():
    """Database in-memory cho test"""
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def cmd_queue():
    return CommandQueue()
