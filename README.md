# trading-bot — investigación cuantitativa y alertas con validación honesta

Sistema para **investigar** si es posible anticipar la dirección de divisas y otros instrumentos,
emitir **alertas fundamentadas** solo cuando la evidencia lo respalde y, en una fase posterior y bajo
condiciones estrictas, considerar la ejecución automática.

> **No promete tasas de acierto.** Si los datos no respaldan una ventaja rentable y robusta, el sistema
> muestra **«SIN SEÑAL»**. No opera con dinero real: no existe código para enviar órdenes reales y una
> guarda lo impide salvo autorización expresa (`docs/03_fase2_intermediarios.md`).

## Resultado de la investigación (resumen)

Estudio pre-registrado con datos reales 2021–2026 (624 hipótesis, corrección por pruebas múltiples,
periodo final bloqueado evaluado una sola vez). Detalle en
[`docs/02_resultados_empiricos.md`](docs/02_resultados_empiricos.md).

- **Divisas (EUR/USD, GBP/USD, USD/JPY, AUD/USD) y oro: SIN SEÑAL** a 1, 5, 15 y 60 minutos. A 1 minuto
  los modelos aciertan 50,5–51,3 %; con pago del 85 % se necesita 54,05 %.
- **80 % de acierto: no alcanzable** en ningún instrumento ni subconjunto con muestra suficiente
  (máximo 59,3 %). Un «80 %» se fabrica con salidas asimétricas… y pierde dinero.
- **Contado/CFD:** sin ninguna configuración rentable, ni con costos optimistas.
- **BTC/USDT 1 minuto:** efecto estadísticamente real (56,4 % en el año bloqueado) que **solo** existe con
  entrada instantánea y empate reembolsado; con 60 s de retraso pierde. Estado `VALIDADO_HOLDOUT`:
  solo alertas «EXPERIMENTAL — NO OPERAR» hasta superar la observación en vivo sin dinero.

## Documentos

| Documento | Contenido |
|---|---|
| [`docs/01_informe_investigacion_fase1a.md`](docs/01_informe_investigacion_fase1a.md) | Informe de investigación y **protocolo pre-registrado** (congelado antes de ver datos) |
| [`docs/02_resultados_empiricos.md`](docs/02_resultados_empiricos.md) | Resultados con datos reales e interpretación |
| [`docs/03_fase2_intermediarios.md`](docs/03_fase2_intermediarios.md) | Comparativa de intermediarios para Colombia y controles de la Fase 2 |
| [`docs/04_registro_de_errores.md`](docs/04_registro_de_errores.md) | Errores encontrados, causas, correcciones y lecciones |
| `results/<etapa>/summary.md` | Informe generado automáticamente por cada ejecución del estudio |

## ¿Local o GitHub? Recomendación

- **GitHub (este repositorio):** para guardar versiones del código, los informes y ejecutar el estudio
  con datos reales en **GitHub Actions** (servidores con internet, gratis en repositorios públicos). Es
  lo que se usó para la investigación, porque el entorno donde se desarrolló no tenía acceso a las
  fuentes de datos.
- **Su PC:** para las **alertas en vivo** y el **panel**, que necesitan un proceso encendido de forma
  continua y conexión directa a la fuente de precios. Un contenedor en la nube se apaga y no sirve
  para eso.
- **Conclusión:** mantenga el código en GitHub y clone el repositorio en su PC. Si quiere que yo
  trabaje directamente en su PC, abra Claude Code (aplicación de escritorio o terminal) dentro de la
  carpeta clonada; desde esta sesión en la nube **no tengo acceso a su computador**.

## Instalación en su PC (Windows, macOS o Linux)

