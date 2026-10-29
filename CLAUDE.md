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

1. ~~Instalar y verificar en local~~ **Hecho (2026-10-01/02)**: mismas versiones que la nube, pruebas
   en verde (79 tras las correcciones), demos idénticas. `tbot data probe` desde Colombia: Binance,
   HistData, Yahoo, Deriv y ForexFactory responden; **Dukascopy no** (503 «No server is available»
   y timeouts, del lado del servidor; igual el 2026-10-02). Una auditoría del bucle en vivo halló y
   corrigió 10 fallos que habrían dañado la observación (ítems 11–20) y una revisión final otros 8
   (ítems 22–29). El feed real de Binance se probó con `run_live` (5 ciclos, sin errores).
2. **BTC 1 min con entrada automática (+2 s): se evalúa con datos históricos de 1 s (Enmienda 2), no en
   vivo** — el usuario NO puede dejar el portátil encendido semanas. La observación en vivo se detuvo el
   2026-10-03 (datos en `runtime/live`, sin inspeccionar). La reproducción oficial corre en GitHub
   Actions (`.github/workflows/replay.yml`, se dispara con `[replay]` en el commit) con el modelo
   registrado `config/modelos/BTCUSDT_h1_gbm.pkl` (SHA-256 en `config/observacion_en_vivo.json`) y guarda
   `results/live/verdict.json` y `sensibilidad.json`. Muestra fija 3 500, criterios de la Aclaración 2.
   Solo sería útil para una automatización, que el usuario hoy NO quiere.
   **Resultado (2026-10-04): APRUEBA** — 57,63 % (lím. inf. 55,98 %), EV +0,060 con entrada a +2 s;
   se apaga con el retraso (+10 s ≈ 56,4 %, +30 s no supera). **Verificación adversaria (2026-10-04):
   sin fuga ni errores** (probabilidades y resultados recalculados coinciden al 100 %; placebo 50,3 %),
   pero la ventaja se debilita: después de la muestra fija 54,1 % (EV +0,001), todo el periodo 56,3 %,
   entre semana 54,1 %, fin de semana 58,4 % (*post hoc*). **Estudio 5 pre-registrado** (docs/01):
   datos desde 2026-10-04, entrada +10 s (manual realista); H5a todas las horas (3 500), H5b solo fin
   de semana UTC (2 500), Holm; plazo 2026-12-13. Evaluar con `replay.yml` (`--entry-delay-s 10`)
   cuando haya datos suficientes (~3 semanas). Señales manuales en demo solo si aprueba.
2b. **Decisión del usuario (2026-10-03): señales MANUALES**, con ≥ 1 min de anticipación, en el
   instrumento y la duración más predecibles; formato: hora de apertura en UTC−5, instrumento, duración,
   dirección. Resultados, todos pre-registrados y aplicados mecánicamente (docs/01):
   - Estudio 2 (B_lat60 de la Fase 1B): BTC 15 y 60 min no confirman → SIN SEÑAL.
   - Estudio 3 (flujo de órdenes, perpetuo, cruce BTC/ETH): no mejora → SIN SEÑAL.
   - Estudio 4 (ETH 15 min solo precio, periodo limpio para ETH): 52,87 % → SIN SEÑAL.
   Patrón: ventajas de ~55 % hasta 2025 que desaparecen en el último año. **No emitir señales manuales
   sin un estudio nuevo pre-registrado que confirme.** Martingala descartada (docs/02, 6.1). No hay
   intermediario con API oficial para BTC a 1 min (Deriv: solo multiplicadores; docs/03, 2.1).
   Evaluaciones largas: usar datos históricos o GitHub Actions, nunca el portátil encendido días.
3. **Repetir el estudio con Dukascopy (bid/ask reales)** en local (bloqueado mientras Dukascopy falle):
   `tbot data download --symbols EURUSD,... --source dukascopy` y `tbot research run --source dukascopy`.
   Es un estudio nuevo: registrar enmienda/nuevo pre-registro antes de mirar resultados.
