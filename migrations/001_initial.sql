CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    discord_id TEXT PRIMARY KEY,
    fishing_rod TEXT DEFAULT 'Wooden Rod',
    current_tool TEXT,
    current_bait TEXT,
    fishing_skill INTEGER DEFAULT 0,
    luck_skill INTEGER DEFAULT 0,
    efficiency_skill INTEGER DEFAULT 0,
    prestige INTEGER DEFAULT 0,
    coins INTEGER DEFAULT 0,
    boss_unlock INTEGER DEFAULT 0,
    mythical_unlock INTEGER DEFAULT 0,
    favorite_fish TEXT,
    favorite_location TEXT,
    favorite_tool TEXT,
    favorite_bait TEXT,
    current_weather TEXT,
    current_event TEXT,
    simulator_presets TEXT,
    notification_prefs TEXT,
    timezone TEXT DEFAULT 'UTC',
    theme TEXT DEFAULT 'dark',
    compact_mode INTEGER DEFAULT 0,
    language TEXT DEFAULT 'en',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('fish','location','tool','bait','simulation','command')),
    item_id TEXT,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('fish','location','tool','bait')),
    item_id TEXT NOT NULL,
    UNIQUE(discord_id, type, item_id)
);

CREATE INDEX IF NOT EXISTS idx_history_discord ON history(discord_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_favorites_discord ON favorites(discord_id, type);
