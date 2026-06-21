import logging

import aiosqlite
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        logger.debug("Connecting to database %s", self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._run_migrations()

    async def close(self) -> None:
        logger.debug("Closing database connection")
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _run_migrations(self) -> None:
        migrations_dir = Path(__file__).parent.parent / "migrations"
        if not migrations_dir.exists():
            return
        files = sorted(migrations_dir.glob("*.sql"))
        if not files:
            return
        async with self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_version'"
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            await self._conn.execute(
                "CREATE TABLE _schema_version (version INTEGER PRIMARY KEY)"
            )
            await self._conn.commit()
        cursor = await self._conn.execute("SELECT MAX(version) FROM _schema_version")
        current = (await cursor.fetchone())[0] or 0
        for f in files:
            version = int(f.stem.split("_")[0])
            if version > current:
                logger.debug("Applying migration %s", f.name)
                async with aiosqlite.connect(self.db_path) as conn:
                    await conn.executescript(f.read_text())
                    await conn.execute(
                        "INSERT INTO _schema_version (version) VALUES (?)",
                        (version,),
                    )
                    await conn.commit()

    async def get_user(self, discord_id: str):
        logger.debug("DB get_user: %s", discord_id)
        async with self._conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def create_user(self, discord_id: str) -> None:
        logger.debug("DB create_user: %s", discord_id)
        await self._conn.execute(
            "INSERT OR IGNORE INTO users (discord_id) VALUES (?)", (discord_id,)
        )
        await self._conn.commit()

    async def update_user(self, discord_id: str, **fields) -> None:
        logger.debug("DB update_user: %s", discord_id)
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [discord_id]
        await self._conn.execute(
            f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?",
            values,
        )
        await self._conn.commit()

    async def get_or_create_user(self, discord_id: str):
        await self.create_user(discord_id)
        return await self.get_user(discord_id)

    async def add_favorite(self, discord_id: str, type: str, item_id: str) -> None:
        logger.debug("DB add_favorite: %s %s %s", discord_id, type, item_id)
        await self._conn.execute(
            "INSERT OR IGNORE INTO favorites (discord_id, type, item_id) VALUES (?, ?, ?)",
            (discord_id, type, item_id),
        )
        await self._conn.commit()

    async def remove_favorite(self, discord_id: str, type: str, item_id: str) -> None:
        logger.debug("DB remove_favorite: %s %s %s", discord_id, type, item_id)
        await self._conn.execute(
            "DELETE FROM favorites WHERE discord_id = ? AND type = ? AND item_id = ?",
            (discord_id, type, item_id),
        )
        await self._conn.commit()

    async def get_favorites(self, discord_id: str, type: str | None = None) -> list:
        logger.debug("DB get_favorites: %s type=%s", discord_id, type)
        if type is not None:
            async with self._conn.execute(
                "SELECT * FROM favorites WHERE discord_id = ? AND type = ? ORDER BY id",
                (discord_id, type),
            ) as cursor:
                return list(await cursor.fetchall())
        async with self._conn.execute(
            "SELECT * FROM favorites WHERE discord_id = ? ORDER BY type, id",
            (discord_id,),
        ) as cursor:
            return list(await cursor.fetchall())

    async def add_history(self, discord_id: str, type: str, item_id: str) -> None:
        logger.debug("DB add_history: %s %s %s", discord_id, type, item_id)
        await self._conn.execute(
            "INSERT INTO history (discord_id, type, item_id) VALUES (?, ?, ?)",
            (discord_id, type, item_id),
        )
        await self._conn.execute(
            """DELETE FROM history WHERE discord_id = ? AND type = ? AND id NOT IN (
                SELECT id FROM history WHERE discord_id = ? AND type = ?
                ORDER BY created_at DESC LIMIT 20
            )""",
            (discord_id, type, discord_id, type),
        )
        await self._conn.commit()

    async def get_history(self, discord_id: str, type: str, limit: int = 20) -> list:
        logger.debug("DB get_history: %s type=%s limit=%s", discord_id, type, limit)
        async with self._conn.execute(
            "SELECT * FROM history WHERE discord_id = ? AND type = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (discord_id, type, limit),
        ) as cursor:
            return list(await cursor.fetchall())
