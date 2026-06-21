import pytest
import pytest_asyncio
from pathlib import Path
from utils.db import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    d = Database(tmp_path / "test.db")
    await d.connect()
    yield d
    await d.close()


# --- get_or_create_user ---

@pytest.mark.asyncio
async def test_get_or_create_user_creates_row(db):
    row = await db.get_or_create_user("111")
    assert row["discord_id"] == "111"

@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing(db):
    await db.get_or_create_user("111")
    await db.update_user("111", fishing_skill=7)
    row = await db.get_or_create_user("111")
    assert row["fishing_skill"] == 7

@pytest.mark.asyncio
async def test_get_or_create_user_idempotent(db):
    await db.get_or_create_user("111")
    await db.get_or_create_user("111")  # no error
    row = await db.get_user("111")
    assert row is not None


# --- add_favorite / remove_favorite / get_favorites ---

@pytest.mark.asyncio
async def test_add_and_get_favorites_by_type(db):
    await db.add_favorite("111", "fish", "goldfish")
    favs = await db.get_favorites("111", "fish")
    assert len(favs) == 1
    assert favs[0]["item_id"] == "goldfish"

@pytest.mark.asyncio
async def test_add_favorite_is_idempotent(db):
    await db.add_favorite("111", "fish", "goldfish")
    await db.add_favorite("111", "fish", "goldfish")
    favs = await db.get_favorites("111", "fish")
    assert len(favs) == 1

@pytest.mark.asyncio
async def test_get_favorites_all_types(db):
    await db.add_favorite("111", "fish", "goldfish")
    await db.add_favorite("111", "location", "ocean")
    favs = await db.get_favorites("111")
    assert len(favs) == 2

@pytest.mark.asyncio
async def test_remove_favorite(db):
    await db.add_favorite("111", "fish", "goldfish")
    await db.remove_favorite("111", "fish", "goldfish")
    favs = await db.get_favorites("111", "fish")
    assert len(favs) == 0

@pytest.mark.asyncio
async def test_remove_favorite_noop_when_missing(db):
    await db.remove_favorite("111", "fish", "nonexistent")  # no error


# --- add_history / get_history ---

@pytest.mark.asyncio
async def test_add_and_get_history(db):
    await db.add_history("111", "fish", "goldfish")
    rows = await db.get_history("111", "fish")
    assert len(rows) == 1
    assert rows[0]["item_id"] == "goldfish"

@pytest.mark.asyncio
async def test_add_history_prunes_to_20(db):
    for i in range(25):
        await db.add_history("111", "fish", f"fish_{i}")
    rows = await db.get_history("111", "fish")
    assert len(rows) == 20

@pytest.mark.asyncio
async def test_get_history_returns_newest_first(db):
    await db.add_history("111", "fish", "first")
    await db.add_history("111", "fish", "second")
    rows = await db.get_history("111", "fish")
    assert rows[0]["item_id"] == "second"

@pytest.mark.asyncio
async def test_get_history_respects_limit(db):
    for i in range(10):
        await db.add_history("111", "fish", f"fish_{i}")
    rows = await db.get_history("111", "fish", limit=3)
    assert len(rows) == 3

@pytest.mark.asyncio
async def test_add_history_stores_data(db):
    await db.add_history("111", "simulation", "river", data='{"failChance": 12.5}')
    rows = await db.get_history("111", "simulation")
    assert rows[0]["data"] == '{"failChance": 12.5}'

@pytest.mark.asyncio
async def test_add_history_data_defaults_none(db):
    await db.add_history("111", "fish", "goldfish")
    rows = await db.get_history("111", "fish")
    assert rows[0]["data"] is None

@pytest.mark.asyncio
async def test_history_scoped_by_type(db):
    await db.add_history("111", "fish", "goldfish")
    await db.add_history("111", "location", "ocean")
    fish_rows = await db.get_history("111", "fish")
    assert all(r["type"] == "fish" for r in fish_rows)

@pytest.mark.asyncio
async def test_add_history_prune_keeps_newest_ids(db):
    for i in range(25):
        await db.add_history("111", "fish", f"fish_{i}")
    rows = await db.get_history("111", "fish")
    assert len(rows) == 20
    item_ids = [r["item_id"] for r in rows]
    # The 5 oldest (fish_0..fish_4) should be pruned; newest 20 should survive
    for i in range(5, 25):
        assert f"fish_{i}" in item_ids, f"fish_{i} was incorrectly pruned"
    for i in range(5):
        assert f"fish_{i}" not in item_ids, f"fish_{i} should have been pruned"
