#!/usr/bin/env python3
"""SmokePing Manager Agent — runs on slave probe servers.

Polls the master for config, writes it locally, and reloads SmokePing.
Zero pip dependencies — uses only Python stdlib.

Usage:
    python3 smokeping_agent.py --master https://smokeping.example.com --key spm_abc123...

Environment variables (alternative to CLI args):
    SPM_MASTER_URL    Master server URL
    SPM_SLAVE_KEY     Slave API key
    SPM_CONFIG_PATH   Where to write the SmokePing config (default: /etc/smokeping/config.d/Targets)
    SPM_PID_FILE      SmokePing PID file (default: /var/run/smokeping/smokeping.pid)
    SPM_POLL_INTERVAL Poll interval in seconds (default: 60)
"""

import argparse
import json
import os
import signal
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser(description="SmokePing Manager Slave Agent")
    parser.add_argument("--master", default=os.environ.get("SPM_MASTER_URL", ""),
                        help="Master server URL")
    parser.add_argument("--key", default=os.environ.get("SPM_SLAVE_KEY", ""),
                        help="Slave API key")
    parser.add_argument("--config-path", default=os.environ.get("SPM_CONFIG_PATH", "/etc/smokeping/config.d/Targets"),
                        help="Path to write SmokePing config")
    parser.add_argument("--pid-file", default=os.environ.get("SPM_PID_FILE", "/var/run/smokeping/smokeping.pid"),
                        help="SmokePing PID file for HUP reload")
    parser.add_argument("--interval", type=int, default=int(os.environ.get("SPM_POLL_INTERVAL", "60")),
                        help="Poll interval in seconds")
    args = parser.parse_args()

    if not args.master or not args.key:
        print("ERROR: --master and --key are required")
        sys.exit(1)

    master = args.master.rstrip("/")
    headers = {"Authorization": f"Bearer {args.key}", "Content-Type": "application/json"}

    print("SmokePing Manager Agent")
    print(f"  Master: {master}")
    print(f"  Config: {args.config_path}")
    print(f"  Poll:   {args.interval}s")

    last_config_hash = None

    while True:
        try:
            # Fetch config from master
            config_data = api_get(f"{master}/api/v1/agent/config", headers)
            if config_data:
                config = config_data["data"]["config"]
                config_hash = config_data["data"]["config_hash"]

                if config_hash != last_config_hash:
                    # Config changed — write and reload
                    write_config(args.config_path, config)
                    reload_smokeping(args.pid_file)
                    last_config_hash = config_hash
                    print(f"  Config updated ({config_hash[:8]})")
                else:
                    pass  # No change

            # Send heartbeat
            smokeping_version = get_smokeping_version()
            api_post(f"{master}/api/v1/agent/heartbeat", headers, {
                "smokeping_version": smokeping_version,
            })

        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(args.interval)


def api_get(url, headers):
    """Make a GET request and return parsed JSON."""
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  Request failed: {e}")
        return None


def api_post(url, headers, data):
    """Make a POST request with JSON body."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def write_config(path, config):
    """Write the SmokePing config file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(config)


def reload_smokeping(pid_file):
    """Send HUP to SmokePing to reload config."""
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        print(f"  SmokePing reloaded (pid {pid})")
    except FileNotFoundError:
        print(f"  PID file not found: {pid_file}")
    except ProcessLookupError:
        print("  SmokePing not running (stale PID)")
    except PermissionError:
        print("  Permission denied sending HUP — run as root")


def get_smokeping_version():
    """Get the installed SmokePing version."""
    try:
        result = subprocess.run(
            ["smokeping", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
