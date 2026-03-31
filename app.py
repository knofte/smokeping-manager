import re
import functools
from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import (
    init_db, get_tree, get_groups, get_group, create_group, update_group, delete_group,
    get_host, create_host, update_host, delete_host
)
from generator import generate_config, write_config, reload_smokeping
from updater import get_current_version, check_for_updates, apply_update
from config import SECRET_KEY, ADMIN_USER, ADMIN_PASSWORD

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Sanitize names for SmokePing (alphanumeric + underscore only)
VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Invalid credentials", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    tree = get_tree()
    groups = get_groups()
    return render_template("index.html", tree=tree, groups=groups)


# --- Group routes ---

@app.route("/group/add", methods=["POST"])
@login_required
def add_group():
    name = request.form.get("name", "").strip()
    title = request.form.get("title", "").strip()
    parent_id = request.form.get("parent_id") or None

    if not name or not VALID_NAME.match(name):
        flash("Invalid name. Use letters, numbers, underscore. Must start with a letter.", "error")
        return redirect(url_for("index"))

    if parent_id:
        parent_id = int(parent_id)

    try:
        create_group(name, title or name, parent_id)
        flash(f"Group '{name}' created", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("index"))


@app.route("/group/<int:group_id>/edit", methods=["POST"])
@login_required
def edit_group(group_id):
    name = request.form.get("name", "").strip()
    title = request.form.get("title", "").strip()
    parent_id = request.form.get("parent_id") or None

    if not name or not VALID_NAME.match(name):
        flash("Invalid name.", "error")
        return redirect(url_for("index"))

    if parent_id:
        parent_id = int(parent_id)
        if parent_id == group_id:
            flash("A group cannot be its own parent.", "error")
            return redirect(url_for("index"))

    try:
        update_group(group_id, name, title or name, parent_id)
        flash(f"Group '{name}' updated", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("index"))


@app.route("/group/<int:group_id>/delete", methods=["POST"])
@login_required
def remove_group(group_id):
    group = get_group(group_id)
    if group:
        delete_group(group_id)
        flash(f"Group '{group['name']}' deleted (including all hosts and subgroups)", "success")
    return redirect(url_for("index"))


# --- Host routes ---

@app.route("/host/add", methods=["POST"])
@login_required
def add_host():
    name = request.form.get("name", "").strip()
    title = request.form.get("title", "").strip()
    host = request.form.get("host", "").strip()
    group_id = request.form.get("group_id")
    probe = request.form.get("probe", "FPing").strip()

    if not name or not VALID_NAME.match(name):
        flash("Invalid name. Use letters, numbers, underscore. Must start with a letter.", "error")
        return redirect(url_for("index"))

    if not host:
        flash("Host (IP or hostname) is required.", "error")
        return redirect(url_for("index"))

    if not group_id:
        flash("Please select a group.", "error")
        return redirect(url_for("index"))

    try:
        create_host(name, host, int(group_id), title or name, probe)
        flash(f"Host '{name}' ({host}) added", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("index"))


@app.route("/host/<int:host_id>/edit", methods=["POST"])
@login_required
def edit_host(host_id):
    name = request.form.get("name", "").strip()
    title = request.form.get("title", "").strip()
    host = request.form.get("host", "").strip()
    group_id = request.form.get("group_id")
    probe = request.form.get("probe", "FPing").strip()
    enabled = 1 if request.form.get("enabled") else 0

    if not name or not VALID_NAME.match(name):
        flash("Invalid name.", "error")
        return redirect(url_for("index"))

    try:
        update_host(host_id, name, host, int(group_id), title or name, probe, enabled)
        flash(f"Host '{name}' updated", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("index"))


@app.route("/host/<int:host_id>/delete", methods=["POST"])
@login_required
def remove_host(host_id):
    host = get_host(host_id)
    if host:
        delete_host(host_id)
        flash(f"Host '{host['name']}' deleted", "success")
    return redirect(url_for("index"))


# --- Config generation & reload ---

@app.route("/config/preview")
@login_required
def preview_config():
    config = generate_config()
    return render_template("preview.html", config=config)


@app.route("/config/deploy", methods=["POST"])
@login_required
def deploy_config():
    try:
        filepath = write_config()
        flash(f"Config written to {filepath}", "success")

        if request.form.get("reload"):
            success, msg = reload_smokeping()
            if success:
                flash(msg, "success")
            else:
                flash(msg, "error")
    except Exception as e:
        flash(f"Deploy failed: {e}", "error")
    return redirect(url_for("index"))


# --- Update routes ---

@app.route("/update")
@login_required
def update_page():
    current = get_current_version()
    has_updates, info = check_for_updates()
    return render_template("update.html", current=current, has_updates=has_updates, info=info)


@app.route("/update/apply", methods=["POST"])
@login_required
def do_update():
    success, message = apply_update()
    if success:
        flash(f"Updated successfully. Restart the service to apply. {message}", "success")
    else:
        flash(f"Update failed: {message}", "error")
    return redirect(url_for("update_page"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
