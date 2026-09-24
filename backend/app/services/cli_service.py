"""Обёртка над SSH (asyncssh) и Telnet (telnetlib3).

Все публичные функции сериализуются по хосту: один OLT — одна
одновременная CLI-сессия. Это решает проблему, когда LTP-X закрывает
соединение при превышении лимита одновременных сессий.
"""
import asyncio
from contextlib import asynccontextmanager
from loguru import logger

try:
    import asyncssh
except ImportError:
    asyncssh = None  # type: ignore

try:
    import telnetlib3
except ImportError:
    telnetlib3 = None  # type: ignore


class CliError(RuntimeError):
    pass


# ----------------------------------------------------------------------
# Сериализация доступа к CLI по хосту
# ----------------------------------------------------------------------
_locks: dict[str, asyncio.Lock] = {}


def _get_lock(host: str) -> asyncio.Lock:
    lock = _locks.get(host)
    if lock is None:
        lock = asyncio.Lock()
        _locks[host] = lock
    return lock


# ----------------------------------------------------------------------
# SSH
# ----------------------------------------------------------------------
@asynccontextmanager
async def ssh_session(host: str, user: str, password: str, port: int = 22,
                      connect_timeout: float = 8.0):
    """Открывает SSH-сессию. Не блокирует — блокировка делается снаружи."""
    if asyncssh is None:
        raise CliError("Модуль asyncssh не установлен")
    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(
                host, port=port, username=user, password=password,
                known_hosts=None, encoding="utf-8",
            ),
            timeout=connect_timeout,
        )
    except asyncio.TimeoutError as e:
        raise CliError(f"SSH: таймаут подключения к {host}:{port}") from e
    except Exception as e:
        raise CliError(f"SSH: {e}") from e
    try:
        yield conn
    finally:
        conn.close()
        try:
            await conn.wait_closed()
        except Exception:
            pass


async def ssh_run_cmd(host: str, user: str, password: str, cmd: str,
                      port: int = 22, timeout: float = 15.0) -> str:
    async with _get_lock(host):
        async with ssh_session(host, user, password, port) as conn:
            try:
                res = await asyncio.wait_for(conn.run(cmd, check=False), timeout=timeout)
            except asyncio.TimeoutError as e:
                raise CliError(f"SSH: таймаут команды '{cmd}'") from e
            return (res.stdout or "") + (res.stderr or "")


async def ssh_run_script(host: str, user: str, password: str,
                         commands: list[str], port: int = 22,
                         timeout: float = 45.0) -> str:
    async with _get_lock(host):
        script = "\n".join(commands) + "\nexit\n"
        async with ssh_session(host, user, password, port) as conn:
            try:
                res = await asyncio.wait_for(
                    conn.run(script, check=False), timeout=timeout
                )
            except asyncio.TimeoutError as e:
                raise CliError(f"SSH: таймаут скрипта ({len(commands)} команд)") from e
            return (res.stdout or "") + (res.stderr or "")


# ----------------------------------------------------------------------
# Telnet
# ----------------------------------------------------------------------
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
            raise CliError(
                f"Telnet: не дождался {markers} за {timeout}с. Получено: {buf[:300]!r}"
            )
        try:
            chunk = await asyncio.wait_for(reader.read(256), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if not chunk:
            raise CliError(f"Telnet: соединение закрыто. Получено: {buf[:300]!r}")
        buf += chunk


async def _read_some(reader, timeout: float) -> str:
    buf = ""
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if not chunk:
            break
        buf += chunk
    return buf


@asynccontextmanager
async def telnet_session(host: str, user: str, password: str, port: int = 23,
                         connect_timeout: float = 8.0):
    """Открывает Telnet-сессию. Не блокирует — блокировка делается снаружи."""
    if telnetlib3 is None:
        raise CliError("Модуль telnetlib3 не установлен")
    try:
        reader, writer = await asyncio.wait_for(
            telnetlib3.open_connection(
                host, port,
                encoding="utf-8", encoding_errors="replace",
            ),
            timeout=connect_timeout,
        )
    except asyncio.TimeoutError as e:
        raise CliError(f"Telnet: таймаут подключения к {host}:{port}") from e
    except Exception as e:
        raise CliError(f"Telnet: {e}") from e

    try:
        await _read_until(reader, ["login:", "username:"], timeout=10)
        writer.write(user + "\r\n")
        await writer.drain()

        await _read_until(reader, ["password:"], timeout=10)
        writer.write(password + "\r\n")
        await writer.drain()

        await _read_until(reader, ["ltp-", "#", ">"], timeout=10)
        yield reader, writer
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def telnet_run_cmd(host: str, user: str, password: str, cmd: str,
                         port: int = 23, timeout: float = 15.0) -> str:
    async with _get_lock(host):
        async with telnet_session(host, user, password, port) as (reader, writer):
            writer.write(cmd + "\r\n")
            await writer.drain()
            await asyncio.sleep(0.5)
            return await _read_some(reader, timeout=timeout)


async def telnet_run_script(host: str, user: str, password: str,
                            commands: list[str], port: int = 23,
                            timeout: float = 45.0) -> str:
    async with _get_lock(host):
        async with telnet_session(host, user, password, port) as (reader, writer):
            chunks: list[str] = []
            for cmd in commands:
                writer.write(cmd + "\r\n")
                await writer.drain()
                await asyncio.sleep(0.7)
                chunks.append(await _read_some(reader, timeout=4.0))
            return "\n".join(chunks)


# ----------------------------------------------------------------------
# Универсальная проверка подключения
# ----------------------------------------------------------------------
async def test_cli(host: str, transport: str, user: str, password: str) -> tuple[bool, str | None]:
    async with _get_lock(host):
        try:
            if transport == "ssh":
                out = await ssh_run_cmd(host, user, password, "show version", timeout=12)
            else:
                out = await telnet_run_cmd(host, user, password, "show version", timeout=12)
            logger.debug(f"CLI {transport} {host}: получено {len(out)} байт")
            if not out.strip():
                return False, "Пустой ответ от OLT"
            if "LTP-" not in out and "version" not in out.lower():
                return False, f"Неожиданный ответ: {out[:300]!r}"
            return True, None
        except CliError as e:
            return False, str(e)
        except Exception as e:
            logger.exception("test_cli failed")
            return False, f"{type(e).__name__}: {e}"


# ----------------------------------------------------------------------
# Универсальный run_script
# ----------------------------------------------------------------------
async def run_script(transport: str, host: str, user: str, password: str,
                     commands: list[str], timeout: float = 45.0) -> str:
    if transport == "ssh":
        return await ssh_run_script(host, user, password, commands, timeout=timeout)
    else:
        return await telnet_run_script(host, user, password, commands, timeout=timeout)