# Contexto del proyecto (léelo antes de trabajar)

Este archivo es el traspaso desde la sesión en la nube (2026-09-30) al trabajo local. El usuario
(Fredy, Colombia, zona America/Bogota) no es experto en trading ni en programación: explica en
español, sin jerga, y pide confirmación antes de acciones irreversibles.

## Objetivo del usuario

Investigar si se puede anticipar el movimiento de divisas y otros instrumentos (interés inicial:
opciones de 1 minuto con meta de 80 % de acierto), emitir alertas fundamentadas y, solo en una
Fase 2 y bajo condiciones estrictas, ejecutar automáticamente.

## Reglas innegociables (del usuario)

- No prometer tasas de acierto ni inventar probabilidades; si no hay evidencia, decir «sin señal».
- Distinguir acierto de rentabilidad neta (pago, spread, comisiones, deslizamiento, empates).
- Nada de información futura en entrenamiento, selección o simulación.
- No simular haber consultado noticias, operado ni probado integraciones que no se probaron.
- **Nunca operar con dinero real** sin autorización expresa y específica. Hoy: solo simulado/demo.
- Aprender de los errores: documentarlos en `docs/04_registro_de_errores.md`.
- Preferencias: analizar lo existente antes de crear archivos (evitar duplicados); en interfaces,
  paleta de colores coherente (el panel usa neutros pizarra + un acento azul + ámbar para experimental).

## Qué se hizo (todo está en este repositorio)

1. **Fase 1A** — `docs/01_informe_investigacion_fase1a.md`: literatura, fuentes, regulación (SFC),
   hipótesis H1–H7 y protocolo **pre-registrado** (congelado en git antes de ver datos), con la
   Enmienda 1 (HistData en vez de Dukascopy en GitHub) y la Aclaración 1 (criterio estricto del
   periodo bloqueado).
2. **Fase 1B** — estudio con datos reales 2021–2026 ejecutado en GitHub Actions
   (`.github/workflows/research.yml`): 6 instrumentos (EUR/USD, GBP/USD, USD/JPY, AUD/USD, XAU/USD,
   BTC/USDT), horizontes 1/5/15/60 min, 624 hipótesis con Holm, walk-forward trimestral y periodo
   bloqueado 2025-09 → 2026-08 evaluado **una sola vez**. Resultados: `results/dev/`,
   `results/holdout/`, `config/frozen.json`; interpretación en `docs/02_resultados_empiricos.md`.
3. **Fase 1C** — paquete `src/tradingbot/` con CLI `tbot`: datos, investigación, motor de alertas
   (estado «SIN SEÑAL»), monitor de deterioro, notificadores, cuenta simulada, panel web local.
4. **Fase 2** (solo documento) — `docs/03_fase2_intermediarios.md`. Dinero real bloqueado por
   `execution/guard.py`; **no existe** adaptador de órdenes reales (intencional).

## Resultados clave

- Divisas y oro: **SIN SEÑAL** (acierto 50,5–51,3 % a 1 min; se necesita 54,05 % con pago 85 %).
- 80 %: no alcanzable (máximo 59,3 % en subconjuntos pequeños).
- Contado/CFD: nada rentable ni con costos optimistas.
- BTC/USDT 1 min GBM (política B): pasó el periodo bloqueado (56,4 %, EV +0,039) pero solo con
  entrada instantánea y empate reembolsado; con 60 s de retraso EV −0,044. Estado
  `VALIDADO_HOLDOUT` → solo alertas «EXPERIMENTAL — NO OPERAR».
- USD/JPY 1 min: buen resultado en el bloqueado pero NO fue candidata en desarrollo; **no promover**
  (sería sesgo de selección). Solo hipótesis nueva para datos posteriores a 2026-09-01.

## Qué falta (próximos pasos)

1. **Instalar y verificar en local**: `pip install -e ".[dev]"`, `pytest -q` (55 pruebas),
   `tbot data probe` para ver qué fuentes alcanza el PC del usuario (desde Colombia Binance API y
   probablemente Dukascopy deberían funcionar; en la nube estaban bloqueadas).
2. **Observación en vivo sin dinero de BTC 1 min** (2–4 semanas): ver README, sección 3 de uso
   (`tbot train --model gbm`, `tbot live`, `tbot serve`, luego `tbot live-verdict`). La cuenta
   simulada usa precios reales de entrada y vencimiento. Esperado: la latencia real borra la ventaja.
3. **Repetir el estudio con Dukascopy (bid/ask reales)** en local:
   `tbot data download --symbols EURUSD,... --source dukascopy` y `tbot research run --source dukascopy`.
   Es un estudio nuevo: registrar enmienda/nuevo pre-registro antes de mirar resultados.
4. Investigar la baja cobertura de HistData 2023 (registro de errores, ítem 10).
5. Feeds en vivo para divisas: requieren cuenta demo con API (Deriv, OANDA, MT5 en Windows o IBKR);
   pedir credenciales al usuario y guardarlas solo en `.env`.
6. Fase 2 solo si algo llega a `VALIDADO` y con autorización expresa del usuario.

## Cómo trabajar aquí

- Rama de trabajo: `claude/festive-cray-n1yfb3` (aún sin fusionar a `main`).
- Pruebas: `pytest -q`. Demo: `tbot alerts demo` y `tbot alerts demo --planted-edge --experimental`.
- No cambiar `config/research.toml` ni reinterpretar resultados ya vistos; cualquier estudio nuevo
  se pre-registra primero (commit con fecha) y se evalúa en datos no usados.
- Todo en UTC internamente; mostrar en America/Bogota.
