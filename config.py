import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database
DATABASE = os.environ.get("SPM_DATABASE", os.path.join(BASE_DIR, "smokeping-manager.db"))

# SmokePing integration
SMOKEPING_CONFIG_DIR = os.environ.get("SPM_CONFIG_DIR", "/etc/smokeping/config.d")
SMOKEPING_INCLUDE_FILE = os.environ.get("SPM_INCLUDE_FILE", "managed-targets")
SMOKEPING_PID_FILE = os.environ.get("SPM_PID_FILE", "/var/run/smokeping/smokeping.pid")
SMOKEPING_CGI_URL = os.environ.get("SPM_CGI_URL", "/smokeping/smokeping.cgi")

# Auth
SECRET_KEY = os.environ.get("SPM_SECRET_KEY", "change-me-in-production")
ADMIN_USER = os.environ.get("SPM_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("SPM_ADMIN_PASSWORD", "admin")
