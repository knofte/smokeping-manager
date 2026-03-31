import os
import subprocess

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def get_current_version():
    """Get the current commit hash and date."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%ai|%s"],
            cwd=APP_DIR, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|", 2)
            return {
                "hash": parts[0][:8],
                "hash_full": parts[0],
                "date": parts[1],
                "message": parts[2] if len(parts) > 2 else "",
            }
    except Exception:
        pass
    return None


def check_for_updates():
    """Fetch from remote and check if updates are available. Returns (has_updates, info)."""
    try:
        # Fetch latest from remote
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=APP_DIR, capture_output=True, text=True, timeout=30
        )

        # Count commits behind
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/master"],
            cwd=APP_DIR, capture_output=True, text=True, timeout=10
        )
        behind = int(result.stdout.strip()) if result.returncode == 0 else 0

        # Get latest remote commit info
        result = subprocess.run(
            ["git", "log", "origin/master", "-1", "--format=%H|%ai|%s"],
            cwd=APP_DIR, capture_output=True, text=True, timeout=10
        )
        remote_info = None
        if result.returncode == 0:
            parts = result.stdout.strip().split("|", 2)
            remote_info = {
                "hash": parts[0][:8],
                "date": parts[1],
                "message": parts[2] if len(parts) > 2 else "",
            }

        # Get log of pending commits
        pending = []
        if behind > 0:
            result = subprocess.run(
                ["git", "log", "--format=%h|%ai|%s", "HEAD..origin/master"],
                cwd=APP_DIR, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split("|", 2)
                        pending.append({
                            "hash": parts[0],
                            "date": parts[1],
                            "message": parts[2] if len(parts) > 2 else "",
                        })

        return behind > 0, {
            "behind": behind,
            "remote": remote_info,
            "pending": pending,
        }
    except Exception as e:
        return False, {"error": str(e)}


def apply_update():
    """Pull latest changes from remote. Returns (success, message)."""
    try:
        # Check for local modifications
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=APP_DIR, capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            return False, "Local modifications detected. Please commit or stash changes first."

        # Pull
        result = subprocess.run(
            ["git", "pull", "origin", "master"],
            cwd=APP_DIR, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)
