from flask import Blueprint, jsonify, request, g
from database import (
    get_tree, get_groups, get_group, create_group, update_group, delete_group,
    get_host, get_hosts, create_host, update_host, delete_host,
    get_users, get_user, create_user, delete_user,
    get_user_permissions, set_user_permissions,
    get_api_tokens, create_api_token, delete_api_token,
    get_audit_log,
)
from auth import (
    hash_password, generate_api_token as gen_token,
    filter_tree_for_user, hash_token,
)
from audit import log_action
from generator import generate_config, write_config, reload_smokeping
from graph_renderer import render_graph
from updater import get_current_version

import re

VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

api = Blueprint("api", __name__, url_prefix="/api/v1")


# --- Auth middleware ---

@api.before_request
def authenticate():
    """Authenticate every API request via Bearer token or session."""
    from database import get_user_by_token, get_user as db_get_user
    from flask import session

    user = None

    # Check Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer spm_"):
        token = auth_header[7:]
        token_h = hash_token(token)
        user = get_user_by_token(token_h)
        if user:
            g.auth_method = "token"

    # Fall back to session
    if not user and session.get("user_id"):
        user = db_get_user(session["user_id"])
        if user:
            g.auth_method = "session"

    if not user or not user.get("is_active", True):
        return jsonify({"error": {"code": "unauthorized", "message": "Authentication required"}}), 401

    g.current_user = user


def require_role(*roles):
    """Check current user has one of the specified roles."""
    if g.current_user["role"] not in roles:
        return jsonify({"error": {"code": "forbidden", "message": "Insufficient permissions"}}), 403
    return None


def require_write():
    """Write operations require pro edition."""
    from features import is_pro
    if not is_pro() and g.auth_method == "token":
        return jsonify({"error": {"code": "forbidden", "message": "Write API requires Pro edition"}}), 403
    return None


# --- System ---

@api.route("/system/status")
def system_status():
    version = get_current_version()
    groups = get_groups()
    hosts = get_hosts()
    return jsonify({"data": {
        "version": version,
        "groups": len(groups),
        "hosts": len(hosts),
        "edition": __import__("features").EDITION,
    }})


@api.route("/system/config-preview")
def config_preview():
    err = require_role("admin")
    if err:
        return err
    config = generate_config()
    return jsonify({"data": {"config": config}})


@api.route("/system/deploy", methods=["POST"])
def deploy():
    err = require_role("admin")
    if err:
        return err
    err = require_write()
    if err:
        return err
    try:
        filepath = write_config()
        success, msg = reload_smokeping()
        log_action("deploy", "system", details={"filepath": filepath, "reload": msg})
        return jsonify({"data": {"config_path": filepath, "reload": msg, "success": success}})
    except Exception as e:
        return jsonify({"error": {"code": "deploy_failed", "message": str(e)}}), 500


# --- Groups ---

@api.route("/groups")
def list_groups():
    fmt = request.args.get("format", "tree")
    if fmt == "tree":
        tree = get_tree()
        tree = filter_tree_for_user(tree, g.current_user)
        return jsonify({"data": tree})
    groups = get_groups()
    return jsonify({"data": [dict(g) for g in groups]})


@api.route("/groups/<int:group_id>")
def get_group_detail(group_id):
    group = get_group(group_id)
    if not group:
        return jsonify({"error": {"code": "not_found", "message": "Group not found"}}), 404
    return jsonify({"data": dict(group)})


@api.route("/groups", methods=["POST"])
def api_create_group():
    err = require_role("admin", "operator")
    if err:
        return err
    err = require_write()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    title = data.get("title", "").strip()
    parent_id = data.get("parent_id")

    if not name or not VALID_NAME.match(name):
        return jsonify({"error": {"code": "invalid_name", "message": "Invalid name"}}), 400

    try:
        create_group(name, title or name, parent_id)
        log_action("create", "group", entity_name=name)
        write_config()
        reload_smokeping()
        return jsonify({"data": {"name": name, "created": True}}), 201
    except Exception as e:
        return jsonify({"error": {"code": "create_failed", "message": str(e)}}), 400


