import sqlite3
from config import DATABASE


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title TEXT,
            parent_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES groups(id) ON DELETE CASCADE,
            UNIQUE(name, parent_id)
        );

        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title TEXT,
            host TEXT NOT NULL,
            group_id INTEGER NOT NULL,
            probe TEXT DEFAULT 'FPing',
            sort_order INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            UNIQUE(name, group_id)
        );
    """)
    db.commit()
    db.close()


# --- Group CRUD ---

def get_groups():
    db = get_db()
    groups = db.execute("SELECT * FROM groups ORDER BY sort_order, name").fetchall()
    db.close()
    return groups


def get_group(group_id):
    db = get_db()
    group = db.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    db.close()
    return group


def create_group(name, title=None, parent_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO groups (name, title, parent_id) VALUES (?, ?, ?)",
        (name, title or name, parent_id)
    )
    db.commit()
    db.close()


def update_group(group_id, name, title=None, parent_id=None):
    db = get_db()
    db.execute(
        "UPDATE groups SET name = ?, title = ?, parent_id = ? WHERE id = ?",
        (name, title or name, parent_id, group_id)
    )
    db.commit()
    db.close()


def delete_group(group_id):
    db = get_db()
    db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    db.commit()
    db.close()


# --- Host CRUD ---

def get_hosts(group_id=None):
    db = get_db()
    if group_id:
        hosts = db.execute(
            "SELECT * FROM hosts WHERE group_id = ? ORDER BY sort_order, name",
            (group_id,)
        ).fetchall()
    else:
        hosts = db.execute("SELECT * FROM hosts ORDER BY sort_order, name").fetchall()
    db.close()
    return hosts


def get_host(host_id):
    db = get_db()
    host = db.execute("SELECT * FROM hosts WHERE id = ?", (host_id,)).fetchone()
    db.close()
    return host


def create_host(name, host, group_id, title=None, probe="FPing"):
    db = get_db()
    db.execute(
        "INSERT INTO hosts (name, host, group_id, title, probe) VALUES (?, ?, ?, ?, ?)",
        (name, host, group_id, title or name, probe)
    )
    db.commit()
    db.close()


def update_host(host_id, name, host, group_id, title=None, probe="FPing", enabled=1):
    db = get_db()
    db.execute(
        "UPDATE hosts SET name = ?, host = ?, group_id = ?, title = ?, probe = ?, enabled = ? WHERE id = ?",
        (name, host, group_id, title or name, probe, enabled, host_id)
    )
    db.commit()
    db.close()


def delete_host(host_id):
    db = get_db()
    db.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
    db.commit()
    db.close()


# --- Tree helpers ---

def get_tree():
    """Build the full group/host tree for display and config generation."""
    db = get_db()
    groups = db.execute("SELECT * FROM groups ORDER BY sort_order, name").fetchall()
    hosts = db.execute("SELECT * FROM hosts WHERE enabled = 1 ORDER BY sort_order, name").fetchall()
    db.close()

    groups_by_parent = {}
    for g in groups:
        parent = g["parent_id"]
        if parent not in groups_by_parent:
            groups_by_parent[parent] = []
        groups_by_parent[parent].append(dict(g))

    hosts_by_group = {}
    for h in hosts:
        gid = h["group_id"]
        if gid not in hosts_by_group:
            hosts_by_group[gid] = []
        hosts_by_group[gid].append(dict(h))

    # Build lookup for parent chain (to construct SmokePing target paths)
    group_by_id = {g["id"]: dict(g) for g in groups}

    def get_group_path(group_id):
        """Build the dotted path for a group, e.g. 'Clients.Pepperstone'."""
        parts = []
        gid = group_id
        while gid is not None:
            g = group_by_id.get(gid)
            if not g:
                break
            parts.append(g["name"])
            gid = g["parent_id"]
        parts.reverse()
        return ".".join(parts)

    def build_subtree(parent_id):
        tree = []
        for g in groups_by_parent.get(parent_id, []):
            group_path = get_group_path(g["id"])
            host_list = []
            for h in hosts_by_group.get(g["id"], []):
                h_copy = dict(h)
                h_copy["target_path"] = f"{group_path}.{h['name']}"
                host_list.append(h_copy)
            node = {
                "type": "group",
                "id": g["id"],
                "name": g["name"],
                "title": g["title"],
                "path": group_path,
                "children": build_subtree(g["id"]),
                "hosts": host_list,
            }
            tree.append(node)
        return tree

    return build_subtree(None)
