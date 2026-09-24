from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "LTP-GUI"
APP_VERSION = "1.0.0"
APP_PORT = 8765
APP_HOST = "127.0.0.1"

# Папка данных:
#   Windows: %LOCALAPPDATA%\LTP-GUI\
#   Linux/Mac: ~/.ltp-gui/  (для отладки)
_local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
if _local:
    DATA_DIR = Path(_local) / "LTP-GUI"
else:
    DATA_DIR = Path.home() / ".ltp-gui"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "data.db"
LOG_PATH = LOG_DIR / "ltp.log"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LTP_GUI_")
    db_url: str = f"sqlite+aiosqlite:///{DB_PATH}"
    log_level: str = "INFO"


settings = Settings()