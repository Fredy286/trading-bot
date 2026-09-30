# Fase 1B — Resultados empíricos e interpretación

> Fuente de todas las cifras: `results/dev/summary.md` (desarrollo, ejecución de GitHub Actions
> [36668266642](https://github.com/Fredy286/trading-bot/actions/runs/36668266642)) y
> `results/holdout/summary.md` (periodo bloqueado, ejecución
> [36668860165](https://github.com/Fredy286/trading-bot/actions/runs/36668860165)). Tablas completas por
> configuración en `results/<etapa>/all_evaluations.csv`. Hash de configuración `2bcecccbf2f9`
> (idéntico en ambas etapas).

## Resumen para decidir

| Pregunta | Respuesta con evidencia |
|---|---|
| ¿Se puede anticipar la dirección de **divisas** (EUR/USD, GBP/USD, USD/JPY, AUD/USD) o del **oro** a 1 minuto con rentabilidad? | **No — SIN SEÑAL.** Acierto de los modelos a 1 min: 50,5–51,3 %, frente a 54,05 % necesario con pago del 85 %. Ninguna configuración de divisas u oro superó los criterios pre-registrados en 5, 15 o 60 min. |
| ¿Es alcanzable un **80 %** de acierto? | **No**, en ningún instrumento, horizonte ni subconjunto de alta confianza con muestra suficiente. Máximo en desarrollo: 59,3 % (BTC, 0,4 % de las decisiones). |
| ¿Y en **contado/CFD** (sin pago fijo)? | **No.** 0 de 312 configuraciones con EV positivo respaldado, incluso con costos optimistas. A 1 min el costo iguala o supera el movimiento medio. |
| ¿Hay **algo**? | Sí, un efecto en **BTC/USDT a 1 minuto** que superó el periodo bloqueado (56,4 %, EV +0,039 por unidad apostada)… **solo si se entra al instante y el empate se reembolsa**. Con 60 s de retraso: EV −0,044. Si el empate cuenta como pérdida: EV −0,031. |
| ¿Qué hace el sistema entonces? | Divisas y oro: **«SIN SEÑAL»**. BTC 1 min: estado `VALIDADO_HOLDOUT` → solo alertas **«EXPERIMENTAL — NO OPERAR»** hasta completar la observación en vivo sin dinero, que ahora mide precios **reales** de entrada y vencimiento. |

## 1. Qué se ejecutó

- 6 instrumentos × 4 horizontes (1, 5, 15, 60 min) × 2 contratos (binaria pago 85 % con empate
  reembolsado; contado con spread + comisión) × 9 modelos × hasta 3 políticas = **624 hipótesis**,
  corregidas por Holm.
- Desarrollo: walk-forward trimestral 2022-01 → 2025-08 (15 trimestres), entrenando con los 12 meses
  previos. Periodo bloqueado: 2025-09 → 2026-08 (4 trimestres), evaluado **una sola vez** con las
  candidatas congeladas mecánicamente (`config/frozen.json`).
- Datos: HistData M1 BID para divisas y oro (enmienda 1: Dukascopy bloqueó a GitHub), Binance M1 para
  BTC/USDT. 2,07 M minutos con cotización por par de divisas; 2,98 M en BTC.

## 2. Calidad de datos y limitaciones de la fuente

- Minutos sin ticks reconstruidos (HistData): 0,5–0,7 % en divisas; 518 en oro.
- Huecos inesperados ≥ 2 h en días hábiles: 93–175 por instrumento en HistData, casi todos festivos
  (Viernes Santo, Navidad, Año Nuevo). BTC: 5 huecos (852 min en total).
- **Pendiente:** en divisas, los trimestres 2023-T1 a 2023-T3 tienen muchas menos decisiones válidas
  (p. ej., EUR/USD 2023-T2: 27 834 frente a ~90 000 habituales) y los huecos detectados no lo explican.
  No cambia las conclusiones (no hay señal en ningún trimestre), pero debe investigarse. Registrado en
  `docs/04_registro_de_errores.md`.
- Precio BID y spread **supuesto** para divisas/oro (ver enmienda 1).

## 3. Hipótesis

| ID | Resultado | Evidencia |
|---|---|---|
| H1 (1 min, pago 85 %) | **Rechazada** en divisas y oro. En BTC, **respaldada solo en condiciones ideales** | FX/oro: acierto 50,5–51,3 % (desarrollo y bloqueado). BTC GBM política B: 56,6 % [56,4] en desarrollo (n = 217 663) y 56,4 % [56,0] en bloqueado (n = 58 386) |
| H2 (≥ 80 %) | **Rechazada** | Mejor subconjunto con n ≥ 100: 59,3 % [58,2; 60,4] en desarrollo; en bloqueado 65,5 % pero con n = 139 (IC amplio y sin EV robusto) |
| H3 (horizontes largos mejoran el EV neto) | **No respaldada** | En contado bajan el umbral (EUR/USD: 97,8 % a 1 min → 56,0 % a 60 min con costos optimistas) pero ningún modelo lo alcanza. BTC 15–60 min pasó desarrollo y **se deterioró** en el bloqueado (EV +0,036 → +0,006; 60 min sin operaciones) |
| H4 (reglas técnicas no superan al azar tras costos) | **Respaldada** en divisas y oro | RSI/Bollinger aciertan 51–55 % en subconjuntos pequeños, ninguno sobrevive a Holm. BTC RSI 15 min: 57,9 % en desarrollo → 56,0 % en bloqueado, sin pasar el criterio estricto |
| H5 (excluir noticias reduce pérdidas) | **Parcialmente respaldada** | La política con filtro (BN) tuvo EV ≥ la política sin filtro (B) en 67 % de las comparaciones y menor caída máxima en 85 % |
| H6 (modelos > referencias) | Divisas: **no**. BTC 1 min GBM: **sí** en condiciones ideales | Referencia aleatoria en BTC 1 min: 50,0 %, EV −0,072 |
| H7 (probabilidades calibradas) | **Respaldada, pero poco informativas** | ECE mediana 0,72 pp (desarrollo) y 0,89 pp (bloqueado); > 2 pp en 3/48 y 2/48 casos. Brier 0,2488–0,2502 frente a 0,25 del azar: bien calibradas porque casi siempre dicen «≈ 50 %» |

## 4. Divisas y oro: por qué no hay señal

| Instrumento | Acierto 1 min (logística / GBM), desarrollo | Idem, periodo bloqueado | Movimiento medio 1 min | Costo optimista ida y vuelta | Umbral contado 1 min |
|---|---|---|---|---|---|
| EUR/USD | 50,6 % / 50,6 % | 50,8 % / 50,6 % | 0,87 pb | 0,84 pb | 97,8 % |
| GBP/USD | 50,6 % / 50,5 % | 50,8 % / 50,5 % | 0,95 pb | 0,95 pb | 99,9 % |
| USD/JPY | 51,1 % / 51,0 % | 51,3 % / 51,2 % | 1,04 pb | 0,70 pb | 83,9 % |
| AUD/USD | 50,6 % / 50,6 % | 50,7 % / 50,5 % | 1,22 pb | 1,65 pb | inalcanzable |
| XAU/USD | 50,5 % / 50,6 % | 51,1 % / 51,0 % | 1,66 pb | 1,48 pb | 94,4 % |

Se observa una reversión a la media muy leve (la regla «contraria al último minuto» acierta 50,3–50,8 %),
coherente con el ruido de microestructura, pero muy lejos de pagar un contrato.

**Observación que genera una hipótesis nueva (no validada):** USD/JPY 1 min con GBM selectivo acertó
55,4 % en desarrollo (no superó Holm, p = 0,22) y 57,0 % en el bloqueado. Por protocolo **no se promueve**:
hacerlo sería seleccionar mirando el periodo bloqueado. Además tiene la misma fragilidad que BTC (con 60 s
de retraso EV ≈ 0; con empate = pérdida EV −0,156). Solo puede probarse con datos nuevos.

## 5. BTC/USDT: la única candidata, y por qué no se debe operar todavía

| Configuración (binaria, pago 85 %) | Desarrollo: acierto / EV | Bloqueado: acierto / EV [IC95] | Bloqueado con 60 s de retraso | Bloqueado con empate = pérdida | Criterio estricto |
|---|---|---|---|---|---|
| 1 min, GBM, B | 56,6 % / +0,044 | 56,4 % / **+0,039** [0,028; 0,050] | 51,4 % / **−0,044** | 55,6 % / **−0,031** | Pasa |
| 1 min, GBM, BN | 56,7 % / +0,045 | 56,5 % / +0,041 [0,030; 0,052] | — | — | Pasa |
| 5 min, GBM, B/BN | 55,2–55,4 % / +0,021–0,025 | 53,7–53,8 % / −0,005 | — | — | No |
| 15 min, RSI extremos | 57,9 % / +0,070 | 56,0 % / +0,036 [0,006; 0,067] | — | — | No (Holm) |
| 15 min, logística B/BN | 56,0–56,3 % / +0,036–0,041 | 54,4–54,7 % / +0,006–0,011 | — | — | No |
| 60 min, logística B/BN | 56,6–57,5 % / +0,048–0,063 | 0 operaciones | — | — | No |

Lectura honesta:

1. El efecto a 1 minuto es **estadísticamente sólido** (dos periodos independientes, 4 de 4 trimestres
   positivos en el bloqueado) pero **microestructural**: existe en el primer instante después del cierre
   de la vela y desaparece en menos de un minuto.
2. Depende de condiciones que un minorista **no controla**: entrada casi instantánea al precio de Binance,
   pago de 85 % y reembolso en empate. Las plataformas de 1 minuto usan su **propio feed**, pagos
   variables y reglas de empate propias, y **no tienen API oficial** (ver Fase 2).
3. **Riesgo:** caída máxima de **280 unidades** de apuesta en el año bloqueado (ganancia total +2 285 en
   58 386 operaciones). Con apuestas del 1 % del capital, esa racha habría arruinado la cuenta.
4. Operaciones descartadas en el bloqueado (configuración 1 min B): 466 562 «sin señal», 647 por
   desconexión simulada, 1 caducada.

**Decisión:** estado `VALIDADO_HOLDOUT`. El sistema la muestra solo como «EXPERIMENTAL — NO OPERAR».
Para pasar a `VALIDADO` debe superar la observación en vivo sin dinero (`tbot live` + `tbot live-verdict`,
≥ 200 alertas, límite inferior de Wilson > 54,05 % y EV > 0) **midiendo precios reales de entrada y
vencimiento**, que es precisamente donde se espera que falle.

## 6. «Acertar» no es ganar: demostración

Entradas **al azar** con objetivo de ganancia de 1σ y límite de pérdida de 10σ (σ a 15 min):

| Instrumento | Objetivo alcanzado («acierto») | EV neto por operación |
|---|---|---|
| EUR/USD | **79,4 %** | −0,66 pb |
| USD/JPY | 78,4 % | −0,89 pb |
| XAU/USD | 78,8 % | −1,46 pb |
| BTC/USDT | 78,2 % | −20,8 pb |

Un 80 % de «acierto» se fabrica fácilmente con salidas asimétricas y **pierde dinero**. Por eso el
sistema exige EV neto positivo, no solo acierto alto.

## 7. Qué NO se pudo hacer

- **Observación en vivo:** no se ejecutó (requiere días con un proceso encendido y acceso directo a la
  fuente; este entorno no lo permite). Queda lista para su PC.
- **Spreads observados** en divisas: no disponibles desde GitHub (Dukascopy limitado). Puede repetirse
  el estudio localmente con `--source dukascopy`.
- **Noticias con dato real vs. consenso:** sin fuente histórica gratuita con marcas de publicación; se
  usaron horarios programados como filtro.
- **Pagos reales** de plataformas de opciones: no verificados (sin cuenta ni API).

## 8. Próximos pasos recomendados

1. No operar con dinero real. No hay configuración `VALIDADO`.
2. Si quiere seguir investigando BTC 1 min: ejecutar en su PC la observación en vivo sin dinero durante
   2–4 semanas (`README.md`, sección de uso) y juzgar con `tbot live-verdict`. Espere que la latencia real
   borre la ventaja.
3. Para divisas: plantear **nuevas** hipótesis pre-registradas (p. ej., USD/JPY 1 min) y probarlas solo
   con datos posteriores a 2026-09-01.
4. Investigar la baja cobertura de HistData en 2023 y, si es posible, repetir con Dukascopy (bid/ask).
