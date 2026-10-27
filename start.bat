@echo off
rem Пивоварня: база в Docker, посредник (server) в свёрнутом окне, интерфейс отдельным окном Edge.
rem Интерфейс берётся из сборки web\.output\public (cd web && npm run generate).
rem Закрыть посредника — закрыть его окно «brewapp bridge» на панели задач.
cd /d "%~dp0server"
rem база нужна посреднику; контейнерный посредник занял бы тот же порт 8000 — останавливаем его
docker compose up -d db
docker compose stop bridge >nul 2>&1
start "brewapp bridge" /min .venv\Scripts\python.exe -m bridge.server
timeout /t 4 /nobreak >nul
start "" msedge --app=http://127.0.0.1:8000 --window-size=1400,1000
