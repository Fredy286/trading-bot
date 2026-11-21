#!/usr/bin/env bash
# El «gran bot» de práctica (idea 7 de docs/10): junta los modelos congelados con su metamodelo congelado.
#   scripts/iniciar_gran.sh blitz   → blitz de BTC de IQ Option (CUENTA DEMO), 8 modelos; panel /gran-blitz
#                                     (solo avisa con IQ abierto: domingo 22:00 → viernes 17:00 de Bogotá)
#   scripts/iniciar_gran.sh okx5    → contratos de 5 min de OKX, ETH y BTC, 6 modelos; panel /gran-okx5 (solo anotar)
#   scripts/iniciar_gran.sh okx15   → contratos de 15 min de OKX, ETH y BTC, 8 modelos; panel /gran-okx15 (solo anotar)
# Avisos también en el celular (Telegram del .env): añada --telegram. Para detener: Ctrl+C (detiene ambos procesos).
# Nunca dinero real: las confirmaciones con datos nuevos son en enero y abril de 2027 (Estudios 64, 68 y 69).
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
TBOT=.venv/bin/tbot
PROD=${1:-blitz}
shift || true
case "$PROD" in
  blitz) CMD=("$TBOT" blitz vivo --gran --runtime runtime/gran_blitz) ;;
  okx5) CMD=("$TBOT" okx vivo --gran --dur 5 --runtime runtime/gran_okx5) ;;
  okx15) CMD=("$TBOT" okx vivo --gran --dur 15 --runtime runtime/gran_okx15) ;;
  *) echo "Uso: $0 blitz|okx5|okx15 [--telegram]"; read -rp "Enter para cerrar"; exit 1 ;;
esac
RUTA="gran-$PROD"
mkdir -p "runtime/gran_$PROD"
"${CMD[@]}" "$@" &
LOOP=$!
"$TBOT" serve &
SERVE=$!
trap 'echo; echo "Deteniendo..."; kill $LOOP $SERVE 2>/dev/null; wait' INT TERM
(sleep 6; xdg-open "http://127.0.0.1:8765/$RUTA" >/dev/null 2>&1) &
echo "Gran bot $PROD (pid $LOOP) y panel (pid $SERVE): http://127.0.0.1:8765/$RUTA - Ctrl+C para detener."
wait
