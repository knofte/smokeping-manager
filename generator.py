import os
import signal
from database import get_tree
from config import SMOKEPING_CONFIG_DIR, SMOKEPING_INCLUDE_FILE, SMOKEPING_PID_FILE


def generate_config():
    """Generate SmokePing Targets @include file from the database tree."""
    tree = get_tree()
    lines = [
        "# ==========================================",
        "# Managed by smokeping-manager — do not edit",
        "# ==========================================",
        "",
    ]
    _render_tree(tree, lines, depth=1)
    return "\n".join(lines) + "\n"


def _render_tree(nodes, lines, depth):
    """Recursively render tree nodes as SmokePing config."""
    prefix = "+" * depth
    for node in nodes:
        if node["type"] == "group":
            lines.append(f"{prefix} {node['name']}")
            lines.append(f"menu = {node['title']}")
            lines.append(f"title = {node['title']}")
            lines.append("")

            # Hosts in this group
            host_prefix = "+" * (depth + 1)
            for host in node.get("hosts", []):
                lines.append(f"{host_prefix} {host['name']}")
                lines.append(f"menu = {host['title']}")
                lines.append(f"title = {host['title']}")
                lines.append(f"host = {host['host']}")
                if host.get("probe") and host["probe"] != "FPing":
                    lines.append(f"probe = {host['probe']}")
                lines.append("")

            # Subgroups
            _render_tree(node.get("children", []), lines, depth + 1)


def generate_slave_config(slave_id):
    """Generate a SmokePing Targets config for a specific slave's assigned hosts."""
    from database import get_slave_hosts, get_slave, get_groups

    slave = get_slave(slave_id)
    if not slave:
        return ""

    hosts = get_slave_hosts(slave_id)
    if not hosts:
        return "# No targets assigned to this slave\n"

    # Build group structure from assigned hosts
    all_groups = {g["id"]: dict(g) for g in get_groups()}
    lines = [
        "# ==========================================",
        f"# Config for slave: {slave['display_name'] or slave['name']}",
        "# Managed by smokeping-manager — do not edit",
        "# ==========================================",
        "",
    ]

    # Group hosts by their group, build needed group paths
    groups_needed = {}
    for h in hosts:
        gid = h["group_id"]
        if gid not in groups_needed:
            groups_needed[gid] = []
        groups_needed[gid].append(dict(h))

    # For each group, build the full path and render
    rendered_groups = set()
    for gid, group_hosts in groups_needed.items():
        # Walk up to get the full group chain
        chain = []
        current_id = gid
        while current_id is not None:
            g = all_groups.get(current_id)
            if not g:
                break
            chain.insert(0, g)
            current_id = g["parent_id"]

        # Render each group in the chain (if not already rendered)
        for depth, grp in enumerate(chain, start=1):
            key = (grp["id"], depth)
            if key not in rendered_groups:
                prefix = "+" * depth
                lines.append(f"{prefix} {grp['name']}")
                lines.append(f"menu = {grp['title']}")
                lines.append(f"title = {grp['title']}")
                lines.append("")
                rendered_groups.add(key)

        # Render hosts at the correct depth
        host_depth = len(chain) + 1
        host_prefix = "+" * host_depth
        for h in group_hosts:
            lines.append(f"{host_prefix} {h['name']}")
            lines.append(f"menu = {h['title']}")
            lines.append(f"title = {h['title']}")
            lines.append(f"host = {h['host']}")
            if h.get("probe") and h["probe"] != "FPing":
                lines.append(f"probe = {h['probe']}")
            lines.append("")

    return "\n".join(lines) + "\n"


def write_config():
    """Write the generated config to the SmokePing include file."""
    config = generate_config()
    filepath = os.path.join(SMOKEPING_CONFIG_DIR, SMOKEPING_INCLUDE_FILE)
    os.makedirs(SMOKEPING_CONFIG_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(config)
    return filepath


def reload_smokeping():
    """Send HUP to SmokePing to reload config. Returns (success, message)."""
    try:
        with open(SMOKEPING_PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        return True, f"SmokePing (pid {pid}) reloaded"
    except FileNotFoundError:
        return False, f"PID file not found: {SMOKEPING_PID_FILE}"
    except ProcessLookupError:
        return False, "SmokePing process not running (stale PID file)"
    except PermissionError:
        return False, "Permission denied — run as root or add to smokeping group"
    except Exception as e:
        return False, str(e)