@api.route("/groups/<int:group_id>", methods=["PUT"])
def api_update_group(group_id):
    err = require_role("admin", "operator")
    if err:
        return err
    err = require_write()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    title = data.get("title", "").strip()
    parent_id = data.get("parent_id")

    if not name or not VALID_NAME.match(name):
        return jsonify({"error": {"code": "invalid_name", "message": "Invalid name"}}), 400

    try:
        update_group(group_id, name, title or name, parent_id)
        log_action("update", "group", group_id, name)
        write_config()
        reload_smokeping()
        return jsonify({"data": {"id": group_id, "updated": True}})
    except Exception as e:
        return jsonify({"error": {"code": "update_failed", "message": str(e)}}), 400


@api.route("/groups/<int:group_id>", methods=["DELETE"])
def api_delete_group(group_id):
    err = require_role("admin", "operator")
    if err:
        return err
    err = require_write()
    if err:
        return err

    group = get_group(group_id)
    if not group:
        return jsonify({"error": {"code": "not_found", "message": "Group not found"}}), 404

    delete_group(group_id)
    log_action("delete", "group", group_id, group["name"])
    write_config()
    reload_smokeping()
    return jsonify({"data": {"id": group_id, "deleted": True}})


# --- Hosts ---

@api.route("/hosts")
def list_hosts():
    group_id = request.args.get("group_id", type=int)
    hosts = get_hosts(group_id)
    return jsonify({"data": [dict(h) for h in hosts]})


@api.route("/hosts/<int:host_id>")
def get_host_detail(host_id):
    host = get_host(host_id)
    if not host:
        return jsonify({"error": {"code": "not_found", "message": "Host not found"}}), 404
    return jsonify({"data": dict(host)})


@api.route("/hosts", methods=["POST"])
def api_create_host():
    err = require_role("admin", "operator")
    if err:
        return err
    err = require_write()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    host = data.get("host", "").strip()
    group_id = data.get("group_id")
    title = data.get("title", "").strip()
    probe = data.get("probe", "FPing").strip()

    if not name or not VALID_NAME.match(name):
        return jsonify({"error": {"code": "invalid_name", "message": "Invalid name"}}), 400
    if not host:
        return jsonify({"error": {"code": "missing_host", "message": "Host is required"}}), 400
    if not group_id:
        return jsonify({"error": {"code": "missing_group", "message": "group_id is required"}}), 400

    try:
        create_host(name, host, int(group_id), title or name, probe)
        log_action("create", "host", entity_name=name, details={"host": host})
        write_config()
        reload_smokeping()
        return jsonify({"data": {"name": name, "host": host, "created": True}}), 201
    except Exception as e:
        return jsonify({"error": {"code": "create_failed", "message": str(e)}}), 400


@api.route("/hosts/<int:host_id>", methods=["PUT"])
def api_update_host(host_id):
    err = require_role("admin", "operator")
    if err:
        return err
    err = require_write()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    host = data.get("host", "").strip()
    group_id = data.get("group_id")
    title = data.get("title", "").strip()
    probe = data.get("probe", "FPing").strip()
    enabled = data.get("enabled", 1)

    if not name or not VALID_NAME.match(name):
        return jsonify({"error": {"code": "invalid_name", "message": "Invalid name"}}), 400

    try:
        update_host(host_id, name, host, int(group_id), title or name, probe, enabled)
        log_action("update", "host", host_id, name)
        write_config()
        reload_smokeping()
        return jsonify({"data": {"id": host_id, "updated": True}})
    except Exception as e:
        return jsonify({"error": {"code": "update_failed", "message": str(e)}}), 400


@api.route("/hosts/<int:host_id>", methods=["DELETE"])
def api_delete_host(host_id):
    err = require_role("admin", "operator")
    if err:
        return err
    err = require_write()
    if err:
        return err

    host = get_host(host_id)
    if not host:
        return jsonify({"error": {"code": "not_found", "message": "Host not found"}}), 404

    delete_host(host_id)
    log_action("delete", "host", host_id, host["name"])
    write_config()
    reload_smokeping()
    return jsonify({"data": {"id": host_id, "deleted": True}})