Requisitos: [Python 3.10 o superior](https://www.python.org/downloads/) (en Windows marque «Add Python
to PATH») y [Git](https://git-scm.com/downloads).

```bash
git clone https://github.com/Fredy286/trading-bot.git
cd trading-bot
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                      # debe terminar sin fallos
```

## Uso

```bash
# 0) ¿Qué fuentes de datos alcanza su PC?
tbot data probe

# 1) Formato de alerta (EJEMPLO FICTICIO) y demostración reproducible con datos SINTÉTICOS
tbot alerts example
tbot alerts demo                                   # paseo aleatorio → «SIN SEÑAL»
tbot alerts demo --planted-edge --experimental     # ventaja sembrada artificialmente → formato de alerta
tbot serve --runtime runtime/demo                  # panel en http://127.0.0.1:8765

# 2) Datos reales y estudio pre-registrado
tbot data download --symbols EURUSD,BTCUSDT --start 2021-01-01 --end 2026-09-01   # Dukascopy (bid/ask) y Binance
tbot data download --symbols EURUSD --source histdata                           # alternativa: HistData (solo BID)
tbot data quality --symbol EURUSD
tbot research run --symbol EURUSD --stage dev      # walk-forward, sin tocar el periodo bloqueado (añada --source histdata si usó HistData)
tbot research report --stage dev                   # veredicto mecánico + config/frozen.json

# 3) Observación en vivo SIN dinero real (hoy: BTC/USDT vía API pública de Binance)
copy .env.example .env        # macOS/Linux: cp .env.example .env
tbot data download --symbols BTCUSDT --start 2025-09-01 --end 2026-10-01
tbot train --symbol BTCUSDT --horizon 1 --model gbm        # estado: VALIDADO_HOLDOUT (no accionable)
tbot live --symbol BTCUSDT --horizon 1 --model gbm --runtime runtime/live
tbot serve --runtime runtime/live                          # en otra terminal
tbot live-verdict --symbol BTCUSDT --horizon 1 --model gbm # tras 3 500 alertas sin empate (~3 semanas)
```

En Windows, `scripts\iniciar_observacion.bat` (doble clic) abre `tbot live` y el panel con estos mismos
comandos; si se cierra o el PC se reinicia, basta con volver a abrirlo.

Durante la observación en vivo (semanas sin supervisión):

- El modelo `VALIDADO_HOLDOUT` se observa siempre: sus alertas salen como «EXPERIMENTAL — NO OPERAR»
  y se evalúan con el precio real de Binance al entrar y al vencer. `TB_SHOW_EXPERIMENTAL` solo hace
  falta para ver alertas de modelos no validados.
- Deje el portátil **conectado al cargador**. Mientras `tbot live` está abierto, Windows no se suspende
  por inactividad (no impide cerrar la tapa ni suspender a mano).
- Si se cierra o el PC se reinicia, vuelva a lanzar el mismo `tbot live`: recupera los resultados ya
  registrados de ese modelo y marca como «no_evaluable (reinicio)» las alertas que quedaron abiertas.
  No se puede abrir dos veces sobre la misma carpeta (se contarían doble).
- Si el bucle deja de actualizar, el panel lo indica con «DETENIDO» en rojo. Los errores, huecos y
  reinicios quedan en `runtime/live/events.jsonl`.
- Los criterios están **pre-registrados** (Aclaración 2 del protocolo): se juzga una sola vez con las
  **primeras 3 500 alertas sin empate** de un único entrenamiento, medidas con precio real, reunidas en
  un máximo de 8 semanas; aprueba solo si el límite inferior de Wilson 95 % supera 54,05 % y el EV medio
  es positivo. Consultar
  `tbot live-verdict` antes no cambia el resultado final. El comando informa cuántas filas excluyó y
  cuántas alertas quedaron «no evaluables» (sin precio, duración real fuera de 60 ± 10 s, reinicio…).
- La decisión se toma 1 s después del cierre de cada vela (`TB_FEED_LATENCY_S=1` en `.env`). Cada hora
  se registra el desfase entre el reloj del PC y el de Binance; si supera 0,5 s, `tbot live` avisa.

El estudio completo con datos reales también se puede lanzar desde GitHub: pestaña **Actions →
«Estudio empírico» → Run workflow**.

### Señales anticipadas para practicar en cuenta DEMO (Estudio 16)

Es el modo pensado para operar **a mano**. El bot decide en el **segundo 50** de cada vela de 1 minuto de
BTC/USD y avisa con sonido. Hay que hacer clic en la plataforma demo lo antes posible, idealmente antes de
que cierre la vela.

1. **Una sola vez:** congelar el modelo, entrenado con los 12 meses hasta el 2026-10-25. Es el mismo
   modelo que se confirmará en enero de 2027, así que no se vuelve a entrenar.

   ```bash
   .venv/bin/tbot senal entrenar
   ```

2. **Cada sesión de práctica:**

   ```bash
   scripts/iniciar_senales.sh
   ```

   Abre el panel en http://127.0.0.1:8765/senales. Pulse **«Activar sonido»** una vez (los navegadores lo
   exigen).
3. **Con cada aviso («↑ SUBE» o «↓ BAJA»):**
   - abra la operación de 1 minuto en la plataforma demo;
   - de inmediato pulse **«YA HICE CLIC»** (o la barra espaciadora): así se mide su tiempo de reacción;
   - anote el precio de entrada y el pago que muestra la plataforma.
4. **Cuando venza** (60 s después del clic): anote en el diario el resultado (ganó, perdió o empate) y el
   precio de salida. El bot calcula el mismo resultado con el precio de Binance y muestra si coinciden.
5. **Pasados 15 s desde el aviso**, el panel dice «TARDE — no entres en esta». Desde ahí ya no hay ventaja
   medida.

