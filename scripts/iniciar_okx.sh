#!/usr/bin/env bash
# Avisos para los event contracts de OKX «Up or Down 5min» (Estudios 54 y 55) + panel web. SIN DINERO REAL: solo anotar.
# Abre http://127.0.0.1:8765/okx. Para detener: Ctrl+C en esta ventana (detiene ambos procesos).
# ETH (por defecto):  scripts/iniciar_okx.sh --telegram      ETH y BTC:  scripts/iniciar_okx.sh --eth --btc --telegram
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
TBOT=.venv/bin/tbot
if [ ! -f config/senal_okx5_eth.json ] && [ ! -f config/senal_okx5_btc.json ]; then
  echo "Falta el modelo congelado. Ejecute una vez: $TBOT okx entrenar"
  read -rp "Enter para cerrar"; exit 1
fi
mkdir -p runtime/okx
"$TBOT" okx vivo --runtime runtime/okx "$@" &
LOOP=$!
"$TBOT" serve --okx-runtime runtime/okx &
SERVE=$!
trap 'echo; echo "Deteniendo..."; kill $LOOP $SERVE 2>/dev/null; wait' INT TERM
(sleep 4; xdg-open http://127.0.0.1:8765/okx >/dev/null 2>&1) &
echo "OKX (pid $LOOP) y panel (pid $SERVE): http://127.0.0.1:8765/okx - Ctrl+C para detener."
wait
