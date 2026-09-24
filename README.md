# LTP-GUI

Web-интерфейс управления ONT на OLT Eltex LTP-4X/8X.

## Требования
- Windows 10/11 x64
- Python 3.11+
- Node.js 20+

## Первый запуск (разработка)
Двойной клик по `run_dev.bat`. Откройте http://localhost:5173

## Сборка для эксплуатации
1. `cd frontend && npm run build` — статика соберётся в `backend/app/static/`.
2. `cd backend && build_exe.bat` — получите `dist\LTP-GUI\LTP-GUI.exe`.
3. Ярлык на `LTP-GUI.exe`, приложение открывается в браузере автоматически.

## Что реализовано (спринт 1)
- [x] Список OLT (CRUD, статус, ping+SNMP)
- [x] Единые учётки в настройках (шифрование через Windows DPAPI)
- [x] Периодическая проверка доступности (ping+SNMP, 60 с)
- [x] Проверка подключения SSH/Telnet по кнопке

## Что дальше (спринт 2)
- [ ] SNMP-поллер состояния ONT и PON-портов
- [ ] CLI-поллер RSSI и SFP
- [ ] Список ONT и карточка ONT
- [ ] График RSSI