#!/usr/bin/env bash
# Avisos para el blitz de BTC de IQ Option (3 min, pago 86 %) en cuenta DEMO (Estudio 42) + panel web.
# Abre http://127.0.0.1:8765/blitz. Para detener: Ctrl+C en esta ventana (detiene ambos procesos).
# Si IQ Option muestra otro pago, páselo:  scripts/iniciar_blitz.sh --pago 85
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
TBOT=.venv/bin/tbot
if [ ! -f config/senal_blitz.json ]; then
  echo "Falta el modelo congelado. Ejecute una vez: $TBOT blitz entrenar"
  read -rp "Enter para cerrar"; exit 1
fi
mkdir -p runtime/blitz
"$TBOT" blitz vivo --runtime runtime/blitz "$@" &
LOOP=$!
"$TBOT" serve --blitz-runtime runtime/blitz &
SERVE=$!
trap 'echo; echo "Deteniendo..."; kill $LOOP $SERVE 2>/dev/null; wait' INT TERM
(sleep 4; xdg-open http://127.0.0.1:8765/blitz >/dev/null 2>&1) &
echo "Blitz (pid $LOOP) y panel (pid $SERVE): http://127.0.0.1:8765/blitz - Ctrl+C para detener."
wait
