# Registro de errores y lecciones aprendidas

> Nadie es perfecto: cada error encontrado queda documentado con su causa, su impacto y la
> corrección. Ningún cambio de esta lista modificó hipótesis, umbrales ni criterios del protocolo
> pre-registrado (`docs/01_informe_investigacion_fase1a.md`) después de ver resultados reales.

| # | Fecha (UTC) | Dónde | Error | Cómo se detectó | Impacto | Corrección |
|---|---|---|---|---|---|---|
| 1 | 2026-09-30 | `research/experiment.py` | La clave de día para el bootstrap usaba `asi8` suponiendo nanosegundos; con otra resolución interna de pandas todos los datos caían en un solo bloque y el IC del EV salía degenerado (`[-0.058, -0.058]`). | Prueba de humo con datos sintéticos | Ninguno sobre resultados reales (aún no existían) | Clave de día = año·10000 + mes·100 + día en hora de Bogotá; prueba `test_block_bootstrap_ci_non_degenerate`. |
| 2 | 2026-09-30 | `research/calibration.py` | La regresión isotónica asignaba probabilidad 0 o 1 en las colas con pocas muestras, justo donde una política selectiva operaría: habría inflado el EV estimado. | Prueba unitaria del calibrador | Ninguno sobre resultados reales | Isotónica sobre bins de ≥ 500 observaciones. |
| 3 | 2026-09-30 | `research/report.py` | La tabla de sensibilidad salía vacía (se filtraba antes de renderizar). | Prueba de humo sintética | Ninguno | Los criterios se calculan sobre todas las filas; solo pueden ser candidatas las que no son de referencia ni de sensibilidad. |
| 4 | 2026-09-30 | `research/features.py` | `spread_rel = spread / mediana` era NaN cuando la fuente no tiene bid/ask (Binance, spread = 0); se descartaban **todas** las decisiones de BTC/USDT (0 evaluaciones). | Ejecución real 36666769740 en GitHub Actions (el estudio de BTC terminó en 15 s) | La ejecución no produjo resultados de BTC; no se vio ningún resultado de acierto | Spread relativo neutro (= 1) si la mediana es 0; prueba de regresión `test_zero_spread_source_still_produces_decisions`. |
| 5 | 2026-09-30 | `.github/workflows/research.yml` | El trabajo de informe guardó en la rama resultados parciales de una ejecución fallida (incluido un `config/frozen.json` sin validez). | Revisión del commit automático | Archivos inválidos en la rama durante minutos | Se eliminaron; el informe solo se guarda si **todos** los instrumentos terminan. La línea del registro de ejecuciones (`results/registry.jsonl`) se conserva como traza honesta del intento. |
| 6 | 2026-09-30 | Descarga Dukascopy | Todas las descargas de Dukascopy desde GitHub Actions recibieron HTTP 503 (y un timeout) desde el primer archivo. | Ejecución 36666769740; diagnóstico 36667788455: 13–17 s por archivo y luego 503/429 (limitación de tasa) | Sin datos de divisas ni oro | Enmienda 1 del protocolo: HistData (BID M1) para FX y oro en GitHub; Dukascopy queda para uso local. |
| 7 | 2026-09-30 | `live/runner.py` | Argumento duplicado `alert` en el registro de eventos; el resumen de la demo contaba solo las últimas 300 alertas. | Ejecución de la demo | Ninguno | Campo renombrado a `payload`; contador de estados independiente. |
| 8 | 2026-09-30 | `signals/alert.py`, `live/feeds.py` | `format_text` fallaba si el pago no estaba definido; el filtro de velas abiertas de Binance comparaba fechas con y sin zona horaria. | Pruebas automatizadas nuevas del sistema de alertas | Ninguno (no se había ejecutado en vivo) | Manejo de valores ausentes; comparación entre marcas con zona horaria. |
| 9 | 2026-09-30 | `.github/workflows/diagnose.yml` | `curl` sin tiempo máximo quedó colgado con Dukascopy y hubo que cancelar la ejecución (se perdieron sus registros). | Ejecución 36667482678 | Diagnóstico repetido | `--max-time 30` y límites de tiempo por paso. |

## Lecciones

1. Las pruebas con datos sintéticos deben cubrir **todas** las variantes de fuente (con y sin bid/ask).
2. Un informe automático nunca debe publicar resultados de una ejecución incompleta.
3. Una muestra pequeña engaña: en la demo con ventaja sembrada, 43 operaciones dieron 20 aciertos
   (parecía que no había ventaja); con 818 operaciones el acierto fue 62,4 % frente a 65,6 % anunciado.