4. Investigar la baja cobertura de HistData 2023 (registro de errores, ítem 10).
5. Feeds en vivo para divisas: requieren cuenta demo con API (Deriv, OANDA, MT5 en Windows o IBKR);
   pedir credenciales al usuario y guardarlas solo en `.env`.
6. Fase 2 solo si algo llega a `VALIDADO` y con autorización expresa del usuario.
7. **Análisis del PDF «El secreto del trading profesional» (2026-10-24)**: `docs/05_...`. El «90 %» de los
   grupos se explica con repeticiones tras perder (al azar: 87,4 % con 2, 93,7 % con 3; EV −0,08) y con
   selección de canales (`scripts/simulacion_grupos_senales.py` → `results/grupos_senales.json`).
   - **Estudio 5:** código listo (`tbot study5-verdict`, `.github/workflows/estudio5.yml`, manual).
     - Enmienda 2026-10-24: Bonferroni α = 0,025 por hipótesis. Cada una se evalúa en cuanto su muestra está
       completa; de las incompletas solo se informa el conteo.
     - **H5a APRUEBA (2026-10-25, run 40160162254):** 56,11 % [54,46 %], EV +0,034, p = 0,0075.
       Entre semana 53,2 %; fin de semana 58,4 % (descriptivo). Con pago 80 % a +10 s, EV +0,009.
       Consecuencia: señales manuales experimentales SOLO en demo (falta construir ese modo y verificar
       el precio, el empate y el pago del intermediario).
     - H5b: 2 286 de 2 500 al 2026-10-24; se completaría con el fin de semana del 25 de octubre
       (lanzar con `end` = 2026-10-26).
   - **Estudio 6 «zonas»:** pre-registrado (bc97dc0), código congelado (37fdd3f) y ejecutado: **SIN SEÑAL**.
     En BTC las zonas no mejoran el log-loss y bajan el EV (55,61 % → 55,19 %). En EUR/USD empeoran.
   - **Estudio 7 (Kronos, análogos, Kalman, ETH como mejoras del GBM de BTC 1 min):** SIN SEÑAL (2026-10-25).
     Kronos solo 50,03 %. ETH: mejora puntual (57,0 % vs 55,8 %, EV +0,050 vs +0,028), IC incluye 0 →
     hipótesis nueva solo con datos posteriores al 2026-10-26 y pre-registro propio. Kronos lo corre el
     USUARIO (el clasificador bloquea ejecutar código descargado): `~/proyectos/kronos-externo`.
   - **Estudio 8 («Golden BIAS 200» de oro, TradingView):** SIN SEÑAL. Pierde en las 4 versiones, en todas
     las sesiones y en todos los años (contado −0,34 USD/oz; binaria 49,1 %).
   - **Estudio 9 (regla de Facebook: RSI 1D+W sobrecomprado → ventas, 4H, 15M):** SIN SEÑAL, acierta 46–49 %
     en BTC/ETH/oro/EUR.
   - **Estudio 10 (oro + correlación con DXY aproximado + zonas):** SIN SEÑAL (48,2 % / 49,9 %); el filtro
     quita por igual perdedoras y ganadoras. Divisas de HistData descargadas: EUR, JPY, GBP hasta 2025-08.
   - **Estudio 11 (regla de la primera vela: ORB 9:30 NY + FVG + envolvente, 3:1):** SIN SEÑAL en Nasdaq 100,
     S&P 500 y oro (−0,18 / −0,09 / −0,34 R). Instrumentos NSXUSD y SPXUSD (HistData) añadidos; HistData no
     tiene NSXUSD desde 2026-05. HistData también tiene UDXUSD (índice del dólar real), aún sin usar.
   - **docs/07_tradingview.md:** cómo usar TradingView (ideas, paper trading, gráfico BINANCE:BTCUSDT) y
     trampas de su backtest; sus datos NO se pueden usar en procesos automáticos (términos de uso).
   - **Enfoque (2026-10-25, del usuario):** no probar herramientas para copiarlas; DESARMARLAS (datos, lógica)
     y extraer la pieza con información real, validarla fuera de muestra e integrarla. El bot debe vigilar
     TODAS las monedas y elegir la de mayor probabilidad (Estudio 13).
   - **docs/08_conocimiento_y_mejoras.md:** por qué funcionan o fallan las estrategias, disección de cada
     herramienta y propuestas P1–P7. Hallazgo: la ventaja del GBM de BTC 1 min sale sobre todo de `clpos`
     (continuación de la presión del final de la vela: 52,8 % si cierra arriba; 55,4 % con volatilidad baja),
     luego del nivel de volatilidad (`scripts/analisis_importancia_btc.py`). P1 (velas de 1 s dentro del
     minuto) es la propuesta más prometedora.
   - **Estudio 12 (ETH → BTC 1 min):** pre-registrado (b6f22fa); evaluar una sola vez después del 2027-01-18.
   - **Estudio 13 (selector multimoneda BTC/ETH/SOL/BNB/XRP/DOGE/ADA):** NO PASA (falla el criterio 5 por poco:
     EV por operación 0,0418 vs BTC 0,0437), pero el EV por día es 2,8 veces mayor; XRP sola 57,46 % (post hoc).
     Sin confirmación según el pre-registro; cualquier variante es hipótesis nueva solo con datos nuevos.
     Probabilidades por moneda en data/processed/estudio13/.
   - **Estudio 14 (selector por EV diario + XRP sola):** pre-registro 1868a92; SOLO datos 2026-10-26 → 2027-01-18.
   - **Estudio 15 (P1: presión dentro del minuto con velas de 1 s):** PASA el desarrollo (58,56 % vs 56,89 %,
     104 813 vs 51 386 operaciones, EV +0,079 vs +0,048; log-loss +0,0021). Verificación: sin fuga (alineación
     100 %), pero la ventaja extra vive en 1–2 s (+1 s 57,3 %, +5 s 55,3 %, +10 s ≈ 0). Confirmación pre-registrada
     con 2026-10-26 → 2027-01-18. Camino a 57–60 %: entrar en ≤ 2 s (automatización).
   - **Ejecución rápida (docs/03, 2.2, 2026-10-25):** no hay vía legal con API oficial desde Colombia para pago
     fijo de 1 min en BTC. Deriv: BTC/ETH solo multiplicadores (8,2 pb de comisión); Binance Futures 4–10 pb vs
     ventaja de +0,47 pb; Polymarket 5/15 min bloqueada por Coljuegos. Camino: P8 (anticipar la señal al
     segundo 50–55) y ejecución manual rápida en demo.
   - **Estudio 16 (P8: aviso anticipado en el segundo 50/55):** PASA el desarrollo. H16a (s 55, clic +5 s) 57,33 %,
     EV +0,056; H16b (s 50, clic +10 s) 57,00 %, EV +0,050; 5/5 trimestres; reloj de 1 s alineado al 100 %.
     H16b tolera 15 s de demora (55,6 %). Confirmación con 2026-10-26 → 2027-01-18. Es el camino para la
     operación MANUAL: el bot debe avisar en el segundo 50 de cada vela.
   - **Modo de señales anticipadas para DEMO (2026-10-25):** `live/anticipada.py`, panel `/senales`,
     `tbot senal entrenar|vivo`, `scripts/iniciar_senales.sh`. Aviso en el s 50 con sonido, botón «ya hice
     clic» (espacio), bloqueo a los 15 s («TARDE»), diario con referencia de Binance por clic. **Pendiente:**
     `tbot senal entrenar` en cuanto Binance publique el 1m/1s del 2026-10-25 (entrena una sola vez el modelo
     de la confirmación del Estudio 16; config/senal_anticipada.json guarda el SHA-256). El internet del PC
     falla a ratos (DNS): el bucle sigue y reintenta.
   - **Modelo de señales anticipadas CONGELADO (2026-10-26):** `BTCUSDT-anticipada-k50-L10-35b764`, SHA-256 5ebfa485…
     (config/senal_anticipada.json); la demo ya se puede usar con `scripts/iniciar_senales.sh`.
   - **Estudio 17 (Fibonacci «zona dorada» + ICT):** SIN SEÑAL. Zona dorada = azar (50,0/50,4/49,8 % vs 50 %) en
     BTC/oro/EUR; bloque ICT no mejora el GBM de BTC (EV 0,048 → 0,038).
   - **IQ Option (comprobado por el usuario, 2026-10-27):** NO hay BTC/USD a 1 minuto; solo binaria de 15 min y
     «blitz» de 3 min. Registro de errores 41 (se recomendó sin comprobar).
   - **Estudio 18 (aviso anticipado con BTC a 3/5/15 min):** SIN SEÑAL con pago 85 % (54,09 / 54,70 / 54,19 %).
     La ventaja vive en el contrato de 1 min. Con pago ≥ 90 % el equilibrio baja (post hoc): pedir al usuario
     el pago real de su plataforma antes de cualquier estudio nuevo.
   - **Estudio 19 (vencimiento fijo cada 15 min, pago 87 %, entrar R min antes):** ninguna pasa estrictamente;
     R=1 es la única con ventaja (55,42 %, EV +0,033, 7/día; con clic +5 s 58,1 %); R≥2 ≈ 53 %. Demo:
     `scripts/iniciar_senales.sh --cuarto 1 --pago 87` (solo si la plataforma deja comprar con ≥ 1 min).
   - **Estudio 20 (2026-10-27, repetición mes a mes «como si no hubiera pasado», 2025-09 → 2026-10-25):** H20a
     **PASA**: 57,60 % [56,91 %], EV +0,059, 22 129 operaciones, 10 de 14 meses con EV > 0. H20b (cuarto de hora,
     pago 87 %) no pasa (54,9 %, 2 174 ops). Informativo: con p ≥ 0,60, **62,5 %** (5 185 ops) y 59,7 % en
     2024-07 → 2025-08; las señales se concentran en algunos meses. Predicciones en results/estudio20/.
   - **Estudio 21 (pre-registrado):** umbral p ≥ 0,60 con el modelo congelado; confirmación con 2026-10-26 →
     2027-01-18. Demo: `--umbral 0.60` (solo práctica).
   - **Estudio 22 (estrategias de comunidades de binarias: MHI, Milhão, Torres Gêmeas, catalogación, bots de
     GitHub, Bollinger de smart-lab):** 0 de 115 pasan; cuadrantes 50,0 % (igual que el placebo); con 2 gales
     85–89 % de ciclos y EV −0,13 a −0,51. Solo Bollinger nocturno (21–24 UTC) en divisas 54–56 % → candidata P10.
     Catálogo local: data/raw/senales_terceros/CATALOGO_ESTRATEGIAS.md (no versionado).
   - **Estudio 23 (auditoría de 21 canales de Telegram, 55 887 señales extraídas sin cuenta):** ningún canal supera
     el azar; ~20 000 señales publicadas ANTES de la entrada aciertan 49–51 % en la primera entrada. CSV e informe
     en data/raw/senales_terceros/ (no versionado). Pares de HistData 2020–2026 en data/raw/histdata_pares/.
   - **Estudio 24 (ETH y BTC/USDC en los segundos 0–49):** H24a (ETH) no pasa (mejora el log-loss pero baja el
     acierto de la política en los dos periodos). H24b (BTC/USDC) tampoco pasa.
   - **Estudio 25/27 (reversión nocturna en divisas, regla de smart-lab desarmada):** en 24 pares nuevos pasa; con
     precio medio de ticks (bid+ask, HistData) y clic a +10 s, **57,17 %** [56,61 %] en 31 166 ops, CALL/PUT
     simétricos, 6/6 meses; a las 22 UTC, 62,3 %. Con precio bid había un artefacto (CALL 75 % justo tras el cierre
     de NY). Falta: confirmación con datos > 2026-10-25 y que el usuario verifique pares no OTC, vencimiento de
     3 min y pago entre 16:00 y 19:00 de Bogotá. Ticks en data/raw/histdata_ticks_seg/.
   - **Estudio 28 (invierno, 2025-11 → 2026-03):** pasa con ventana UTC fija (56,79 %, 26 832 ops) y con la anclada a NY
     (55,37 %); la regla eligió **UTC fija = 16:00–18:59 Bogotá todo el año**. Hora fuerte: 22 UTC (17:00 Bogotá),
     61,7 % invierno y 62,3 % verano. **Estudio 29 pre-registrado:** confirmación con ticks 2026-10-26 → 2027-01-18
     (H29a ventana entera, H29b solo 22 UTC), una vez, cuando HistData los publique.
   - **Modo en vivo de la reversión nocturna (2026-10-28):** `live/nocturna.py`, panel `/nocturna`, `tbot nocturna`,
     `scripts/iniciar_nocturna.sh`. Usa la API pública de Deriv (sin cuenta; 19 de los 24 pares; precio medio), avisa
     con sonido, registra el clic y mide el resultado de referencia con los ticks de Deriv. Probado en vivo
     (3 avisos, ventana forzada). Dependencia nueva: websocket-client.
   - **Estudio 30 (reversión en otras horas y mercados):** ninguna pasa. Divisas a otras horas 51–54 %; oro, S&P y BTC
     de noche no. La ventaja existe solo a las 21–24 UTC.
   - **Estudio 31 (solidez de parámetros, informativo):** sólida. Superficie suave y monótona (más ancho/largo → más
     acierto); 30/2,5/5 min = 61,3 % (21 302 ops). Enmienda al Estudio 29: H29c (esa casilla). Modo en vivo:
     `--variante fuerte` (5 min), solo práctica.
   - **Estudio 26 (aviso anticipado + umbral p ≥ 0,60 en otras monedas):** solo ETH pasa (653 ops, 58,8 %); XRP, SOL y
     DOGE nunca llegan a p 0,60 con clic a +10 s.
   - **Lección de los Estudios 20–24:** lo único que sube el acierto es **filtrar por confianza** del propio
     modelo (p ≥ 0,60 → ~60–62 %). Sumar variables de terceros, de otros mercados o de canales no lo mejora.
   - **Investigación diaria automática:** tarea programada `investigacion-diaria-trading-bot` (7:00 Bogotá,
     corre si la app está abierta) → bitácora docs/09_bitacora_investigacion.md (solo commit, sin push).
     Tiene prohibido mirar resultados de datos posteriores al 2026-10-25 (reservados para los Estudios 12/14/15).
   - **docs/06_ideas_de_otros_traders.md:** catálogo vivo de ideas de terceros probadas, errores típicos,
     estudios sobre traders de redes y lista de señales de estafa. El usuario NO quiere comprar nada: busca
     piezas para pulir el modelo propio. Añadir ahí cada idea nueva.
   - **Pendientes:** auditor de señales de terceros y gestión/diario para la demo.

## Cómo trabajar aquí

- Rama de trabajo: `claude/festive-cray-n1yfb3` (aún sin fusionar a `main`).
- Pruebas: `pytest -q`. Demo: `tbot alerts demo` y `tbot alerts demo --planted-edge --experimental`.
- No cambiar `config/research.toml` ni reinterpretar resultados ya vistos; cualquier estudio nuevo
  se pre-registra primero (commit con fecha) y se evalúa en datos no usados.
- Todo en UTC internamente; mostrar en America/Bogota.
- PC del usuario: Ubuntu 26.04 (desde 2026-10-12; Windows 11 queda en arranque dual). Proyecto en `~/proyectos/trading-bot`, entorno `.venv` (Python 3.14): `.venv/bin/tbot`, `.venv/bin/pytest -q`. Observación en vivo + panel: `scripts/iniciar_observacion.sh` (Ctrl+C detiene ambos; en Windows era `iniciar_observacion.bat`).
