@echo off
rem Inicia la observacion en vivo de BTC/USDT 1 minuto (SIN dinero real) y el panel web.
rem Doble clic para abrirla. Para detenerla, cierre las dos ventanas negras.
rem Si se cierra o el PC se reinicia, vuelva a hacer doble clic: recupera lo ya registrado.
chcp 65001 >nul
cd /d "%~dp0.."
if not exist ".venv\Scripts\tbot.exe" (
  echo No se encuentra .venv\Scripts\tbot.exe. Instale primero: python -m venv .venv  y  pip install -e ".[dev]"
  pause
  exit /b 1
)
if not exist "models\BTCUSDT_h1_gbm.pkl" (
  echo Falta el modelo. Ejecute: tbot data download --symbols BTCUSDT --start 2025-09-01 --end 2026-09-01
  echo y luego: tbot train --symbol BTCUSDT --horizon 1 --model gbm
  pause
  exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul
start "tbot live - observacion BTC 1 min (NO CERRAR)" cmd /k ".venv\Scripts\tbot.exe live --symbol BTCUSDT --horizon 1 --model gbm --runtime runtime/live"
start "tbot serve - panel" cmd /k ".venv\Scripts\tbot.exe serve --runtime runtime/live"
timeout /t 4 >nul
start "" "http://127.0.0.1:8765"
