# SmokePing Manager

Web-based target management for SmokePing. Add, edit and remove monitoring targets via a web UI instead of editing config files manually.

## Features

- **Group/host tree** — organize targets in nested groups (e.g. Clients > Pepperstone > web01)
- **Web UI** — add, edit, delete groups and hosts from your browser
- **Config generator** — generates SmokePing `@include` file with proper `+`/`++`/`+++` hierarchy
- **One-click reload** — sends HUP to SmokePing to apply changes
- **Self-update** — check for and apply updates from the web UI
- **Dark mode** UI

## Quick Install (Ubuntu/Debian)

Requires an existing SmokePing installation (`apt install smokeping`).

```bash
git clone https://github.com/knofte/smokeping-manager.git /opt/smokeping-manager
cd /opt/smokeping-manager
sudo bash install.sh
```

Then:
1. Edit `/etc/smokeping-manager.env` and change the admin password
2. `sudo systemctl start smokeping-manager`
3. Open `http://your-server:5000`
4. Login with admin / your-password

## How It Works

SmokePing Manager does **not** modify your existing SmokePing config. Instead, it manages a separate `managed-targets` file that SmokePing loads via `@include`. Your existing targets are untouched.

## License

MIT
