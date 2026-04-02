-- Slave probe management
CREATE TABLE IF NOT EXISTS slaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    hostname TEXT NOT NULL,
    api_key_hash TEXT,
    api_key_prefix TEXT,
    status TEXT DEFAULT 'pending',
    last_seen_at TIMESTAMP,
    smokeping_version TEXT,
    location TEXT,
    is_local INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Which targets are assigned to which slaves
CREATE TABLE IF NOT EXISTS host_slaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER NOT NULL,
    slave_id INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE,
    FOREIGN KEY (slave_id) REFERENCES slaves(id) ON DELETE CASCADE,
    UNIQUE(host_id, slave_id)
);

CREATE INDEX IF NOT EXISTS idx_host_slaves_host ON host_slaves(host_id);
CREATE INDEX IF NOT EXISTS idx_host_slaves_slave ON host_slaves(slave_id);
