@echo off
setlocal enabledelayedexpansion

cd /d %~dp0

echo ============================================
echo   LTP-GUI build script
echo ============================================
echo.

REM --- 1. Проверяем, что venv есть ---
if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] Не найден .venv. Создайте venv и установите зависимости.
  exit /b 1
)

REM --- 2. Собираем фронтенд ---
echo [1/4] Сборка фронтенда...
pushd ..\frontend
if not exist "node_modules" (
  echo [ERROR] node_modules не найден. Запустите "npm install" в frontend.
  popd
  exit /b 1
)
call npm run build
if errorlevel 1 (
  echo [ERROR] npm run build failed
  popd
  exit /b 1
)
popd

REM --- 3. Генерируем иконку (если ещё нет) ---
echo [2/4] Проверка иконки...
if not exist "..\assets\ltp-gui.ico" (
  echo Иконка не найдена, генерирую...
  call .venv\Scripts\activate
  python make_icon.py
  if errorlevel 1 (
    echo [WARN] Не удалось сгенерировать иконку, продолжаю без неё
  )
)

REM --- 4. Активируем venv ---
call .venv\Scripts\activate
if errorlevel 1 (
  echo [ERROR] Не удалось активировать venv
  exit /b 1
)

REM --- 5. PyInstaller ---
echo [3/4] PyInstaller: сборка LTP-GUI.exe...
if exist "dist\LTP-GUI" rmdir /S /Q "dist\LTP-GUI"
if exist "build\LTP-GUI" rmdir /S /Q "build\LTP-GUI"

set ICON_ARG=
if exist "..\assets\ltp-gui.ico" set ICON_ARG=--icon "..\assets\ltp-gui.ico"

pyinstaller --noconfirm --clean --name LTP-GUI ^
  %ICON_ARG% ^
  --add-data "app\static;app\static" ^
  --collect-submodules app ^
  --collect-all pysnmp ^
  --collect-all asyncssh ^
  --collect-all telnetlib3 ^
  --collect-all apscheduler ^
  --hidden-import win32crypt ^
  --hidden-import aiosqlite ^
  --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.lifespan.on ^
  app\__main__.py

if errorlevel 1 (
  echo [ERROR] PyInstaller failed
  exit /b 1
)

echo.
echo [4/4] Проверка результата:
if exist "dist\LTP-GUI\LTP-GUI.exe" (
  echo   OK: dist\LTP-GUI\LTP-GUI.exe
  echo.
  echo Следующий шаг: собрать инсталлятор через Inno Setup
  echo   - Открыть ..\installer.iss в Inno Setup Compiler
  echo   - Нажать Build - Compile
  echo   - Результат: ..\installer-output\LTP-GUI-Setup-1.0.0.exe
) else (
  echo   [ERROR] LTP-GUI.exe не найден
  exit /b 1
)

endlocal