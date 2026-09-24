import argparse
import asyncio
import sys
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

# --- PyInstaller fix: обеспечить работу относительных импортов ---
# Если main.py запускается как скрипт (PyInstaller или python app/main.py),
# __package__ пустой, и `from .config` падает с ImportError.
# Добавляем корень backend/ в sys.path и выставляем __package__ = "app".
if __package__ in (None, ""):
    _here = Path(__file__).resolve()
    _root = _here.parent.parent  # backend/ — родитель app/
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    __package__ = "app"
# --- /fix ---

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .config import APP_NAME, APP_VERSION, APP_PORT, APP_HOST, LOG_DIR
from .db import init_db, SessionLocal
from .api import settings as api_settings
from .api import olts as api_olts
from .api import onts_search as api_onts_search
from .api import olts_system as api_olts_system
from .api import olts_vlans as api_olts_vlans
from .api import olts_uplinks as api_olts_uplinks
from .api import olts_alarms as api_olts_alarms
from .api import olts_macs as api_olts_macs
from .api import dashboard as api_dashboard
from .api import onts as api_onts
from .api import ont_actions as api_ont_actions
from .api import ont_manage as api_ont_manage
from .api import ont_edit as api_ont_edit
from .api import ont_services as api_ont_services
from .api import olt_backup as api_olt_backup
from .api import terminal_ws as api_terminal_ws
from .services.poller import start_poller, stop_poller
from .services.ont_poller import poll_all_olts
from .services.ont_state_poller import poll_all as poll_states_all
from .services.snmp_poller import poll_all as poll_macs_all
from .services.ont_config_poller import poll_all as poll_configs_all


# ---- CLI-аргументы -------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(prog="LTP-GUI", add_help=True)
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Не открывать браузер автоматически",
    )
    parser.add_argument(
        "--port", type=int, default=APP_PORT,
        help=f"TCP-порт HTTP-сервера (по умолчанию {APP_PORT})",
    )
    parser.add_argument(
        "--host", type=str, default=APP_HOST,
        help=f"Адрес прослушивания (по умолчанию {APP_HOST})",
    )
    args, _ = parser.parse_known_args()
    return args


ARGS = _parse_args()


# ---- Frozen-режим (PyInstaller) -----------------------------------------

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _static_dir() -> Path:
    """
    Папка со статикой фронта.
    - При обычном запуске: backend/app/static (рядом с main.py).
    - В PyInstaller onedir: <exe_dir>/app/static.
    - В PyInstaller onefile: sys._MEIPASS/app/static.
    """
    if _is_frozen():
        base = Path(sys.executable).parent
        candidate = base / "app" / "static"
        if candidate.exists():
            return candidate
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "app" / "static"
    return Path(__file__).parent / "static"


# ---- Настройка логов -----------------------------------------------------

def _setup_logging():
    try:
        logger.add(
            LOG_DIR / "ltp.log",
            rotation="10 MB",
            retention="30 days",
            level="INFO",
            enqueue=True,
            encoding="utf-8",
            backtrace=False,
            diagnose=False,
        )
    except Exception as e:
        print(f"[WARN] Не удалось инициализировать файловый лог: {e}", file=sys.stderr)


