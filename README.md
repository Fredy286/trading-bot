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
#    en .env ponga TB_SHOW_EXPERIMENTAL=true para ver las alertas experimentales
tbot data download --symbols BTCUSDT --start 2025-09-01 --end 2026-10-01
tbot train --symbol BTCUSDT --horizon 1 --model gbm        # estado: VALIDADO_HOLDOUT (no accionable)
tbot live --symbol BTCUSDT --horizon 1 --runtime runtime/live
tbot serve --runtime runtime/live                          # en otra terminal
tbot live-verdict --symbol BTCUSDT --model gbm             # tras ≥ 200 alertas evaluadas
```

El estudio completo con datos reales también se puede lanzar desde GitHub: pestaña **Actions →
«Estudio empírico» → Run workflow**.

## Configuración (variables de entorno)

Todas las opciones están en [`.env.example`](.env.example): instrumentos, horario permitido (hora de
Bogotá), tipo de contrato, pago y si está verificado, umbral de calidad (EV mínimo), canal de
notificación (consola, archivo, Telegram, webhook) y límites de riesgo. Los tokens se leen del entorno;
no hay secretos en el código.

## Qué incluye cada alerta

Instrumento, intermediario y fuente de precio, fecha y hora en America/Bogota, dirección prevista, hora
límite para actuar, duración, probabilidad calibrada con su intervalo, umbral de rentabilidad, pago y
costos considerados, valor esperado, razones cuantificables, factores que la invalidarían y estado de
validación del modelo. Cada alerta registra cuándo se **generó, envió, recibió y evaluó**
(`runtime/<dir>/events.jsonl`).

Estados: `SEÑAL` (solo con modelo `VALIDADO`), `EXPERIMENTAL — NO OPERAR`, `SIN SEÑAL`, `PAUSADO`
(el monitor detectó deterioro en vivo).

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
