@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo ============================================
echo   LTP-GUI - запуск в режиме разработки
echo ============================================
echo.

REM --- Поиск Python: сначала py, потом python ---
set PYTHON=
where py >nul 2>nul && set PYTHON=py
if "%PYTHON%"=="" (
  where python >nul 2>nul && set PYTHON=python
)
if "%PYTHON%"=="" (
  echo [ОШИБКА] Python не найден в PATH.
  echo.
  echo Установите Python 3.11+:
  echo   https://www.python.org/downloads/windows/
  echo ВАЖНО: при установке отметьте "Add python.exe to PATH".
  echo После установки ЗАКРОЙТЕ это окно и откройте заново.
  echo.
  pause
  exit /b 1
)
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do set PYVER=%%v
echo [OK] %PYVER% (команда: %PYTHON%)

REM --- Поиск npm ---
where npm >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ОШИБКА] npm не найден в PATH.
  echo.
  echo Установите Node.js 20 LTS:
  echo   https://nodejs.org/en/download
  echo Возьмите "Windows Installer (.msi) 64-bit".
  echo После установки ЗАКРОЙТЕ это окно и откройте заново.
  echo.
  pause
  exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODEVER=%%v
echo [OK] Node.js %NODEVER%
echo.

REM --- Backend: venv ---
pushd backend
if not exist .venv\Scripts\python.exe (
  echo [1/4] Создаю Python venv...
  %PYTHON% -m venv .venv
  if errorlevel 1 (
    echo [ОШИБКА] Не удалось создать venv
    popd ^& pause ^& exit /b 1
  )
  echo [2/4] Устанавливаю backend-зависимости (может занять пару минут)...
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -e .[windows]
  if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить backend-зависимости
    popd ^& pause ^& exit /b 1
  )
) else (
  echo [OK] backend venv уже создан
  call .venv\Scripts\activate.bat
)
popd

REM --- Frontend: npm install ---
pushd frontend
if not exist node_modules (
  echo [3/4] Устанавливаю npm-зависимости (может занять минуту)...
  call npm install
  if errorlevel 1 (
    echo [ОШИБКА] npm install провалился
    popd ^& pause ^& exit /b 1
  )
) else (
  echo [OK] frontend node_modules уже установлен
)
popd

REM --- Запуск ---
echo.
echo [4/4] Запускаю backend и frontend...
echo.
start "LTP-GUI backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate.bat && python -m app.main"
timeout /t 3 /nobreak >nul
start "LTP-GUI frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Готово. Через 5-10 секунд откройте http://localhost:5173
echo Для остановки закройте оба открывшихся окна cmd.
echo.
pause