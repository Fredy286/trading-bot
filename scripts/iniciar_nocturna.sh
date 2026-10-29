#!/usr/bin/env bash
# Reversión nocturna en divisas para cuenta DEMO (Estudios 25, 27 y 28) + panel web.
# Abre http://127.0.0.1:8765/nocturna. Para detener: Ctrl+C en esta ventana (detiene ambos procesos).
# Ventana: la que eligió el Estudio 28 (o forzarla con --ventana utc | nueva_york).
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
TBOT=.venv/bin/tbot
mkdir -p runtime/nocturna
"$TBOT" nocturna --runtime runtime/nocturna "$@" &
LOOP=$!
"$TBOT" serve --nocturna-runtime runtime/nocturna &
SERVE=$!
trap 'echo; echo "Deteniendo..."; kill $LOOP $SERVE 2>/dev/null; wait' INT TERM
(sleep 4; xdg-open http://127.0.0.1:8765/nocturna >/dev/null 2>&1) &
echo "Señales nocturnas (pid $LOOP) y panel (pid $SERVE): http://127.0.0.1:8765/nocturna - Ctrl+C para detener."
wait
