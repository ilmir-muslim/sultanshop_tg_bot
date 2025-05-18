from curses.ascii import DEL
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GROUPS_FILE = BASE_DIR / "data" / "groups.json"
ADMIN_FILE = BASE_DIR / "data" / "admins.json"
DELIVERERS_FILE = BASE_DIR / "data" / "deliverers.json"