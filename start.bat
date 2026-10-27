@echo off
rem Пивоварня: база в Docker, сервис и агент — в свёрнутых окнах, интерфейс отдельным окном Edge.
rem Интерфейс берётся из сборки web\.output\public (cd web && npm run generate).
rem Закрыть — закрыть окна «brewapp service» и «brewapp agent» на панели задач.
cd /d "%~dp0service"
rem база нужна сервису; сервис и агент в контейнерах заняли бы порт 8000 и подключение к пивоварне — останавливаем их
docker compose up -d db
docker compose stop service agent >nul 2>&1
start "brewapp service" /min .venv\Scripts\python.exe -m app.server
timeout /t 4 /nobreak >nul
start "brewapp agent" /min /d "%~dp0agent" "%~dp0agent\.venv\Scripts\python.exe" -m agent
start "" msedge --app=http://127.0.0.1:8000 --window-size=1400,1000