@api.route("/hosts/<int:host_id>/graph")
def host_graph(host_id):
    """Render a graph for a specific host. Returns PNG image."""
    from flask import Response
    host = get_host(host_id)
    if not host:
        return jsonify({"error": {"code": "not_found", "message": "Host not found"}}), 404

    # Build target path from group hierarchy
    group = get_group(host["group_id"])
    if not group:
        return jsonify({"error": {"code": "not_found", "message": "Group not found"}}), 404

    # Build path by walking up group parents
    parts = [group["name"]]
    parent_id = group["parent_id"]
    while parent_id:
        parent = get_group(parent_id)
        if not parent:
            break
        parts.insert(0, parent["name"])
        parent_id = parent["parent_id"]
    target_path = ".".join(parts) + "." + host["name"]

    display_range = request.args.get("range", "3h")
    style = request.args.get("style", "classic")
    content_type, body = render_graph(target_path, display_range, style=style)
    return Response(body, content_type=content_type, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    })


# --- Users (admin only) ---

@api.route("/users")
def list_users():
    err = require_role("admin")
    if err:
        return err
    users = get_users()
    # Don't expose password hashes
    result = []
    for u in users:
        d = dict(u)
        d.pop("password_hash", None)
        result.append(d)
    return jsonify({"data": result})


@api.route("/users/<int:user_id>")
def get_user_detail(user_id):
    err = require_role("admin")
    if err:
        return err
    user = get_user(user_id)
    if not user:
        return jsonify({"error": {"code": "not_found", "message": "User not found"}}), 404
    d = dict(user)
    d.pop("password_hash", None)
    d["permissions"] = [dict(p) for p in get_user_permissions(user_id)]
    return jsonify({"data": d})


@api.route("/users", methods=["POST"])
def api_create_user():
    err = require_role("admin")
    if err:
        return err
    err = require_write()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip() or None
    role = data.get("role", "viewer")

    if not username or not password:
        return jsonify({"error": {"code": "missing_fields", "message": "Username and password required"}}), 400
    if role not in ("admin", "operator", "viewer"):
        return jsonify({"error": {"code": "invalid_role", "message": "Role must be admin, operator, or viewer"}}), 400

    try:
        pw_hash = hash_password(password)
        user_id = create_user(username, pw_hash, email, role)

        permissions = data.get("permissions", [])
        if permissions and role != "admin":
            perm_list = [(p, "view") for p in permissions]
            set_user_permissions(user_id, perm_list)

        log_action("create", "user", user_id, username, {"role": role})
        return jsonify({"data": {"id": user_id, "username": username, "role": role, "created": True}}), 201
    except Exception as e:
        return jsonify({"error": {"code": "create_failed", "message": str(e)}}), 400


@api.route("/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    err = require_role("admin")
    if err:
        return err
    err = require_write()
    if err:
        return err

    if user_id == g.current_user["id"]:
        return jsonify({"error": {"code": "cannot_delete_self", "message": "Cannot delete yourself"}}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": {"code": "not_found", "message": "User not found"}}), 404

    delete_user(user_id)
    log_action("delete", "user", user_id, user["username"])
    return jsonify({"data": {"id": user_id, "deleted": True}})


# --- API Tokens ---

@api.route("/tokens")
def list_tokens():
    tokens = get_api_tokens(g.current_user["id"])
    return jsonify({"data": [dict(t) for t in tokens]})


@api.route("/tokens", methods=["POST"])
def api_create_token():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": {"code": "missing_name", "message": "Token name required"}}), 400

    raw_token, token_hash, token_prefix = gen_token()
    create_api_token(g.current_user["id"], name, token_hash, token_prefix)
    log_action("create", "api_token", entity_name=name)

    return jsonify({"data": {
        "token": raw_token,
        "prefix": token_prefix,
        "name": name,
        "message": "Save this token — it won't be shown again"
    }}), 201


@api.route("/tokens/<int:token_id>", methods=["DELETE"])
def api_delete_token(token_id):
    delete_api_token(token_id, g.current_user["id"])
    return jsonify({"data": {"id": token_id, "deleted": True}})


# --- Audit Log ---

@api.route("/audit-log")
def list_audit():
    err = require_role("admin")
    if err:
        return err
    limit = request.args.get("limit", 100, type=int)
    entity_type = request.args.get("entity_type")
    user_id = request.args.get("user_id", type=int)
    entries = get_audit_log(limit=limit, entity_type=entity_type, user_id=user_id)
    return jsonify({"data": [dict(e) for e in entries]})
