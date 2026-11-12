"""Entorno de pruebas: debe importarse ANTES que `bot` para que no toque datos reales."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="bot-tests-")
os.environ["TELEGRAM_TOKEN"] = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_0123456789"
os.environ["GROUP_ID"] = "-1001234567890"
os.environ["BOT_OWNER_ID"] = "1"
os.environ["ADMIN_IDS"] = ""
