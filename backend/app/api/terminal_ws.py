"""WebSocket-прокси к CLI OLT через xterm.js.

Протокол обмена (JSON):
  Клиент → сервер:
    {"type": "input",  "data": "ls -l\r"}
    {"type": "resize", "cols": 120, "rows": 30}
  Сервер → клиент:
    {"type": "output", "data": "..."}
    {"type": "error",  "message": "..."}
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..db import SessionLocal
from ..models import Olt, Settings as SettingsModel
from ..security import decrypt

try:
    import asyncssh
except ImportError:
    asyncssh = None

try:
    import telnetlib3
except ImportError:
    telnetlib3 = None


router = APIRouter(tags=["terminal"])


@router.websocket("/ws/olts/{olt_id}/terminal")
async def terminal_ws(websocket: WebSocket, olt_id: int):
    await websocket.accept()

    async with SessionLocal() as session:
        olt = await session.get(Olt, olt_id)
        cfg = await session.get(SettingsModel, 1)

    if olt is None:
        await _send_error(websocket, "OLT не найден")
        await websocket.close()
        return
    if cfg is None or not cfg.cli_user or cfg.cli_password_enc is None:
        await _send_error(websocket, "Не заданы учётные данные CLI")
        await websocket.close()
        return

    password = decrypt(cfg.cli_password_enc) or ""

    try:
        if cfg.default_transport == "ssh":
            await _run_ssh_terminal(websocket, olt.ip, cfg.cli_user, password)
        else:
            await _run_telnet_terminal(websocket, olt.ip, cfg.cli_user, password)
    except Exception as e:
        logger.exception(f"terminal_ws olt={olt.ip}")
        await _send_error(websocket, f"{type(e).__name__}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _send_error(websocket: WebSocket, message: str):
    try:
        await websocket.send_json({"type": "error", "message": message})
    except Exception:
        pass


# ---- SSH ---------------------------------------------------------------

async def _run_ssh_terminal(websocket, host: str, user: str, password: str):
    if asyncssh is None:
        await _send_error(websocket, "asyncssh не установлен")
        return

    try:
        conn = await asyncssh.connect(
            host, username=user, password=password, known_hosts=None,
        )
    except Exception as e:
        await _send_error(websocket, f"SSH: {e}")
        return

    try:
        process = await conn.create_process(
            term_type="xterm",
            term_size=(120, 30),
        )
    except Exception as e:
        await _send_error(websocket, f"SSH create_process: {e}")
        try:
            conn.close()
            await conn.wait_closed()
        except Exception:
            pass
        return

    async def ws_to_ssh():
        try:
            while True:
                msg = await websocket.receive_json()
                mtype = msg.get("type")
                if mtype == "input":
                    process.stdin.write(msg.get("data", ""))
                elif mtype == "resize":
                    cols = max(20, min(400, int(msg.get("cols", 120))))
                    rows = max(5, min(200, int(msg.get("rows", 30))))
                    process.change_terminal_size(cols, rows)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"ws_to_ssh: {e}")

    async def ssh_to_ws():
        try:
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                await websocket.send_json({"type": "output", "data": chunk})
        except Exception as e:
            logger.debug(f"ssh_to_ws: {e}")

    tasks = [asyncio.create_task(ws_to_ssh()),
             asyncio.create_task(ssh_to_ws())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        try:
            conn.close()
            await conn.wait_closed()
        except Exception:
            pass


# ---- Telnet ------------------------------------------------------------

async def _run_telnet_terminal(websocket, host: str, user: str, password: str):
    if telnetlib3 is None:
        await _send_error(websocket, "telnetlib3 не установлен")
        return

    try:
        reader, writer = await telnetlib3.open_connection(
            host, 23, encoding="utf-8", encoding_errors="replace",
        )
    except Exception as e:
        await _send_error(websocket, f"Telnet: {e}")
        return

    # Логин
    try:
        await _read_until(reader, ["login:", "username:"], timeout=10)
        writer.write(user + "\r\n")
        await writer.drain()

        await _read_until(reader, ["password:"], timeout=10)
        writer.write(password + "\r\n")
        await writer.drain()

        prompt = await _read_until(reader, ["ltp-", "#", ">"], timeout=10)
        await websocket.send_json({"type": "output", "data": prompt})
    except Exception as e:
        await _send_error(websocket, f"Telnet auth: {e}")
        try:
            writer.close()
        except Exception:
            pass
        return

    async def ws_to_telnet():
        try:
            while True:
                msg = await websocket.receive_json()
                if msg.get("type") == "input":
                    writer.write(msg.get("data", ""))
                    await writer.drain()
                elif msg.get("type") == "resize":
                    # Telnet resize не поддерживаем
                    pass
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"ws_to_telnet: {e}")

    async def telnet_to_ws():
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                await websocket.send_json({"type": "output", "data": chunk})
        except Exception as e:
            logger.debug(f"telnet_to_ws: {e}")

    tasks = [asyncio.create_task(ws_to_telnet()),
             asyncio.create_task(telnet_to_ws())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        try:
            writer.close()
        except Exception:
            pass


async def _read_until(reader, markers: list[str], timeout: float) -> str:
    buf = ""
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    lowered = [m.lower() for m in markers]
    while True:
        for m in lowered:
            if m in buf.lower():
                return buf
        if loop.time() > end:
            raise TimeoutError(f"не дождался {markers}")
        try:
            chunk = await asyncio.wait_for(reader.read(256), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if not chunk:
            raise ConnectionError("соединение закрыто")
        buf += chunk