# ---- Lifespan -----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logger.info(f"{APP_NAME} v{APP_VERSION} запускается…")

    await init_db()
    start_poller()

    ont_scheduler = AsyncIOScheduler(timezone="UTC")

    async def _ont_tick():
        try:
            result = await poll_states_all(SessionLocal, concurrency=3)
            total = sum(v for v in result.values()) if result else 0
            if total == 0:
                logger.warning("SNMP-поллер ONT вернул 0, fallback на CLI")
                await poll_all_olts(SessionLocal, concurrency=3)
        except asyncio.CancelledError:
            logger.debug("ONT tick cancelled (shutdown)")
            return
        except Exception as e:
            logger.exception(f"ONT tick: {e}")

    ont_scheduler.add_job(
        _ont_tick, "interval", seconds=120, id="ont_poll",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
        coalesce=True,
    )
    ont_scheduler.add_job(
        _ont_tick, "date", run_date=datetime.utcnow(),
        id="ont_poll_first", replace_existing=True,
    )
    ont_scheduler.start()
    logger.info("ONT-поллер запущен, интервал 120 с")

    mac_scheduler = AsyncIOScheduler(timezone="UTC")

    async def _mac_tick():
        try:
            await poll_macs_all(SessionLocal, concurrency=1)
        except asyncio.CancelledError:
            logger.debug("MAC tick cancelled (shutdown)")
            return
        except Exception as e:
            logger.exception(f"MAC tick: {e}")

    mac_scheduler.add_job(
        _mac_tick, "interval", minutes=5, id="mac_poll",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
        coalesce=True,
    )
    mac_scheduler.add_job(
        _mac_tick, "date", run_date=datetime.utcnow(),
        id="mac_poll_first", replace_existing=True,
    )
    mac_scheduler.start()
    logger.info("MAC-поллер запущен, интервал 5 мин")

    config_scheduler = AsyncIOScheduler(timezone="UTC")

    async def _config_tick():
        try:
            await poll_configs_all(SessionLocal, concurrency=1)
        except asyncio.CancelledError:
            logger.debug("Config tick cancelled (shutdown)")
            return
        except Exception as e:
            logger.exception(f"Config tick: {e}")

    config_scheduler.add_job(
        _config_tick, "interval", minutes=15, id="config_poll",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
        coalesce=True,
    )
    config_scheduler.add_job(
        _config_tick, "date", run_date=datetime.utcnow(),
        id="config_poll_first", replace_existing=True,
    )
    config_scheduler.start()
    logger.info("Config-поллер запущен, интервал 15 мин")

    if not ARGS.no_browser:
        url = f"http://{ARGS.host}:{ARGS.port}"
        try:
            webbrowser.open(url)
            logger.info(f"Открываю браузер: {url}")
        except Exception as e:
            logger.warning(f"Не удалось открыть браузер: {e}")

    logger.info(f"{APP_NAME} запущен на http://{ARGS.host}:{ARGS.port}")
    try:
        yield
    finally:
        try:
            ont_scheduler.shutdown(wait=True)
        except Exception as e:
            logger.warning(f"ont_scheduler.shutdown: {e}")
        try:
            mac_scheduler.shutdown(wait=True)
        except Exception as e:
            logger.warning(f"mac_scheduler.shutdown: {e}")
        try:
            config_scheduler.shutdown(wait=True)
        except Exception as e:
            logger.warning(f"config_scheduler.shutdown: {e}")
        try:
            stop_poller()
        except Exception as e:
            logger.warning(f"stop_poller: {e}")
        await asyncio.sleep(0.3)
        logger.info(f"{APP_NAME} остановлен")


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        f"http://127.0.0.1:{ARGS.port}",
        f"http://localhost:{ARGS.port}",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_settings.router)
app.include_router(api_olts.router)
app.include_router(api_olts_system.router)
app.include_router(api_olts_vlans.router)
app.include_router(api_olts_uplinks.router)
app.include_router(api_olts_alarms.router)
app.include_router(api_olts_macs.router)
app.include_router(api_dashboard.router)
app.include_router(api_onts.router)
app.include_router(api_onts_search.router)
app.include_router(api_ont_actions.router)
app.include_router(api_ont_manage.router)
app.include_router(api_ont_edit.router)
app.include_router(api_ont_services.router)
app.include_router(api_olt_backup.router)
app.include_router(api_terminal_ws.router)


@app.get("/api/health")
async def health():
    return {"app": APP_NAME, "version": APP_VERSION, "ok": True}


static_dir = _static_dir()
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    logger.info(f"Static: {static_dir}")
else:
    logger.warning(f"Static dir not found: {static_dir}")


if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"Starting uvicorn on {ARGS.host}:{ARGS.port} "
        f"(frozen={_is_frozen()}, reload=False)"
    )
    uvicorn.run(
        app,
        host=ARGS.host,
        port=ARGS.port,
        reload=False,
        log_level="info",
        access_log=False,
    )