El diario está en `runtime/senales/`. Allí, `clics.jsonl` y `registros.jsonl` son suyos, y `senales.jsonl`
es del bot. Con unas decenas de operaciones anotadas se puede saber:
- cuánto tarda usted en hacer clic;
- si la plataforma sigue el precio de Binance;
- si devuelve el dinero en empate;
- cuánto paga de verdad.

Son las condiciones que exige el Estudio 5 antes de cualquier otra cosa. **Nunca con dinero real.**

### Reversión nocturna en divisas para practicar en cuenta DEMO (Estudios 25, 27 y 28)

```bash
scripts/iniciar_nocturna.sh
```

- Abre el panel en `http://127.0.0.1:8765/nocturna`; pulse «Activar sonido».
- Cada minuto de la ventana nocturna (de 16:00 a 19:00 en Bogotá, todo el año, según el
  Estudio 28) mira 19 pares en la API pública de Deriv (sin cuenta). La ★ marca la hora fuerte (5 p. m.).
- Si una vela de 1 min cierra fuera de las bandas de Bollinger (20, 2), suena el aviso: **SUBE** (CALL) si
  cerró por debajo, **BAJA** (PUT) si cerró por encima. Vencimiento: **3 minutos**.
- Entre en los primeros 10 s y pulse «Ya entré». Pasados 15 s, el panel marca «TARDE».
- Unos 3½ min después, el diario anota el resultado de referencia con el precio medio de Deriv, desde la
  hora de su clic. El resultado de su plataforma puede ser distinto: compárelos.
- Desarrollo: 57,2 % con clic a +10 s (Estudio 27). **Sin confirmación con datos nuevos todavía. Solo demo.**

## Configuración (variables de entorno)

Todas las opciones están en [`.env.example`](.env.example): instrumentos, horario permitido (hora de
Bogotá), tipo de contrato, pago y si está verificado, umbral de calidad (EV mínimo), canal de
notificación (consola, archivo, Telegram, webhook) y límites de riesgo. Los tokens se leen del entorno;
no hay secretos en el código.

## Qué incluye cada alerta

Instrumento, intermediario y fuente de precio, fecha y hora en America/Bogota, dirección prevista, hora
límite para actuar, duración, probabilidad calibrada de la alerta y, aparte, el **acierto histórico de
señales parecidas** con su intervalo (IC90) —es una tasa del grupo de confianza parecida en calibración,
por eso la probabilidad de la alerta puede quedar fuera de ese intervalo—, umbral de rentabilidad, pago y
costos considerados, valor esperado, razones cuantificables, factores que la invalidarían y estado de
validación del modelo. Cada alerta registra cuándo se **generó, envió y evaluó**
(`runtime/<dir>/events.jsonl`, lo escribe `tbot live`) y cuándo se **recibió** (`runtime/<dir>/acks.jsonl`,
lo escribe el panel al pulsar «Marcar como recibida»).

Estados: `SEÑAL` (solo con modelo `VALIDADO`), `EXPERIMENTAL — NO OPERAR`, `SIN SEÑAL`, `PAUSADO`
(el monitor detectó deterioro en vivo; las que habrían sido alerta se siguen evaluando como hipotéticas,
sin operar, para que la observación no se estanque).

## Arquitectura

```
src/tradingbot/
  data/        descarga (Dukascopy, Binance, HistData), almacenamiento Parquet con manifiesto, limpieza
  research/    etiquetas, variables causales, modelos, walk-forward con purga, calibración,
               contratos y costos, simulación de ejecución, métricas, informe
  signals/     formato de alertas, motor de decisión, modelos entrenados, monitor de deterioro
  notify/      consola, archivo, Telegram, webhook
  live/        fuentes en vivo, bucle de alertas, demostración
  execution/   cuenta simulada y guarda de dinero real (sin adaptador real)
  app/         panel web local (biblioteca estándar)
tests/         pruebas automatizadas (anti-anticipación, purga, costos, calibración, alertas, panel…)
config/        protocolo del estudio (research.toml) y demo sintética (research_demo.toml)
```

## Limitaciones conocidas

- Con velas de 1 minuto no se puede modelar una latencia de pocos segundos con exactitud; se acota
  con dos escenarios (entrada en la vela siguiente o una vela después).
- El precio de Dukascopy/Binance no es el precio del intermediario donde se operaría; un contrato
  binario se liquida con el feed del intermediario.
- El feed en vivo implementado es Binance (cripto). Para divisas en vivo se requiere una cuenta con
  API (Deriv, OANDA, MetaTrader 5 o Interactive Brokers) — ver `docs/03_fase2_intermediarios.md`.
- Telegram y webhook están probados con un cliente simulado, no contra los servicios reales.

## Aviso

Herramienta de investigación. No es asesoría financiera ni una recomendación de inversión.
