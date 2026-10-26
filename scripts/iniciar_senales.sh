#!/usr/bin/env bash
# Señales anticipadas de BTC/USD 1 minuto para cuenta DEMO (Estudio 16) + panel web.
# Abre http://127.0.0.1:8765/senales. Para detener: Ctrl+C en esta ventana (detiene ambos procesos).
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
TBOT=.venv/bin/tbot
if [ ! -f config/senal_anticipada.json ]; then
  echo "Falta el modelo congelado. Ejecute una vez: $TBOT senal entrenar"
  read -rp "Enter para cerrar"; exit 1
fi
mkdir -p runtime/senales
"$TBOT" senal vivo --runtime runtime/senales &
LOOP=$!
"$TBOT" serve --senal-runtime runtime/senales &
SERVE=$!
trap 'echo; echo "Deteniendo..."; kill $LOOP $SERVE 2>/dev/null; wait' INT TERM
(sleep 4; xdg-open http://127.0.0.1:8765/senales >/dev/null 2>&1) &
echo "Señales (pid $LOOP) y panel (pid $SERVE): http://127.0.0.1:8765/senales - Ctrl+C para detener."
wait
