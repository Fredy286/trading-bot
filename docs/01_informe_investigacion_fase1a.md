# Fase 1A — Informe de investigación y protocolo pre-registrado

> **Estado del documento:** protocolo congelado **antes** de descargar o analizar datos de precios.
> Cualquier cambio posterior a este archivo queda en el historial de git y debe justificarse en
> `docs/04_registro_de_errores.md`. Los resultados empíricos van en `docs/02_resultados_empiricos.md`.

---

## 0. Resumen ejecutivo (lo que ya se sabe antes de mirar datos)

1. **El 80 % de acierto a 1 minuto no está respaldado por ninguna evidencia pública seria para
   pares de divisas líquidos.** Los estudios que reportan cifras así suelen predecir *otra cosa*
   (por ejemplo, el signo del **siguiente cambio** del precio medio en un libro de órdenes, no la
   dirección a un plazo fijo), usan datos que no estarían disponibles en el momento de decidir, o
   no descuentan costos. La literatura revisada coincide en que mejoras de acierto **no se traducen
   necesariamente en beneficio** después de costos, deslizamiento y latencia
   ([ScienceDirect 2025](https://sciencedirect.com/science/article/pii/S095741742501351X);
   [ACM MLMI 2024](https://dl.acm.org/doi/10.1145/3696271.3696272)).
2. **Una tasa de acierto de 80 % con pago de 85 % implicaría un valor esperado de +0,48 unidades por
   operación** y una fracción de Kelly de 56 % del capital por operación. Eso sería una de las
   anomalías más rentables jamás documentadas; si existiera de forma persistente y accesible con
   datos gratuitos, sería arbitrada rápidamente
   ([Neely, Weller y Ulrich — JFQA](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/adaptive-markets-hypothesis-evidence-from-the-foreign-exchange-market/9D336CDCA83233819EB5CDD0F4BC0DAA):
   las ganancias de reglas técnicas en divisas desaparecieron a inicios de los 90).
3. **Acertar la dirección no es lo mismo que ganar dinero.** Con opciones de pago fijo el umbral
   mínimo depende del pago; con contado/CFD depende del spread frente al movimiento típico. A 1
   minuto, el spread de un intermediario minorista puede ser del mismo orden que el movimiento medio
   del precio, lo que hace el umbral inalcanzable (sección 6).
4. **Las noticias a 1 minuto no son utilizables como señal direccional para un minorista.** El precio
   salta *inmediatamente* después del dato, antes incluso de que suba el volumen
   ([Chaboud, Chernenko y Wright, JEEA 2008](https://academic.oup.com/jeea/article-abstract/6/2-3/589/2295924));
   las respuestas dependen de la *sorpresa* frente al consenso
   ([Andersen, Bollerslev, Diebold y Vega, AER 2003](https://www.aeaweb.org/articles?id=10.1257%2F000282803321455151)),
   y las API de calendario accesibles actualizan el dato real con minutos de retraso
   ([ejemplo: FinanceFlowAPI, 5–10 min](https://financeflowapi.com/world_economic_calendar)). Sí son
   útiles como **filtro de riesgo** (no operar alrededor de publicaciones programadas).
5. **Regulación en Colombia:** la SFC advierte que las actividades de trading/forex del exterior **no
   pueden promocionarse** en Colombia sin su autorización y que no hay firmas autorizadas para
   promover forex ([SFC en Facebook](https://www.facebook.com/superintendencia.financiera/posts/las-actividades-de-trading-forex-o-mercado-de-valores-del-exterior-no-pueden-pro/1513155767510374/);
   [Ámbito Jurídico](https://www.ambitojuridico.com/noticias/mercantil/financiero-cambiario-y-seguros/ofrecimiento-de-forex-por-personas-no-0)).
   Las plataformas de opciones binarias de 1 minuto más conocidas (IQ Option, Quotex, Pocket
   Option) no están vigiladas por la SFC y **no ofrecen API oficial**
   ([iqoptionapi — "ONLY FOR STUDY"](https://github.com/iqoptionapi/iqoptionapi)). En la UE, la ESMA
   **prohibió** la venta de opciones binarias a minoristas en 2018
   ([ESMA](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors)).

**Conclusión preliminar (a confirmar o refutar con datos en la Fase 1B):** la hipótesis nula de
trabajo es que **no existe señal explotable a 1 minuto** en los instrumentos evaluados. El sistema se
diseña para que, si los datos lo confirman, emita «SIN SEÑAL» en lugar de forzar operaciones.

---

## 1. Qué se intentará predecir (definición exacta)

| Elemento | Definición |
|---|---|
| **Instrumentos (fijados de antemano, no se eliminan después)** | EUR/USD, GBP/USD, USD/JPY, AUD/USD, XAU/USD (oro) y BTC/USDT (cripto, como «otro instrumento» con volumen real). |
| **Fuente de cotización histórica** | Dukascopy Bank SA: velas de 1 minuto **BID y ASK** por separado ([datafeed público](https://www.dukascopy.com/swiss/english/marketwatch/historical/); [descripción del feed](https://www.dukascopy.com/wiki/en/faq/feed/)). BTC/USDT: archivos públicos de Binance (`data.binance.vision`) con volumen negociado. |
| **Precio de referencia** | Precio medio `mid = (bid + ask) / 2` por minuto (para BTC/USDT: precio de negociación, sin bid/ask). |
| **Marca temporal** | Inicio del minuto en **UTC**. La vela `t` cubre `[t, t+60 s)`. Su cierre está disponible en `t+60 s` (+ retraso del proveedor, configurable). Reportes y alertas se muestran en **America/Bogota** (UTC−5, sin horario de verano). |
| **Momento de decisión** | `τ = t + 60 s` (cierre de la vela `t`). Solo se usan datos con marca `≤ t`. |
| **Precio de entrada** | Apertura de la vela `t + d` con `d = 1` (primer precio tras la decisión). Sensibilidad con `d = 2` (≈ 1 minuto de retraso total, conservador para operación manual). |
| **Horizontes** | 1, 5, 15 y 60 minutos. Salida = cierre de la vela `t + d + h − 1`. |
| **«Sube» / «Baja»** | Sube si `mid_salida > mid_entrada`; baja si `mid_salida < mid_entrada`. |
| **Empate** | `mid_salida == mid_entrada` (a la precisión del proveedor). Regla configurable: **reembolso** (resultado 0, por defecto) o **pérdida**. Se reporta la frecuencia de empates. |
| **Cotizaciones faltantes** | Si falta alguna vela entre la entrada y la salida, la observación se marca **no evaluable** (no se rellena). Si el mercado está cerrado (> 30 min sin ticks, p. ej. fin de semana) no hay decisión. Minutos aislados sin ticks dentro de la sesión se conservan como «sin cambio». |
| **Muestreo** | Para `h = 1` se decide en cada minuto. Para `h > 1` solo en minutos múltiplos de `h` para que las etiquetas **no se solapen**. |

**Limitación declarada:** con velas de 1 minuto no se puede modelar con exactitud una latencia de, por
ejemplo, 7 segundos. Se acota con dos escenarios (`d = 1` optimista y `d = 2` pesimista) y se marca
como **caducada** toda señal cuya latencia configurada supere la vigencia máxima.

---

## 2. Fuentes de información: utilidad real, costo y latencia

| Fuente | Disponibilidad | Costo | Latencia típica | ¿Usable antes de emitir una señal de 1 min? | Evaluación |
|---|---|---|---|---|---|
| Retornos y volatilidad históricos (M1 bid/ask) | Dukascopy, HistData, OANDA/Deriv API | Gratis | Histórico | Sí (solo pasado) | Base de todo. La volatilidad **sí** es predecible (estacionalidad intradía); la dirección, mucho menos. |
| Tendencia / reversión (momentum, medias, RSI, Bollinger) | Derivado del precio | Gratis | 0 | Sí | Hipótesis a probar contra el azar; evidencia histórica de decaimiento ([Neely et al.](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1403345)). |
| Volumen | Divisas: **no hay volumen consolidado** (mercado OTC); Dukascopy solo da el volumen de su propia liquidez. Cripto: volumen real del exchange. | Gratis | 0 | Sí | Proxy débil en FX; medible en BTC. |
| Spread / liquidez | Dukascopy (bid/ask) | Gratis | 0 | Sí | Clave para costos y como filtro (spread anormal = no operar). |
| Horarios de mercado / sesiones | Calendario fijo | Gratis | 0 | Sí | La volatilidad por hora es muy estable; útil para filtrar. |
| Calendario macroeconómico (hora programada) | ForexFactory (web, sin API oficial), Trading Economics (pago), FMP (freemium) | 0 – pago | Conocido con días de antelación | **Sí, como filtro** | Útil para *no* operar en ventanas de publicación. |
| Dato publicado vs. consenso (sorpresa) | Trading Economics, FMP, FinanceFlow… | Pago | Segundos a 10 min tras la publicación en API accesibles | **No** a 1 minuto | El mercado reacciona en segundos ([Chaboud et al.](https://www.federalreserve.gov/pubs/ifdp/2007/903/ifdp903.pdf)). |
| Noticias textuales en tiempo real | Newswires institucionales (Bloomberg, Refinitiv, Dow Jones) | Muy alto | ms | Solo con infraestructura institucional | Fuera del alcance de un minorista. |
| Tipos de interés | FRED, bancos centrales | Gratis | Diario | Sí | Relevante a horizontes de días/semanas (carry), **irrelevante a 1 minuto**. |
| Eventos extraordinarios | No programables | — | — | No | Se tratan como riesgo: detección de saltos de spread/volatilidad → pausa. |
| Régimen de mercado (volatilidad) | Derivado del precio | Gratis | 0 | Sí | Se reporta desempeño por terciles de volatilidad calculados solo con pasado. |

**No se supone que más indicadores mejoren el pronóstico.** Cada bloque de variables debe demostrar
mejora fuera de muestra frente a los modelos de referencia; si no, se descarta.

### Restricciones reales de este entorno de trabajo (declaradas)

- El contenedor en la nube donde se desarrolló este proyecto **no tiene acceso de red** a Dukascopy,
  Binance, Yahoo, HistData, Deriv, FRED ni calendarios económicos (respuesta 403 del proxy). Solo
  alcanza GitHub y los registros de paquetes.
- Por eso la descarga de datos y el estudio empírico se ejecutan en **GitHub Actions** (servidores con
  internet), con resultados versionados en el repositorio. El mismo código corre en el PC local.
- **No se consultaron noticias en tiempo real, no se abrió ninguna cuenta, no se operó y no se probó
  ninguna integración con intermediarios.**

---

## 3. ¿Sirven las noticias a 1 minuto?

- Andersen et al. (2003) muestran que las sorpresas macro producen **saltos** en la media condicional
  del tipo de cambio; la reacción depende de la *sorpresa* (dato − consenso), no del dato en sí.
- Chaboud et al. (2008), con datos EBS a 1 segundo: el precio **salta inmediatamente** tras el anuncio
  con poco volumen; el volumen y la volatilidad se disparan unos 15 s después.
- Implicación: para usar noticias como señal direccional a 1 minuto se necesitaría (a) el consenso,
  (b) el dato real en milisegundos y (c) ejecución en milisegundos. Un minorista con API de calendario
  que actualiza en minutos **llega tarde**.
- **Uso que sí se evaluará:** ventanas de exclusión (de 5 min antes a 10 min después) alrededor de
  horas típicas de publicación, conocidas de antemano: 08:30, 10:00 y 14:00 hora de Nueva York
  (datos de EE. UU. y FOMC); 07:00 y 09:30 hora de Londres (datos del Reino Unido); 14:15 hora de
  Fráncfort (BCE); 11:30 hora de Sídney (Australia); 08:50 hora de Tokio (Japón). Se aplican en
  días hábiles, haya o no publicación ese día (no se usa el calendario real para no introducir
  información no disponible). Hipótesis H5.

---

## 4. Modelos: referencia primero, complejidad solo si se gana fuera de muestra

Modelos pre-registrados (hiperparámetros **fijos**, sin búsqueda):

| Tipo | Modelo | Regla |
|---|---|---|
| Referencia | Azar | Moneda con semilla fija. |
| Referencia | Dirección mayoritaria | La clase más frecuente en el tramo de entrenamiento. |
| Técnica | Momentum-1 | Misma dirección que el último minuto. |
| Técnica | Reversión-1 | Dirección contraria al último minuto. |
| Técnica | Tendencia SMA20 | Sube si `cierre > SMA(20)`. |
| Técnica | RSI(14) extremos | Sube si RSI < 30, baja si RSI > 70, si no, no opera. |
| Técnica | Bollinger(20, 2) reversión | Sube si z < −2, baja si z > 2, si no, no opera. |
| Estadístico | Regresión logística L2 (C = 1) | Variables estandarizadas con el tramo de ajuste. |
| Aprendizaje automático | HistGradientBoosting | `max_iter=200, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0`. |

Variables (todas calculadas con datos `≤ t`): retornos de los últimos 5 minutos normalizados por
volatilidad; retornos acumulados 5/15/60/240 min; volatilidad realizada 15/60/240 y su cociente; rango
de la vela; posición del cierre en la vela; distancia a SMA20/SMA60; RSI14; z de Bollinger; spread
relativo; volumen relativo; frecuencia reciente de minutos sin cambio; hora del día (seno/coseno);
día de la semana; indicador de ventana de publicación programada.

La logística o el boosting solo se prefieren a una referencia si su **valor esperado neto** fuera de
muestra es mayor y el intervalo de confianza lo respalda.

---

## 5. Sesgos y cómo se evitan

| Riesgo | Control implementado |
|---|---|
| Sesgo de anticipación (lookahead) | Variables solo con datos `≤ t`; prueba automática que **altera el futuro** y verifica que las variables pasadas no cambian. |
| Solapamiento de etiquetas | Purga: se eliminan del entrenamiento las muestras cuya etiqueta termina después del inicio del tramo de prueba; muestreo no solapado para `h > 1`. |
| Sobreajuste | Hiperparámetros fijos pre-registrados; validación walk-forward trimestral; periodo final **bloqueado**. |
| Selección oportunista de pares/horarios | Instrumentos y horarios fijados en este documento; se reportan **todos**, incluidos los malos. |
| Pruebas repetidas | Registro de cada experimento (`results/registry.jsonl`); corrección de Holm sobre todas las hipótesis; se informa el número total de configuraciones probadas ([Bailey y López de Prado, *Deflated Sharpe Ratio*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)). |
| Proveedor ≠ intermediario | La liquidación de un contrato binario usa el feed **del intermediario**, que puede diferir de Dukascopy. Se declara como limitación; en la fase de observación en vivo se compara el feed del intermediario. |
| Cambio de régimen | Resultados por trimestre y por tercil de volatilidad; monitor de deterioro en vivo que pausa alertas. |
| Calibración engañosa | Calibración isotónica ajustada en un tramo distinto del de ajuste y evaluada en datos no vistos (ECE, Brier, tabla de confiabilidad). |

---

## 6. Umbral mínimo de acierto según el contrato

### 6.1 Opciones de pago fijo («binarias», «digitales», «turbo»)

Si se arriesga 1 y se gana `b` (pago neto) o se pierde 1, el acierto mínimo (sin contar empates) es
`p* = 1 / (1 + b)`. Si los empates cuentan como pérdida y ocurren con frecuencia `q`, el acierto
mínimo entre las operaciones sin empate sube a `p* = 1 / ((1 − q)(1 + b))`.

| Pago `b` | `p*` (empate = reembolso) | `p*` (empate = pérdida, q = 10 %) | EV si el acierto fuera 80 % |
|---|---|---|---|
| 70 % | 58,82 % | 65,36 % | +0,36 |
| 80 % | 55,56 % | 61,73 % | +0,44 |
| 85 % | 54,05 % | 60,06 % | +0,48 |
| 90 % | 52,63 % | 58,48 % | +0,52 |
| 92 % | 52,08 % | 57,87 % | +0,54 |

Los pagos anunciados por plataformas de 1 minuto fluctúan por activo y hora
([comparativa](https://tradersunion.com/brokers/forex/view/pocket-option/pocket-option-vs-quotex/));
**no se han verificado** pagos reales. El sistema los recibe como parámetro.

### 6.2 Contado / CFD

Con movimiento medio absoluto `m` en el horizonte y costo total `c` (spread + comisión + deslizamiento)
por operación de ida y vuelta, el acierto mínimo aproximado es `p* ≈ 0,5 + c / (2m)`.
**Si `c ≥ m`, ni un acierto del 100 % sería rentable en promedio.** La Fase 1B medirá `m` por
instrumento, hora y horizonte, y `c` con el spread observado.

**Regla de publicación:** no basta con `p > 50 %`. Se exige `EV neto estimado ≥ margen` y que la
configuración haya superado los criterios de validación de la sección 8.

---

## 7. Hipótesis comprobables

| ID | Hipótesis | Se considera **respaldada** si… |
|---|---|---|
| H1 | Algún modelo predice la dirección a 1 min por encima del umbral de rentabilidad de una opción con pago 85 % | Límite inferior de Wilson 95 % del acierto > 54,05 %, EV con IC bootstrap > 0 y p-valor ajustado por Holm < 0,05, en validación y en el periodo bloqueado. |
| H2 | Existe algún subconjunto (umbral de confianza) con acierto ≥ 80 % | Límite inferior de Wilson ≥ 80 % con n ≥ 100 fuera de muestra y EV > 0. **Expectativa previa: no.** |
| H3 | Horizontes más largos (5–60 min) mejoran el EV neto frente a 1 min | EV neto mayor con IC que no se solapa. |
| H4 | Las reglas técnicas populares no superan al azar después de costos | Su EV neto es ≤ 0 o su IC incluye 0. |
| H5 | Excluir ventanas de publicación programada reduce pérdidas/varianza | Menor pérdida máxima y EV no inferior. |
| H6 | Los modelos estadísticos/ML superan a la mejor referencia fuera de muestra | Diferencia de EV con IC > 0. |
| H7 | Las probabilidades calibradas son fiables | ECE < 2 puntos porcentuales y bins alineados con la diagonal en datos no vistos. |

---

## 8. Protocolo de validación (pre-registro)

- **Periodo de datos:** 2021-01-01 a 2026-08-31 (UTC).
- **Desarrollo (walk-forward):** pruebas trimestrales desde 2022-T1 hasta 2025-08-31. Para cada
  trimestre se entrena con los **12 meses inmediatamente anteriores**; el último 20 % de ese tramo se
  reserva para calibrar; entre tramos se aplica una purga de `d + h` minutos.
- **Periodo final bloqueado:** 2025-09-01 a 2026-08-31. El código se niega a evaluarlo salvo con
  `--stage holdout` y un archivo de configuración congelada (`config/frozen.json`) generado de forma
  **mecánica** por la etapa de desarrollo. Se ejecuta **una sola vez**.
- **Políticas:** (A) operar todas las decisiones; (B) operar solo si `EV estimado ≥ 0,02` (binaria) o
  `EV estimado ≥ 0,25 × costo` (contado); (B+N) igual que B con exclusión de ventanas de noticias.
- **Contratos:** binaria con pago 85 % y empate reembolsado (principal); contado con spread observado
  + comisión de 0,7 pips ida y vuelta (FX), 0,07 USD/oz (oro), 0,2 % ida y vuelta (BTC).
  Sensibilidad (no son hipótesis nuevas): pago 70–95 %, empate = pérdida, `d = 2`.
- **Métricas:** número de decisiones, operaciones, descartadas (sin señal, filtradas, caducadas,
  desconexión, no evaluables), empates; acierto con IC de Wilson; rentabilidad neta; EV por operación
  con IC bootstrap por bloques diarios; reducción máxima del capital; resultados por instrumento, hora
  (America/Bogota), trimestre y régimen de volatilidad; comparación con referencias; ECE, Brier,
  tabla de confiabilidad; curva cobertura-acierto (umbrales fijados con el tramo de calibración).
- **Criterios para declarar una configuración «candidata» (todos obligatorios):**
  1. ≥ 300 operaciones fuera de muestra en desarrollo;
  2. límite inferior de Wilson 95 % del acierto > umbral `p*` (binaria) o IC 95 % del EV > 0 (contado);
  3. p-valor ajustado por Holm < 0,05 sobre **todas** las configuraciones probadas;
  4. EV positivo en ≥ 60 % de los trimestres y ningún trimestre aporta > 50 % del beneficio total;
  5. EV mayor que el de la mejor referencia.
- **Criterios de descarte:** incumplir cualquiera de los anteriores; o, en el periodo bloqueado,
  EV ≤ 0 o acierto ≤ `p*`; o, en observación en vivo, límite superior de Wilson del acierto
  acumulado < `p*` tras ≥ 50 señales → **pausa automática**.
- **Si ninguna configuración supera los criterios:** el sistema opera en modo **«SIN SEÑAL»** y solo
  ofrece investigación y monitoreo.

---

## 9. Datos necesarios, limitaciones y costos aproximados

| Necesidad | Solución | Costo | Limitación |
|---|---|---|---|
| Histórico M1 bid/ask FX y oro | Dukascopy datafeed | 0 | Es el precio de Dukascopy (ECN), no el del intermediario donde se operaría. |
| Histórico M1 cripto con volumen | Binance public data | 0 | Solo un exchange. |
| Precio en tiempo real (FX) | Deriv API (WebSocket, app_id gratuito), OANDA v20 (cuenta demo), MT5 (Windows) o IB | 0 con cuenta demo | Requiere cuenta y credenciales **que no tengo**. Disponibilidad para residentes en Colombia a confirmar por el usuario. |
| Precio en tiempo real (cripto) | Binance REST/WebSocket público | 0 | — |
| Calendario económico | CSV importable (ForexFactory exportado manualmente, o API de pago) | 0 – pago | Sin API oficial gratuita confiable. |
| Cómputo | PC personal o GitHub Actions (repos públicos) | 0 | Estudios de 1 minuto con varios años requieren minutos a horas. |

---

## 10. Fuentes consultadas

- Andersen, Bollerslev, Diebold y Vega (2003), *Micro Effects of Macro Announcements*, AER — [AEA](https://www.aeaweb.org/articles?id=10.1257%2F000282803321455151), [PDF](https://public.econ.duke.edu/~boller/Published_Papers/aer_03.pdf)
- Chaboud, Chernenko y Wright (2008), *Trading Activity and Macroeconomic Announcements in High-Frequency Exchange Rate Data*, JEEA — [OUP](https://academic.oup.com/jeea/article-abstract/6/2-3/589/2295924), [Fed IFDP 903](https://www.federalreserve.gov/pubs/ifdp/2007/903/ifdp903.pdf)
- Neely, Weller y Ulrich, *The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market*, JFQA — [Cambridge](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/adaptive-markets-hypothesis-evidence-from-the-foreign-exchange-market/9D336CDCA83233819EB5CDD0F4BC0DAA), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1403345)
- Bailey y López de Prado, *The Deflated Sharpe Ratio* — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551), [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- *Predictive modeling of foreign exchange trading signals using machine learning techniques* (2025) — [ScienceDirect](https://sciencedirect.com/science/article/pii/S095741742501351X)
- *Predicting Foreign Exchange EUR/USD Direction Using Machine Learning* (MLMI 2024) — [ACM](https://dl.acm.org/doi/10.1145/3696271.3696272)
- *From orders to prices: a stochastic description of the limit order book to forecast intraday returns* — [arXiv 2004.11953](https://arxiv.org/pdf/2004.11953) (ejemplo de «80 %» que predice el **siguiente cambio** del precio en el libro de órdenes, no la dirección a plazo fijo ni el beneficio neto)
- ESMA, prohibición de opciones binarias para minoristas (2018) — [ESMA](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors)
- Superintendencia Financiera de Colombia — [publicación sobre trading/forex del exterior](https://www.facebook.com/superintendencia.financiera/posts/las-actividades-de-trading-forex-o-mercado-de-valores-del-exterior-no-pueden-pro/1513155767510374/), [¿De qué se trata el mercado forex?](https://www.superfinanciera.gov.co/publicaciones/10115325/de-que-se-trata-el-mercado-forex/), [advertencias por ejercicio ilegal](https://www.superfinanciera.gov.co/publicaciones/10107761/sala-de-prensaadvertencias-y-medidas-administrativas-por-ejercicio-ilegal-de-actividad-financiera-no-se-deje-enganar-10107761/)
- Ámbito Jurídico, *Ofrecimiento de Forex por personas no autorizadas se considera ilegal* — [enlace](https://www.ambitojuridico.com/noticias/mercantil/financiero-cambiario-y-seguros/ofrecimiento-de-forex-por-personas-no-0)
- Dukascopy — [feed de precios](https://www.dukascopy.com/wiki/en/faq/feed/), [exportación histórica](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- Deriv — [documentación de la API](https://developers.deriv.com/docs/), [índices sintéticos (RNG)](https://deriv.com/markets/derived-indices/synthetic-indices)
- IQ Option API no oficial — [GitHub](https://github.com/iqoptionapi/iqoptionapi)
- Interactive Brokers API — [IBKR](https://www.interactivebrokers.com/en/trading/ib-api.php); OANDA v20 — [developer.oanda.com](https://developer.oanda.com/rest-live-v20/introduction/); MetaTrader 5 Python — [MQL5](https://www.mql5.com/en/docs/python_metatrader5)

---

## Enmienda 1 — cambio de fuente para divisas y oro (2026-09-30, ANTES de ver resultados de divisas)

**Motivo verificable.** Desde los servidores de GitHub Actions, el datafeed de Dukascopy respondió
13–17 s por archivo y luego HTTP 503 y 429 (limitación de tasa explícita) — ejecuciones
`36666769740` y `36667788455` del workflow, registradas en `docs/04_registro_de_errores.md`. Descargar
los ~15 000 archivos diarios necesarios así es inviable. HistData respondió con normalidad.

**Cambio.** Para EUR/USD, GBP/USD, USD/JPY, AUD/USD y XAU/USD el estudio ejecutado en GitHub usa
**HistData.com, velas M1 de precio BID** (zona EST fija, convertida a UTC). BTC/USDT sigue con Binance.
Todo lo demás del protocolo (hipótesis, particiones, modelos, políticas, criterios) queda **igual**.

**Consecuencias declaradas:**
1. La dirección se mide con el precio **BID**, no con el precio medio. Con spread aproximadamente
   constante dentro de un minuto la diferencia es pequeña, pero no nula.
2. El spread **no se observa**: para el contrato de contado se usa un spread **supuesto optimista**
   tipo cuenta ECN (EUR/USD 0,2 pips; GBP/USD 0,5; USD/JPY 0,3; AUD/USD 0,4; oro 0,25 USD) más la
   comisión pre-registrada. Si el contado no es rentable ni con costos optimistas, la conclusión es más
   robusta; si lo fuera, habría que confirmarlo con spreads observados. El informe añade una tabla de
   sensibilidad del umbral a costos de 0,5–10 pb que no depende del supuesto.
3. Las variables de spread (`spread_vol`, `spread_rel`) quedan constantes y no aportan información.
4. HistData omite los minutos sin ticks; se reconstruyen como velas planas al último cierre conocido
   (sin información futura) si el hueco dura < 30 min; huecos más largos = mercado cerrado.
5. El contrato binario no depende del spread, por lo que la hipótesis principal (H1) no se ve afectada
   por el supuesto de costos.

El código conserva el descargador de Dukascopy (bid/ask) para ejecutar el mismo estudio desde un PC
personal, donde la limitación de tasa probablemente no aplique (`tbot data download --source dukascopy`).

## Aclaración 1 — criterio del periodo bloqueado (2026-09-30, después de desarrollo y ANTES del periodo bloqueado)

El protocolo contenía dos redacciones: la de descarte (sección 8: «EV ≤ 0 o acierto ≤ p*») y la de
H1 («límite inferior de Wilson > p*, IC del EV > 0 y Holm < 0,05, en validación y en el periodo
bloqueado»). Se adopta la **más exigente** para otorgar `VALIDADO_HOLDOUT`: límite inferior de Wilson
95 % del acierto > umbral, límite inferior del IC 95 % del EV > 0 y p-valor de Holm < 0,05 sobre la
familia de candidatas congeladas. El criterio mínimo se reporta solo como información. Además se
informa si el EV del periodo bloqueado cae por debajo del IC de desarrollo (deterioro). Implementado en
`research/report.py::holdout_verdict` y probado antes de ejecutar el periodo bloqueado.

Observación registrada antes del periodo bloqueado: en desarrollo, las candidatas de BTC/USDT a 1 y
5 minutos **pierden la ventaja con 60 s de retraso** en la entrada (sensibilidad `B_lat60`), por lo que
serían inoperables con latencia humana aunque superen el periodo bloqueado.

## Aclaración 2 — observación en vivo sin dinero (2026-10-03, ANTES de iniciarla)

La sección 8 solo fijaba la regla de **pausa** en vivo. Los criterios para **aprobar** la observación
(≥ 200 alertas, límite inferior > p*, EV > 0) estaban en el código, pero podían relajarse por línea de
comandos. Además, consultar el veredicto cada día y parar en el primer «aprobado» infla los falsos
positivos: en una simulación sin ventaja real (20 000 repeticiones, 28 días, 40–160 alertas/día) se
aprueba por azar el 10,5–12,5 % de las veces, frente a 2,9 % con una muestra fija de 200. Se fijan aquí, **antes de ver
ningún resultado en vivo del modelo real**. La única ejecución contra Binance hasta hoy usó un modelo
sintético con alertas forzadas, para probar la conexión; no aporta información sobre la ventaja.

1. **Objeto:** BTC/USDT, horizonte 1 min, modelo `gbm` entrenado con
   `tbot train --symbol BTCUSDT --horizon 1 --model gbm` con los 12 meses completos disponibles
   (2025-09-01 a 2026-08-31; el archivo de septiembre de Binance aún no estaba publicado). Se observa
   **un único entrenamiento**, registrado antes de empezar en `config/observacion_en_vivo.json`:
   `BTCUSDT-h1-gbm-2026-08-31-e436ef`. `tbot live` se niega a observar otro y `tbot live-verdict` solo
   cuenta ese (no hay opción para elegir otro después).
2. **Regla de decisión = la política validada** en el periodo bloqueado: alerta si el EV estimado con
   la probabilidad calibrada es ≥ 0,02 (pago supuesto 85 %, empate reembolsado), excluyendo las
   ventanas de publicación programada (BN). El filtro adicional del motor (límite inferior del acierto
   histórico de señales parecidas > p*) **no** formaba parte de la política validada: en la observación
   no bloquea. Se anota en cada alerta (`ic_filter_ok`) para un análisis **secundario** que no decide.
   Los parámetros de la política (contrato binaria, pago 0,85, empate reembolsado, margen de EV 0,02,
   horario 0–24 h, espera 1 s, antigüedad máxima de los datos 11 s) quedan en el mismo registro y
   `tbot live` los **impone** sobre el `.env`. Cada fila del libro guarda la política con que se midió;
   las filas con otra política no cuentan. El umbral p* sale del contrato registrado, no del `.env`.
3. **Medición:** la decisión se toma 1 s después del cierre de la vela **según el reloj de Binance**
   (el desfase del PC se mide cada hora y se corrige; Binance publica la vela definitiva a ~0,3 s,
   medido el 2026-10-03). El precio de entrada es el último negociado en Binance obtenido en ese
   ciclo; el de vencimiento, el del ciclo del minuto siguiente. La duración real entre ambos precios
   debe estar en 60 ± 10 s; si no, «no evaluable». Precio igual = empate (reembolso). Si en un ciclo no
   llega la vela nueva, no se repite la decisión anterior: cada vela cuenta una sola vez.
4. **Muestra fija:** las **primeras 3 500 alertas sin empate** medidas con precio real, en orden de
   tiempo. El veredicto se juzga **una sola vez** sobre esa muestra; antes de completarla es
   «muestra insuficiente» y no puede aprobar. Consultarlo antes no cambia el resultado final. Si a
   las **8 semanas** de iniciada la observación la muestra no está completa, el resultado es «no
   concluyente» y no aprueba.

   *Corrección del mismo día, antes de iniciar la observación y sin ningún dato en vivo:* la primera
   redacción de esta aclaración fijaba 200 alertas, el valor que tenía el código. Al entrenar el
   modelo real se calculó la potencia (simulación de 4 000 repeticiones, empates 1,5 %): con 200
   alertas, una ventaja igual a la del periodo bloqueado (56,4 %) solo aprobaría el 11 % de las
   veces; con 3 500, el 80 %. La probabilidad de aprobar sin ventaja es ~2,3 % en ambos casos. Con
   ~153 alertas/día (ritmo de la política BN en el periodo bloqueado: 55 955 en 12 meses), 3 500 se
   reúnen en ~3 semanas. Conteo con el modelo registrado (solo cuántas alertas, sin mirar aciertos):
   ~240/día de media en el tramo de calibración (mediana 141; los fines de semana triplican a los días
   laborables), así que la muestra se completaría en ~2–4 semanas. Los empates observados en todos los
   minutos son ~4–5 % (la simulación supuso 1,5 %); no cambian el tamaño, porque la muestra cuenta
   alertas **sin** empate. El filtro adicional del punto 2 aprobó el 100 % de las alertas del modelo
   registrado en esos conteos, así que el análisis secundario probablemente coincidirá con el principal.
5. **Criterio de aprobación (todos):** límite inferior de Wilson 95 % del acierto > p* = 1/(1+0,85) =
   54,05 %, y EV medio > 0 en la misma muestra (empates con PnL 0).
6. **Pausa (sección 8):** si tras ≥ 50 señales el límite superior queda por debajo de p*, el monitor
   pausa. Las alertas que se habrían emitido se siguen evaluando como hipotéticas y cuentan para la
   muestra (la pausa no detiene la observación ni la convierte en un resultado mejor).
7. **Se reporta siempre:** alertas no evaluables por motivo, duración real y retraso medidos, desfase
   del reloj, desglose por hora de Bogotá y el resultado secundario con el filtro adicional.
8. **Consecuencia:** si aprueba → estado `VALIDADO` (procedimiento BTC/USDT h1 gbm, política BN) y
   solo entonces podría considerarse la Fase 2, con autorización expresa del usuario. Si no aprueba →
   BTC/USDT queda en «SIN SEÑAL». Expectativa declarada de antemano: la latencia real probablemente
   borra la ventaja.
9. **Fuera de la observación:** las pruebas manuales que el usuario haga en cuentas demo de cualquier
   plataforma no cuentan para este veredicto, porque usan otro feed de precios y otra latencia.

Implementado en `config/observacion_en_vivo.json` (registro), `signals/monitor.py::fixed_sample`,
`cli.py::cmd_live_verdict` (sin opciones para cambiar entrenamiento, muestra ni umbral; informa lo del
punto 7), `live/runner.py::run_live` (impone el registro) y `signals/registry.py::validation_status_for`
(solo valida el veredicto del entrenamiento y la política registrados, con la muestra fija de 3 500 y
el umbral p* del contrato registrado). Pruebas en `tests/test_alerts_system.py`.

## Enmienda 2 — la observación en vivo se sustituye por datos de 1 segundo (2026-10-03, ANTES de descargarlos)

**Motivo:** el usuario no puede dejar el portátil encendido semanas. La observación en vivo de la
Aclaración 2 se detuvo el 2026-10-03 a las 21:01 UTC por su decisión. Sus 103 alertas evaluadas se
conservan en `runtime/live`, **no se han inspeccionado** y no deciden nada (se informarán aparte).
Binance publica gratis las velas de **1 segundo** de BTC/USDT (archivos diarios). Con ellas se mide
exactamente lo mismo que en vivo, con datos que el modelo nunca vio, sin tener un equipo encendido.

**Datos de evaluación:** velas de contado de BTC/USDT de 1 minuto (para las variables) y de 1 segundo
(para los precios) **desde el 2026-09-01 00:00 UTC**. El entrenamiento del modelo registrado terminó el
2026-08-31 23:58 y ninguna evaluación usó esos datos. Lo único que se vio de ese periodo: conteos de
alertas (sin aciertos) del 2026-09-30 al 2026-10-03 hechos por un revisor, la estructura de un archivo
y las 103 alertas en vivo del 2026-10-03, cuyos resultados no se miraron.

**Procedimiento (el mismo código que en vivo):** se reproduce minuto a minuto `SignalEngine` +
`AlertLoop` con el modelo `BTCUSDT-h1-gbm-2026-08-31-e436ef` y la política registrada en
`config/observacion_en_vivo.json`, sin ningún cambio.
- **Decisión:** 1 s después del cierre de cada vela, con las velas de 1 minuto ya cerradas.
- **Entrada:** el último precio negociado antes de cierre + 2 s, es decir, el cierre de la vela de 1 s que
  empieza en +1 s. En vivo se midió ~1,5 s; se usa +2 s para no favorecer al modelo.
- **Vencimiento:** el último precio negociado antes de cierre + 62 s, lo que da una duración de 60 s.
- **Velas de 1 s sin operaciones:** se toma la última anterior, hasta 5 s antes; si no hay ninguna, la
  alerta es «no evaluable».
- **Empate:** precio igual, que se reembolsa.

**Muestra y criterio (sin cambios respecto a la Aclaración 2):**
- Muestra: las primeras **3 500 alertas sin empate** desde el 2026-09-01, en orden de tiempo.
- Aprobación: límite inferior de Wilson 95 % > 54,05 % y EV medio > 0.
- Plazo: si con los datos hasta el 2026-10-27 (8 semanas) no se completa, el resultado es «no
  concluyente».
- Sensibilidad informativa, que no decide: entrada a +1, +3, +5, +10 y +30 s, y pago del 80 %.

**Consecuencia:** si aprueba, el procedimiento pasa a `VALIDADO` **solo para una eventual
automatización**, que el usuario hoy no quiere y que exigiría su autorización expresa. Si no aprueba,
BTC/USDT a 1 minuto queda en «SIN SEÑAL».

**Ejecución:** la primera reproducción en el portátil se interrumpió el 2026-10-03 a las 21:44 UTC
(consola cerrada, con el equipo en batería), en el minuto simulado 2026-09-12 08:38. Sus resultados **no se
inspeccionaron** y no cuentan. La ejecución oficial se hace en GitHub Actions
(`.github/workflows/replay.yml`) con el mismo código y el modelo registrado copiado en
`config/modelos/BTCUSDT_h1_gbm.pkl`. Su SHA-256 queda en el registro y la reproducción lo verifica.

**Resultado (GitHub Actions, run 37178839251, commit 66bd077) — PENDIENTE DE VERIFICACIÓN ADVERSARIA:**
muestra fija de 3 500 alertas sin empate (1–~16 de septiembre de 2026), acierto **57,63 %** (límite inferior
95 % 55,98 % > 54,05 %), EV **+0,060**, entrada a +2,0 s y duración de 60,0 s en todas, sin alertas no
evaluables. Según el criterio registrado, **aprueba**. Sensibilidad informativa: +1 a +3 s → 56,8–57,6 %;
+5 a +10 s → 56,4–56,5 % (límite inferior ≈ 54,7 %); +30 s → 55,4 % (límite inferior 53,8 %, no
supera). Ese EV supone empate reembolsado; con empate = pérdida sería negativo (empates 8,9 %). Las 103
alertas en vivo del 2026-10-03 (informativas): 81 sin empate, 61,7 % [50,8–71,6 %].
**Verificación adversaria (2026-10-04, independiente del código de la reproducción; script fuera del
repositorio sobre el libro del artefacto del run 37178839251):**
- **Fuga de información: no hay.** La probabilidad recalculada con la serie completa de septiembre (incluido
  el futuro) en la vela que cierra en el instante de decisión coincide con la del libro (diferencia máxima
  1e-15); con la vela siguiente no coincide (diferencia mediana 0,05). Placebo con dirección aleatoria sobre
  las mismas alertas: 50,32 %.
- **Precios y resultados: correctos.** Entrada y vencimiento recalculados desde las velas de 1 s coinciden
  con el libro en el 100 % de las 6 229 alertas; muestra fija 57,63 %, EV +0,060, igual que el veredicto.
- **Pero la ventaja es menor y menos estable que el titular:**
  | Tramo (entrada +2 s, pago 85 %, empate reembolsado) | n sin empate | Acierto [IC95] | EV |
  |---|---|---|---|
  | Muestra fija (1–~16 sep, la que decide) | 3 500 | 57,63 % [55,98–59,26] | +0,060 |
  | Después de la muestra (~16 sep – 2 oct, control) | 2 219 | 54,12 % [52,04–56,19] | +0,001 |
  | Todo el periodo | 5 719 | 56,27 % [54,98–57,55] | +0,038 |
  | Fin de semana / laborable (todo el periodo) | 2 885 / 2 834 | 58,37 % / 54,13 % | +0,069 / +0,001 |
  Intervalo bootstrap por días (32 días): 54,32–57,81 %. 12 de 32 días por debajo de 54,05 %. Un tercio
  de las alertas son de minutos consecutivos. Entrada a +0/+1/+5/+10/+30/+60 s (todo el periodo):
  54,6/55,7/55,5/55,2/53,8/52,4 %.
- **Conclusión:** el resultado registrado es **auténtico** (no es un error) y el criterio se cumple, pero la
  estimación honesta para el futuro es **~55–56 % con entrada inmediata, cerca del punto de equilibrio
  entre semana y en la segunda mitad de septiembre**. El desglose por fin de semana es *post hoc*: no se
  usa como regla sin confirmarlo en datos nuevos (Estudio 5). No se recomienda operar con dinero real.

**Limitaciones declaradas:**
- Supone que el bucle habría funcionado todos los minutos, sin cortes.
- Mide con el precio de Binance, no con el del intermediario.
- La latencia real de un sistema automático (+2 s) es imposible a mano.

## Estudio 2 — señales manuales con 1 minuto de anticipación (pre-registro, 2026-10-03)

**Motivo (decisión del usuario, 2026-10-03):** no automatizar. El usuario operará a mano en cualquier
intermediario y necesita, para cada señal, la hora de apertura con su zona horaria, el instrumento, la
duración y la dirección, con **al menos 1 minuto de anticipación**. Prioriza acertar y ganar; el
instrumento y la duración pueden ser los que resulten más predecibles.

**Equivalencia con el estudio.** La señal se calcula al cierre de la vela de decisión (minuto `t`) y la
entrada ocurre en la apertura de la vela `t+2`, es decir, 60 s después. Es exactamente la política
`B_lat60` ya calculada en la Fase 1B: EV estimado ≥ 0,02, binaria con pago 85 % y empate reembolsado,
y etiquetas con retraso de entrada 2. En la Fase 1B era una política de **sensibilidad**, no elegible
como candidata, así que estas hipótesis son **nuevas**.

**Regla de selección (mecánica, solo con desarrollo, `results/dev/all_evaluations.csv`):** entre las
48 configuraciones binarias `B_lat60` (6 instrumentos × 4 horizontes × 2 modelos), son hipótesis las
que cumplen los 5 criterios de la sección 8, con Holm calculado **dentro de esas 48**. Resultado
(calculado antes de este registro):

| Hipótesis | Instrumento | Duración | Modelo | Desarrollo: operaciones, acierto, límite inferior 95 %, EV | Holm (48) |
|---|---|---|---|---|---|
| M1 | BTC/USDT | 15 min | logit | 30 856; 55,37 %; 54,82 %; +0,024 | 0,00008 |
| M2 | BTC/USDT | 60 min | logit | 5 914; 56,48 %; 55,21 %; +0,045 | 0,0045 |

AUD/USD a 15 y 5 min (gbm) tenían buen acierto, pero no superan Holm (p ajustado 0,15 y 0,21).
**No** se incluyen.

**Confirmación 1: periodo bloqueado (2025-09-01 a 2026-08-31).** Las filas `B_lat60` de M1 y M2 se
calcularon en la ejecución del periodo bloqueado (`results/holdout/all_evaluations.csv`), pero **no se
han leído para esta decisión**; se leen por primera vez después de este registro. Advertencia
honesta: ese periodo ya se usó una vez para otras hipótesis y en sesiones anteriores se miraron otras
de sus filas (USD/JPY 1 min y BTC 1 min con retraso). Por eso no es un periodo «virgen», aunque sí es
fuera de muestra para estas dos hipótesis, elegidas sin él. Criterio estricto (Aclaración 1), para
cada hipótesis: límite inferior de Wilson 95 % del acierto > p* = 54,05 %, límite inferior del IC 95 %
del EV > 0 y p de Holm < 0,05 entre las 2. Se informa además si el EV cae por debajo del IC de
desarrollo (deterioro).

**Consecuencias:**
1. La que no confirme queda descartada. Si ninguna confirma: «SIN SEÑAL» también para el modo manual.
2. La que confirme pasa a **señales manuales experimentales**: formato «instrumento | ABRIR a las HH:MM:00
   (hora de Colombia, UTC−5) | duración | ARRIBA/ABAJO», emitidas ~58 s antes de la apertura, solo para
   **cuenta demo** mientras no esté validada en vivo. El usuario debe configurar su intermediario en
   UTC−5 o convertir la hora.
3. **Confirmación 2 (definitiva): observación en vivo sin dinero** con precios reales de Binance (entrada
   en el precio a la hora indicada, vencimiento a la duración indicada). Antes de iniciarla se fijará
   con fecha su tamaño de muestra mediante un cálculo de potencia. Advertencia anticipada: con efectos de
   este tamaño (55–56 % frente a 54,05 %), una confirmación con 80 % de potencia requiere miles de
   operaciones (≈ 11 000 para M1 y ≈ 3 300 para M2), es decir, **más de un año** al ritmo de desarrollo
   (~23 y ~4,5 señales al día). La observación en vivo servirá sobre todo para detectar fallos graves
   (feed, horario, ejecución), no para confirmar la ventaja con rapidez.
4. Expectativa declarada: aunque confirme, el acierto esperado es **~55–56 %, no 80 %**, con una ganancia
   esperada pequeña (+0,02 a +0,045 por unidad apostada) y medida con el precio de Binance, no con el del
   intermediario donde se opere.

**Resultado de la confirmación 1 (leído después del commit `23a59da`, aplicado mecánicamente):**

| Hipótesis | Operaciones | Acierto | Límite inferior 95 % | EV [IC 95 %] | p | ¿Confirma? |
|---|---|---|---|---|---|---|
| M1 BTC/USDT 15 min | 4 187 | 54,15 % | 52,64 % | +0,002 [−0,027; +0,028] | 0,46 | **No** (y deterioro: EV bajo el IC de desarrollo) |
| M2 BTC/USDT 60 min | 0 | — | — | — | — | **No** (el modelo no generó ninguna señal en el año) |

**Conclusión:** ninguna configuración es predecible con 1 minuto de anticipación según la evidencia
disponible. El modo manual queda en **«SIN SEÑAL»**. No se emiten señales manuales del Estudio 2.

## Estudio 3 — información nueva para señales manuales (pre-registro, 2026-10-03, ANTES de calcularla)

**Pregunta:** ¿la información que el sistema nunca usó (flujo de órdenes agresor de contado y de futuros,
prima y financiación del perpetuo, y el otro activo) permite acertar la dirección a 15 minutos entrando
1 minuto después de la señal? La revisión previa (docs/02, sección 6.3) anticipa que **probablemente no**.
Expectativa declarada: «SIN SEÑAL».

**Hipótesis (familia de 2, Holm entre ellas):**
- **H3-BTC:** BTC/USDT.
- **H3-ETH:** ETH/USDT.

**Diseño común a las dos hipótesis:**
- **Duración:** 15 minutos.
- **Decisión:** al cierre de las velas que empiezan en minutos múltiplos de 15 (UTC).
- **Entrada:** apertura de la vela `t+2`, es decir, 1 minuto después de la señal. Etiquetas con retraso 2.
- **Precio de referencia:** contado de Binance.
- **Contrato:** binaria, pago 85 %, empate reembolsado; p* = 54,05 %.
- **Política:** B, es decir, EV estimado ≥ 0,02 con la probabilidad calibrada (isotónica por bins, como en
  la Fase 1B).
- **Modelo:** el `logit` del proyecto (estandarización + regresión logística, C = 1).
  - Modelo de **referencia:** solo las variables de precio actuales (`FEATURES`).
  - Modelo **de prueba:** las mismas variables más el bloque nuevo fijo, que se describe abajo.
- **Validación:** walk-forward idéntico a la sección 8.
  - Pruebas trimestrales del 2022-01-01 al 2025-08-31.
  - Entrenamiento con los 12 meses anteriores: el 20 % final para calibrar y purga entre tramos.
  - El periodo 2025-09 → 2026-08 no se usa en esta fase.

**Bloque nuevo (17 variables, fijadas ahora).** Todas se calculan con datos de minutos que terminan en el
cierre de la vela de decisión:

| Grupo | Variables | Definición |
|---|---|---|
| Flujo agresor en contado | `tib_s_5`, `tib_s_15`, `tib_s_60`, `tib_s_240` | 2·Σ compras agresoras / Σ volumen − 1 en los últimos 5, 15, 60 y 240 min (columna `taker_buy_base`) |
| Flujo agresor en el perpetuo USD-M | `tib_p_5`, `tib_p_15`, `tib_p_60`, `tib_p_240` | Lo mismo, con las velas del perpetuo |
| Diferencia de flujo | `tib_d_15`, `tib_d_60` | Perpetuo menos contado, a 15 y 60 min |
| Prima del perpetuo | `prem_c`, `prem_d15`, `prem_d60` | Cierre de la prima en la vela de decisión y su cambio en 15 y 60 min |
| Financiación | `fund` | Última tasa liquidada con `calc_time` ≤ cierre de la vela de decisión |
| Otro activo (ETH para BTC, BTC para ETH) | `x_r5`, `x_r15`, `x_r60` | Rendimientos del otro activo en 5, 15 y 60 min |
| Diferencia con el otro activo | `x_rel15`, `x_rel60` | Rendimiento propio menos el del otro, en 15 y 60 min |

*Nota del mismo día, antes de calcular nada:* el texto de arriba dice «17 variables», pero la tabla
enumera **19** por nombre (el conteo estaba mal). Se usan las 19 de la tabla, que es la lista explícita.
Además, «etiquetas con retraso 2» se aplica tanto al ajuste como a la evaluación de los dos modelos.
Registro de errores, ítem 38.

**Criterios para «pasa la fase de desarrollo»** (los 5, para cada hipótesis):
1. ≥ 300 operaciones.
2. Límite inferior de Wilson 95 % > 54,05 %.
3. p de Holm < 0,05 entre las 2 hipótesis.
4. EV > 0 en ≥ 60 % de los trimestres y ningún trimestre aporta > 50 % del beneficio.
5. **Mejora frente al modelo de referencia en las mismas decisiones.** Hacen falta las dos condiciones:
   - IC 95 % por bootstrap de bloques diarios de la diferencia de log-loss (referencia − prueba) > 0;
   - EV de la prueba ≥ EV de la referencia.

   Sustituye a «supera la mejor referencia de reglas», porque aquí la pregunta es si la información
   nueva aporta.

**Si alguna pasa:**
1. **Filtro no confirmatorio** en 2025-09 → 2026-08, periodo ya usado, declarado: se sigue solo si el
   acierto puntual es > 54,05 % y el log-loss es mejor que el de referencia.
2. **Confirmación limpia** con datos posteriores al 2026-09-01, evaluada con los archivos de Binance (sin
   equipo encendido):
   - muestra fija de 5 136 operaciones por hipótesis (potencia 80 % si el acierto real es ≥ 56 %);
   - fecha límite 2027-09-30, y si no se completa, «no concluyente»;
   - controles de inutilidad con 1 700 y 3 400 operaciones, solo para parar, nunca para aprobar antes.

**Si ninguna pasa:** se cierra con «SIN SEÑAL».

**Fuera de la familia (solo informativo):** GBM, duraciones de 5 y 60 min y efecto del cuarto de hora.
Las divisas no entran (HistData no tiene volumen agresor).

**Resultado de la fase de desarrollo (commit 86faa7c; la primera ejecución no vale, ítem 39):**

| Hipótesis | Modelo | Operaciones | Acierto [lím. inf. 95 %] | EV [IC 95 %] | Trimestres EV > 0 | Mejora de log-loss [IC 95 %] |
|---|---|---|---|---|---|---|
| H3-BTC | solo precio (referencia) | 30 837 | 55,67 % [55,12 %] | +0,030 [+0,020; +0,041] | 87 % | — |
| H3-BTC | precio + bloque nuevo | 33 855 | 55,11 % [54,58 %] | +0,020 [+0,010; +0,029] | 67 % | −0,00009 [−0,00030; +0,00011] |
| H3-ETH | solo precio (referencia) | 32 168 | 55,35 % [54,80 %] | +0,024 [+0,014; +0,034] | 87 % | — |
| H3-ETH | precio + bloque nuevo | 29 234 | 55,29 % [54,72 %] | +0,023 [+0,012; +0,033] | 79 % | −0,00020 [−0,00041; −0,00001] |

**Veredicto: ninguna hipótesis pasa.** Falla el criterio 5: la información nueva no mejora la predicción
(en ETH la empeora de forma significativa) ni la ganancia esperada. **Estudio 3: SIN SEÑAL.**

## Estudio 4 — ETH/USDT a 15 min, solo precio, 1 min de anticipación (pre-registro, 2026-10-03)

**Origen:** en la fase de desarrollo del Estudio 3, el modelo de **referencia** de ETH (solo variables de
precio) cumplió los criterios 1–4 de la sección 8 con entrada 1 minuto después de la señal. Para
ETH/USDT el periodo 2025-09-01 → 2026-08-31 **nunca se usó**: ni en la Fase 1B (que no incluía ETH) ni
en los Estudios 2–3. Es, para esta hipótesis, un periodo de confirmación limpio. Advertencia
declarada: la combinación análoga de BTC (Estudio 2, M1) bajó de 55,4 % en desarrollo a 54,15 % en ese
periodo.

**Hipótesis única H4-ETH:** ETH/USDT, 15 min, decisión al cierre de las velas de minutos múltiplos de 15
(UTC), entrada en la apertura de `t+2` (1 min después), `logit` con solo `FEATURES`, etiquetas con
retraso 2, política B (EV ≥ 0,02), binaria 85 % con empate reembolsado. Mismo código que el Estudio 3
(`research/study3.py`, modelo de referencia).

**Confirmación:** walk-forward trimestral en 2025-09-01 → 2026-08-31 (12 meses de entrenamiento
anteriores, 20 % de calibración, purga). Para confirmar debe cumplir los tres criterios estrictos
(Aclaración 1):
- límite inferior de Wilson 95 % > 54,05 %;
- límite inferior del IC 95 % del EV > 0;
- p < 0,05 (una sola hipótesis).

Se informa además el deterioro frente al desarrollo y la sensibilidad con pago del 80 %.

**Consecuencias:**
- **Si confirma:** señales manuales **experimentales, solo para cuenta demo**, con el formato «ETH/USD |
  ABRIR a las HH:MM:00 (hora de Colombia, UTC−5) | 15 minutos | ARRIBA/ABAJO». Seguimiento con datos
  posteriores al 2026-09-01, evaluados con los archivos de Binance, sin necesidad de un equipo encendido.
- **Si no confirma:** ETH también queda en «SIN SEÑAL».

**Resultado (commit 41ec483, aplicado mecánicamente):**

| Periodo | Operaciones | Acierto [lím. inf. 95 %] | EV [lím. inf. IC 95 %] |
|---|---|---|---|
| Desarrollo 2022-01 → 2025-08 | 32 168 | 55,35 % [54,80 %] | +0,024 [+0,014] |
| Confirmación 2025-09 → 2026-08 | 3 550 | **52,87 % [51,23 %]** | **−0,022 [−0,052]** |

**No confirma** (falla los tres criterios) y hay deterioro claro frente al desarrollo. **Estudio 4: SIN
SEÑAL.** Es el mismo patrón que BTC en el Estudio 2: ventajas de ~55 % hasta 2025 que desaparecen en el
último año.

## Estudio 5 — confirmación en datos nuevos, con entrada manual realista (pre-registro, 2026-10-04)

**Origen:** la Enmienda 2 aprobó y la verificación adversaria confirmó que no hay errores, pero la ventaja
cae a ~54 % en la segunda mitad de septiembre y entre semana. El desglose por fin de semana surgió
*después* de mirar los datos, así que solo vale como hipótesis nueva. El usuario operaría **a mano**: la
alerta aparece ~1,5 s después del cierre y necesita unos segundos para pulsar. Por eso se evalúa con
entrada a **+10 s**.

**Datos:** solo velas de Binance (1 min y 1 s) **desde el 2026-10-04 00:00 UTC**, que nadie ha visto (el
libro de septiembre termina el 2026-10-02 y las 103 alertas en vivo son del 2026-10-03). Se evalúan con
la misma reproducción de GitHub Actions (`tbot replay --entry-delay-s 10`), sin el portátil.

**Sin cambios:** modelo `BTCUSDT-h1-gbm-2026-08-31-e436ef` (mismo SHA-256), política registrada (EV ≥ 0,02,
todas las horas), duración 60 s, pago 85 %, empate reembolsado, código de la Enmienda 2.

**Hipótesis (corrección de Holm, α = 0,05, pruebas binomiales unilaterales frente a 54,05 %):**
- **H5a (todas las horas):** muestra fija = las primeras **3 500** alertas sin empate desde el 2026-10-04.
- **H5b (solo sábado y domingo, en UTC):** muestra fija = las primeras **2 500** alertas sin empate de fin
  de semana desde el 2026-10-04, tomadas del mismo libro.

Cada hipótesis aprueba si, además de Holm, cumple: límite inferior de Wilson 95 % > 54,05 % y EV > 0. Se
informa sin decidir: entrada a +2, +5 y +20 s, pago del 80 % y desglose por día.

**Plazo:** si al **2026-12-13** (10 semanas) no se completa una muestra, esa hipótesis queda «no
concluyente».

**Consecuencias:**
- **Si aprueba H5a:** señales manuales experimentales para **cuenta demo**, a cualquier hora, con el
  formato «BTC/USD | ENTRAR YA (antes de 10 s) | 1 minuto | ARRIBA/ABAJO | hora de Colombia».
- **Si solo aprueba H5b:** lo mismo, pero solo sábados y domingos.
- **Si no aprueba ninguna:** BTC a 1 minuto queda «SIN SEÑAL» también para uso manual.

En ningún caso se usa dinero real sin autorización expresa. Antes, una prueba en demo debe comprobar que
el precio del intermediario sigue al de Binance, que el empate se reembolsa y que el pago es ≥ 85 %.

*Nota de implementación (2026-10-24, antes de reproducir ningún dato posterior al 2026-10-03).* Código:
`tbot study5-verdict` (`live/study5.py`) y el flujo `.github/workflows/estudio5.yml`, que se ejecuta a
mano. Se precisan cinco puntos que el texto dejaba abiertos:
1. **Fin de semana:** sábado o domingo en UTC según la vela de decisión (hora de la alerta).
2. **Plazo:** cuentan las alertas de todo el 2026-12-13 (UTC), es decir, hasta el 2026-12-14 excluido.
3. **Alertas válidas:**
   - solo el modelo, el método y la política registrados;
   - una alerta por vela de decisión;
   - entrada a +10 s (si el libro tiene otra, el código se detiene).
4. **Muestra incompleta al vencer el plazo:** esa hipótesis es «no concluyente» y entra en Holm con p = 1.
5. **Una sola evaluación:** mientras falte alguna muestra y no haya vencido el plazo, el comando solo
   informa conteos (nunca aciertos) y el flujo no guarda el libro. El veredicto se calcula una vez, con las
   dos muestras completas o al vencer el plazo.

La sensibilidad informativa usa entradas a +2, +5, +10 y +20 s y pagos del 85 % y 80 %. Además, la
reproducción descarga las velas de 1 min desde 3 días antes del inicio, para el calentamiento de las
variables (antes dependía del histórico mensual, que no cubre el 1–3 de octubre).

**Enmienda al Estudio 5 (2026-10-24, a pedido del usuario, ANTES de reproducir datos posteriores al
2026-10-03).**
- **Motivo:** la muestra de fin de semana (H5b) no se completa hasta ~2026-11-22. La de todas las horas
  (H5a) estaría completa ya.
- **Cambio:** la corrección de Holm se sustituye por **Bonferroni**. Cada hipótesis se prueba con
  α = 0,025: p unilateral < 0,025 frente a p* = 54,05 %.
- **Por qué es válido:** Bonferroni controla el error de familia igual que Holm (≤ 5 %) y es algo más
  exigente. Permite evaluar cada hipótesis **por separado**, en cuanto su muestra fija esté completa o
  vence el plazo, sin esperar a la otra.
- **Sin cambios:** muestras (3 500 y 2 500), límite inferior de Wilson 95 % > p*, EV > 0, plazo y
  consecuencias.
- **Consecuencias:**
  - si H5a aprueba, las señales experimentales en demo valen para todas las horas (H5b se evalúa
    igual cuando se complete y se informa);
  - si H5a no aprueba, se espera a H5b (solo fines de semana);
  - si ninguna aprueba, SIN SEÑAL.
- **Una sola evaluación:** cada hipótesis se evalúa una vez. Mientras la muestra de una hipótesis esté
  incompleta, el comando solo informa su conteo.

**Resultado de H5a (run 40160162254 de GitHub Actions, datos 2026-10-04 → 2026-10-24, aplicado
mecánicamente; `results/estudio5/verdict.json`):**

| | Valor |
|---|---|
| Muestra fija | 3 500 alertas sin empate (2026-10-04 → 2026-10-19), más 481 empates |
| Aciertos | 1 964 = **56,11 %** [IC 95 %: 54,46 %; 57,75 %] |
| Umbral p* | 54,05 % (pago 85 %, empate reembolsado) |
| EV por unidad apostada | **+0,034** |
| p unilateral | 0,0075 (< 0,025) |
| **Veredicto** | **H5a APRUEBA** |

**Sensibilidad (informativa, no decide):**

| Entrada tras el cierre | +2 s | +5 s | +10 s | +20 s |
|---|---|---|---|---|
| Acierto | 58,1 % | 57,0 % | 56,1 % | 55,4 % |
| EV con pago 85 % | +0,066 | +0,049 | +0,034 | +0,023 |
| EV con pago 80 % | +0,040 | +0,023 | +0,009 | −0,002 |

**Desglose descriptivo (no es una prueba; el de fin de semana es la hipótesis H5b, aún incompleta):**
- **entre semana:** 813/1 529 = **53,2 %** [50,7 %; 55,7 %], por debajo del umbral;
- **sábado y domingo UTC:** 1 151/1 971 = **58,4 %** [56,2 %; 60,6 %].

La ventaja de la muestra se concentra en el fin de semana, como en la verificación adversaria de la
Enmienda 2.

**Control interno:** la sensibilidad a +10 s, calculada por otro camino de código (directamente sobre
las velas de 1 s), reproduce exactamente el resultado del bucle: 1 964 aciertos y 481 empates.

**Consecuencia pre-registrada:** señales manuales experimentales **solo en cuenta demo**, a cualquier
hora. Antes, la prueba en demo debe comprobar que el precio del intermediario sigue al de Binance, que
el empate se reembolsa y que el pago es ≥ 85 % (con 80 % el EV a +10 s es casi nulo). H5b
(2 286 de 2 500) se evalúa en cuanto se complete. Nunca dinero real sin autorización expresa.

## Estudio 6 — zonas de precio (pre-registro, 2026-10-24, ANTES de calcular ninguna variable de zona)

**Origen:** análisis del PDF «El secreto del trading profesional» (docs/05). La única idea del PDF con
respaldo académico que el proyecto no ha probado son las **zonas**:
- números redondos, máximo y mínimo del día anterior y extremos recientes;
- Osler (2000): rebote en niveles publicados del 60,8 % frente al 56,2 % en niveles arbitrarios;
- Osler (2003): toma de ganancias en números redondos y stop-loss justo después.

El modelo actual no sabe dónde están esos niveles. Nadie ha calculado estas variables sobre datos reales.

**Expectativa declarada:** «SIN SEÑAL». Si existe efecto, lo plausible es 52–55 %.

**Pregunta:** ¿saber dónde están las zonas mejora la predicción de la dirección a 15 minutos, entrando
1 minuto después de la señal?

**Hipótesis (familia de 2, Holm entre ellas):**
- **H6-BTC:** BTC/USDT, contado de Binance (`research/study3.py`: `spot_bars` sobre `data/raw/estudio3`);
  número redondo = múltiplo de **1 000 USD**.
- **H6-EUR:** EUR/USD, HistData M1 BID, la fuente de la Fase 1B (Enmienda 1); número redondo = múltiplo
  de **0,0100**. Es el mercado de los estudios de Osler.

**Diseño común (el del Estudio 3, para que la comparación sea limpia):**
- **Duración:** 15 minutos.
- **Decisión:** al cierre de las velas que empiezan en minutos múltiplos de 15 (UTC).
- **Entrada:** apertura de `t+2`, con etiquetas con retraso 2 en el ajuste y en la evaluación.
- **Contrato:** binaria, pago 85 %, empate reembolsado; p* = 54,05 %.
- **Política:** B (EV estimado ≥ 0,02 con la probabilidad calibrada).
- **Ejecución simulada:** la del Estudio 3 (`simulate` con los parámetros de `config/research.toml`).
- **Modelo:** `logit` del proyecto.
  - **Referencia:** solo `FEATURES`.
  - **Prueba:** `FEATURES` más el bloque de zonas.
  - Las dos usan las **mismas decisiones**: filas donde existen todas las variables de los dos.
- **Desarrollo:** walk-forward de la sección 8.
  - Pruebas trimestrales del 2022-01-01 al 2025-08-31.
  - Entrenamiento con los 12 meses anteriores: el 20 % final para calibrar y purga entre tramos.

**Bloque de zonas (10 variables, fijadas ahora).** Fila t usa solo velas hasta el cierre de t.

Notación:
- `c`, `h`, `l`: cierre, máximo y mínimo de cada vela de 1 minuto;
- `σ` = `vol60 · √15`, donde `vol60` es la desviación de los rendimientos logarítmicos de 1 minuto en
  60 velas, igual que en `compute_features` (sin `σ` > 0 no hay decisión);
- `paso` = 1 000 (BTC) o 0,0100 (EUR/USD);
- `R` = `round(c / paso) · paso`, el número redondo más cercano;
- «distancia a X» = `(ln c − ln X) / σ`.

| Variable | Definición |
|---|---|
| `z_rn` | Distancia a `R` |
| `z_rn_x15` | `signo(floor(c_t / paso) − floor(c_{t−15} / paso))`: +1 si en 15 min cruzó un número redondo hacia arriba, −1 hacia abajo, 0 si no |
| `z_rn_n` | Minutos desde la última vela de 1 min cuyo intervalo [`l`, `h`] contiene un múltiplo de `paso` (0 si es la vela t; tope 240) |
| `z_pdh`, `z_pdl` | Distancia al máximo `h` y al mínimo `l` del día UTC anterior completo (NaN si ese día tiene < 720 velas) |
| `z_hi240`, `z_lo240` | Distancia a `H` = máx. de `h` y a `L` = mín. de `l` en las velas t−239 … t−15 |
| `z_t_hi`, `z_t_lo` | Número de velas en t−239 … t−15 con `(ln H − ln h) ≤ 0,25·σ` (resp. `(ln l − ln L) ≤ 0,25·σ`): «toques» del extremo |
| `z_rej15` | `(c − mín l) / (máx h − mín l)` en las velas t−14 … t (0,5 si el rango es 0) |

**Criterios para «pasa la fase de desarrollo»** (los 5 del Estudio 3, para cada hipótesis):
1. ≥ 300 operaciones.
2. Límite inferior de Wilson 95 % > 54,05 %.
3. p de Holm < 0,05 entre las 2 hipótesis.
4. EV > 0 en ≥ 60 % de los trimestres y ningún trimestre aporta > 50 % del beneficio.
5. **Mejora frente a la referencia en las mismas decisiones:**
   - IC 95 % por bootstrap de bloques diarios de la diferencia de log-loss (referencia − prueba) > 0,
     medida en todas las decisiones sin empate;
   - EV de la prueba ≥ EV de la referencia.

**Control obligatorio (ítem 39):** si los dos modelos predicen igual, la ejecución se aborta y no vale.

**Si alguna pasa:**
1. **Filtro no confirmatorio** en 2025-09 → 2026-08, periodo ya usado y así declarado: se sigue solo si el
   acierto puntual es > 54,05 % y el log-loss mejora frente a la referencia.
2. **Confirmación limpia** con datos desde el **2026-09-01**:
   - mismo walk-forward trimestral, continuado (12 meses de entrenamiento anteriores a cada trimestre);
   - evaluada en GitHub Actions, sin el portátil;
   - muestra fija = las primeras **5 136 operaciones sin empate** por hipótesis (potencia 80 % si el
     acierto real es ≥ 56 %);
   - aprueba si cumple, con Holm entre las hipótesis que lleguen: Wilson 95 % > 54,05 %, límite
     inferior del IC 95 % del EV > 0 y p de Holm < 0,05;
   - **inutilidad**, solo para parar y nunca para aprobar antes: con 1 700 y con 3 400 operaciones, si el
     límite **superior** de Wilson 95 % es < 54,05 %, esa hipótesis termina en «SIN SEÑAL»;
   - plazo **2027-09-30**: si no se completa la muestra, «no concluyente».

**Si ninguna pasa:** se cierra con «SIN SEÑAL».

**Consecuencias:**
- **Si confirma:** señales manuales experimentales **solo en cuenta demo**, con el formato «instrumento |
  ABRIR a las HH:MM (hora de Colombia, UTC−5) | 15 minutos | ARRIBA/ABAJO».
- **Si no confirma:** SIN SEÑAL.
- Nunca dinero real sin autorización expresa.

**Fuera de la familia (solo informativo):** GBM, duraciones de 5 y 60 min, otros pasos de número redondo
(500 USD; 0,0050), y la frecuencia de «rebote» al estilo de Osler (no cruzar el nivel en 15 min) en
números redondos frente a niveles desplazados medio paso.

*Nota de implementación (2026-10-24, antes de ejecutar).* Código: `research/study6.py` y
`tbot research study6`, con el mismo comparador que el Estudio 3 (`study3.compare`, extraído sin cambiar
resultados: el Estudio 4 se reprodujo idéntico). Detalles que el texto dejaba abiertos:
- **Mínimo de velas con precio:** 200 de las 225 para los extremos de 240 min (como `vol240`) y 12 de 15
  para `z_rej15` (como `vol15`).
- **Velas de HistData:** las rellenadas por falta de ticks (huecos < 30 min) cuentan como velas con
  precio para el umbral de 720 del día anterior.
- **Lunes de EUR/USD:** el «día anterior» es el domingo UTC, que casi nunca tiene 720 velas. Por eso
  esas decisiones quedan fuera **en los dos modelos**, como dicta la definición.
- **Tolerancia de redondeo:** 1e-9 al dividir por el paso, para que un toque exacto de 1,1000 cuente.

**Resultado de la fase de desarrollo (commit 37fdd3f, aplicado mecánicamente; `results/estudio6/dev.json`):**

| Hipótesis | Modelo | Operaciones | Acierto [lím. inf. 95 %] | EV [IC 95 %] | Trimestres EV > 0 | Mejora de log-loss [IC 95 %] |
|---|---|---|---|---|---|---|
| H6-BTC | solo precio (referencia) | 30 320 | 55,61 % [55,05 %] | +0,029 [+0,018; +0,040] | 93 % | — |
| H6-BTC | precio + zonas | 33 016 | 55,19 % [54,65 %] | +0,021 [+0,010; +0,031] | 80 % | +0,00002 [−0,00015; +0,00019] |
| H6-EUR | solo precio (referencia) | 1 411 | 53,76 % [51,14 %] | −0,005 [−0,054; +0,041] | 60 % | — |
| H6-EUR | precio + zonas | 1 380 | 51,64 % [48,99 %] | −0,044 [−0,091; +0,003] | 0 % | −0,00008 [−0,00027; +0,00010] |

**Veredicto: ninguna hipótesis pasa.**
- **BTC:** cumple los criterios 1–4 (como ya los cumplía el modelo de solo precio), pero falla el 5: las
  zonas no mejoran la predicción (el IC del log-loss incluye 0) y **bajan** la ganancia esperada.
- **EUR/USD:** falla 2–5.
- **Estudio 6: SIN SEÑAL.**

En EUR/USD, el acierto sobre todas las decisiones coincidió en los dos modelos (51,00 %). Se comprobó que
no es el fallo del ítem 39: los modelos eligen lados distintos en el 12 % de las decisiones (correlación
de probabilidades 0,85).

## Estudio 7 — herramientas de «Kronos» y del video del usuario (pre-registro, 2026-10-25, ANTES de calcularlas)

**Origen:** el usuario vio un video sobre «Kronos AI». El video describe esta estrategia:
1. cada vela se convierte en 6 dimensiones y se traduce a tokens binarios;
2. se buscan en el historial los momentos más parecidos al actual y se promedia lo que pasó después;
3. un filtro de Kalman y otros activos afinan la proyección;
4. se dibujan las próximas 12 velas y, si el retorno supera un umbral, se marca señal larga o corta.

**Qué es Kronos** (revisión del 2026-10-25, detalles en docs/05, sección 7):
- modelo de Tsinghua (arXiv 2508.02739, AAAI 2026), código MIT: `shiyu-coder/Kronos`, commit `67b630e`;
- tokeniza OHLCV + importe (6 dimensiones) con cuantización binaria esférica (2 × 10 bits);
- preentrenado con más de 12 000 millones de velas, **hasta junio de 2024**, incluidas velas de 1 min de
  perpetuos de Binance;
- en cripto, su correlación de rango con el rendimiento siguiente es ≈ 0,03–0,04. Eso equivale, como
  mucho, a ~51 % de acierto direccional. No publica acierto direccional ni pruebas en cripto.

**Pregunta:** cada una de cuatro herramientas, ¿mejora la probabilidad del modelo GBM del proyecto para
la dirección de BTC/USDT a 1 minuto? Es la configuración que aprobó H5a.

**Expectativa declarada:** «SIN SEÑAL» en las cuatro. El GBM ya usa los rendimientos recientes, de los
que dependen el análogo y el Kalman. La correlación publicada de Kronos es baja. El adelanto de ETH sobre
BTC en 1 minuto no está documentado.

**Herramientas (familia de 4; corrección de Bonferroni):**

| ID | Herramienta | Definición fija (todo causal, con velas que cierran en t) |
|---|---|---|
| T7-KRONOS | Kronos-small, sin reentrenar | `NeoQuasar/Kronos-small` + `Kronos-Tokenizer-base`, contexto de 512 velas de 1 min (OHLCV, importe = volumen × media de OHLC, como el código oficial), 1 vela predicha, T = 0,6, top-p = 0,9, 5 muestras promediadas, semilla fija por bloque. Variable: `ln(cierre predicho de t+1 / cierre reconstruido de t) / vol60`, ambos del mismo decodificado. Sin 512 velas completas, no hay decisión |
| T7-ANALOG | Momentos más parecidos | Patrón = 12 últimos rendimientos de 1 min / vol60. Biblioteca = los minutos del tramo de entrenamiento del trimestre (mismos 12 meses y purga que el GBM). Se toman los 100 vecinos más cercanos (distancia euclídea). Variable: media del signo del minuto siguiente de esos vecinos (empates = 0) |
| T7-KALMAN | Kalman de tendencia | Filtro de Kalman estacionario de nivel y pendiente (equivale a Holt) sobre el logaritmo del cierre, ganancias fijas α = 0,3, β = 0,05. Variable: pendiente / vol60 |
| T7-ETH | Otro activo | Rendimientos de ETH/USDT de 1 y 5 min (contado de Binance) / vol60 de ETH: dos variables |

**Diseño:**
- **Etiqueta:** dirección de la vela t+1 (entrada en su apertura, salida en su cierre). Es `make_labels(h = 1,
  d = 1)` de la Fase 1B, binaria al 85 %, empate reembolsado.
- **Referencia:** GBM del proyecto con `FEATURES`, en walk-forward trimestral: pruebas del 2024-10-01 al
  2025-08-31, entrenamiento con los 12 meses previos, 20 % final para calibración isotónica y purga.
  Sale una probabilidad calibrada `p` para cada minuto.
- **Conjunto de evaluación E:** 20 000 minutos sorteados al azar (semilla 20261025), uniformes en
  2024-10-01 → 2025-08-31, entre los que tienen `p`, etiqueta y todas las variables de las cuatro
  herramientas. Kronos se calcula solo en E, por su costo (~0,7 s por decisión en este PC).
  - El periodo empieza **3 meses después** del fin del preentrenamiento de Kronos, que no vio estos datos.
  - El GBM y las otras herramientas solo usan datos anteriores a cada trimestre.
- **Combinador:** regresión logística (C = 1, variables estandarizadas con el tramo de ajuste).
  - **Base:** `[logit(p)]`, que es solo recalibración.
  - **Prueba de cada herramienta:** `[logit(p), variables de la herramienta]`.
  - **Ajuste expansivo:** con las decisiones de E sin empate de los trimestres anteriores. Para probar
    2025-T1 se usa 2024-T4; para 2025-T2, 2024-T4 + 2025-T1; para 2025-07/08, todo lo anterior.
  - **Prueba:** las decisiones de E del 2025-01-01 al 2025-08-31.

**Criterios (cada herramienta pasa si cumple los dos):**
1. Límite inferior del IC **98,75 %** (Bonferroni 0,05/4) por bootstrap de bloques diarios de la mejora de
   log-loss (base − prueba), en las decisiones de prueba sin empate, > 0.
2. EV de la política B (EV estimado ≥ 0,02 con la probabilidad combinada y la tasa de empates causal de
   la Fase 1B) **≥** el de la base, en las mismas decisiones.

**Solo informativo:** acierto de cada herramienta sola (signo de su variable), acierto y EV de la base y
de cada combinación, desglose entre semana y fin de semana UTC.

**Consecuencias:**
- **Si alguna pasa:** es candidata a incorporarse al modelo. Su confirmación se pre-registra **antes** de
  mirar datos posteriores al 2026-10-26, con la entrada a +10 s del Estudio 5. No cambia nada de lo que
  ya está aprobado hasta entonces.
- **Si ninguna pasa:** las cuatro quedan en «SIN SEÑAL» y no se incorporan.
- Nada de esto autoriza dinero real.

**Resultado (commit de8de82; Kronos-small revisión `901c26c`, 20 000 predicciones calculadas en el PC del
usuario; aplicado mecánicamente; `results/estudio7/dev.json`).** Prueba: 14 444 decisiones de E en
2025-01 → 2025-08, de ellas 13 943 sin empate.

| Herramienta | Mejora de log-loss [IC 98,75 %] | Política B: operaciones / acierto / EV | EV base | Acierto de la herramienta sola |
|---|---|---|---|---|
| Solo GBM (base) | — | 1 322 / 55,76 % / +0,028 | — | — |
| T7-KRONOS | −0,000016 [−0,00015; +0,00012] | 1 375 / 56,15 % / +0,035 | +0,028 | **50,03 %** |
| T7-ANALOG | −0,000070 [−0,00026; +0,00012] | 1 338 / 55,47 % / +0,023 | +0,028 | 50,36 % |
| T7-KALMAN | −0,000002 [−0,00007; +0,00006] | 1 193 / 56,18 % / +0,035 | +0,028 | 50,43 % |
| T7-ETH | **+0,000259** [−0,00048; +0,00101] | 2 003 / 56,97 % / +0,050 | +0,028 | **51,98 %** |

**Veredicto:** ninguna pasa el criterio 1; en las cuatro, el IC de la mejora incluye 0. **Estudio 7: SIN
SEÑAL.** No se incorpora ninguna.
- **Kronos** sola acierta 50,03 %, igual que una moneda, en la dirección del minuto siguiente de BTC. No
  añade información al GBM.
- **Análogos y Kalman** no aportan: el GBM ya usa los rendimientos recientes.
- **ETH** es la única con mejora puntual positiva: más operaciones (2 003) con más acierto (57,0 %) y el
  doble de EV. Pero su intervalo es ancho e incluye 0, y esa lectura es posterior a ver los datos.
  **Queda como hipótesis nueva**, que solo puede confirmarse con datos que nadie haya visto (posteriores al
  2026-10-26) y un pre-registro propio.

## Estudio 8 — «Golden BIAS 200» reconstruido en oro (pre-registro, 2026-10-25, ANTES de calcularlo)

**Origen:** el usuario encontró en TradingView el indicador «Golden BIAS 200» v6.4. Es de solo
invitación: se paga 50 USD por Telegram y el código es cerrado. Su descripción publica estas reglas
para XAU/USD:
- tendencia: SMA 15 y SMA 200, con el precio por encima de ambas para comprar (debajo para vender);
- distancia mínima entre las medias («minDistance»);
- la vela debe mantener la dirección durante el minuto;
- entrada solo si el precio toca un retroceso («offset») desde la SMA 15;
- sesiones en hora de México: 08:00–12:00, 17:30–23:00 y 01:00–07:00;
- panel multitemporal de M5 a H4 («si todas las flechas coinciden, alta probabilidad»);
- TP y SL dibujados al entrar.

No publica parámetros ni resultados verificables. Se reconstruye con parámetros fijados **ahora**, sin
mirar datos de oro con estas reglas. El proyecto ya sabe que el oro no tuvo señal con sus modelos
(Fase 1B).

**Expectativa declarada:** «SIN SEÑAL». Las reglas de medias móviles no superaron al azar tras costos en
oro (H4 de la Fase 1B). Un TP y un SL simétricos dan un acierto cercano al 50 % menos los costos.

**Datos:** XAU/USD HistData M1 BID, la fuente de la Fase 1B (Enmienda 1). Se usan velas medias = BID +
spread supuesto / 2, con `to_canonical(fill_gaps=True)`. Costo por operación de contado: spread supuesto
0,25 + comisión 0,07 = **0,32 USD/oz** ida y vuelta, el escenario optimista del proyecto.

**Reglas reconstruidas (velas de 1 min; todo con información hasta el cierre de t):**
- SMA15 y SMA200 de los cierres; ATR14 = media de 14 rangos verdaderos.
- **Compra** si se cumplen todas (venta: simétrico):
  1. `c_t > SMA15_t`, `c_t > SMA200_t` y `SMA15_t > SMA200_t`;
  2. `SMA15_t − SMA200_t ≥ 1,0 · ATR14_t` (distancia mínima);
  3. vela t alcista: `c_t > o_t` (dirección mantenida durante el minuto);
  4. cierre de t dentro de una sesión en hora de Ciudad de México (`America/Mexico_City`):
     [08:00, 12:00), [17:30, 23:00) o [01:00, 07:00).
- **Multitemporal (MTF)**, solo en las variantes que lo dicen: en 5, 15, 60 y 240 min, la última vela
  **cerrada** de ese marco (cortes en UTC) cierra por encima de la SMA20 de sus cierres, para comprar
  (por debajo, para vender). Las cuatro deben coincidir.
- **Una operación a la vez:** no hay señal nueva mientras haya una orden pendiente o una posición abierta.

**Ejecución de contado / CFD (hipótesis H8a y H8b):**
- **Orden límite** en `L = SMA15_t + 0,25·ATR14_t` para compras (`SMA15_t − 0,25·ATR14_t` para ventas),
  válida en las velas t+1 … t+10.
  - Se llena en la primera vela con `l ≤ L` (compra), al precio `min(L, apertura)`.
  - Si `L ≥ c_t`, se entra a mercado en la apertura de t+1.
  - Si no se llena, no hay operación.
- **Salidas:** SL a 1,5·ATR14_t y TP a 1,5·ATR14_t desde la entrada, o cierre a mercado 60 velas después
  de entrar.
  - Si SL y TP caen en la misma vela, cuenta el SL (conservador).
  - Los cierres parciales no se modelan.
- **Resultado:** `(salida − entrada) · lado − 0,32` USD/oz. También se informa en múltiplos del riesgo (R).

**Versión binaria (H8c y H8d):**
- Misma señal; dirección = lado.
- **Entrada:** apertura de t+2, es decir, 1 min después, como operación manual.
- **Vencimiento:** 5 min (`make_labels(h = 5, d = 2)`).
- Pago 85 %, empate reembolsado.
- Sin solapamiento: tras una señal, no hay otra hasta que vence.

**Hipótesis (familia de 4, Bonferroni α = 0,0125 cada una):**
- **H8a:** contado, sin MTF.
- **H8b:** contado, con MTF.
- **H8c:** binaria a 5 min, sin MTF.
- **H8d:** binaria a 5 min, con MTF.

**Fase A, prueba directa sin ajuste** (las reglas no se entrenan), 2022-01-01 → 2025-08-31. Pasa si:
- **contado:**
  - ≥ 300 operaciones;
  - límite inferior del IC 98,75 % (bootstrap por días) del resultado neto medio > 0;
  - resultado > 0 en ≥ 60 % de los trimestres;
- **binaria:**
  - ≥ 300 operaciones;
  - p unilateral < 0,0125 frente a 54,05 %;
  - Wilson 95 % > 54,05 %;
  - EV > 0.

**Fase B**, solo para las que pasen A: 2025-09-01 → 2026-08-31, con los mismos criterios. Ese periodo nunca
se usó con esta estrategia; sí con los modelos de oro de la Fase 1B, y así se declara. Si pasa, la
confirmación final se hará con datos posteriores al 2026-09-01.

**Solo informativo:** «winrate» (porcentaje de TP antes que SL), que es lo que muestra la tabla del
indicador; resultado por sesión y por año; operaciones sin llenar.

**Consecuencias:**
- Si alguna pasa las dos fases, se propone su confirmación con datos nuevos.
- Si ninguna pasa, SIN SEÑAL y **no se recomienda pagar el indicador**.
- Nada de esto autoriza dinero real.

*Nota de implementación (2026-10-25, antes de ejecutar).* Código: `research/study8.py` y
`tbot research study8`. Detalles que el texto dejaba abiertos:
- **Vela de entrada:** solo se comprueba el SL. Dentro de esa vela no se sabe si el máximo llegó antes
  o después de la entrada, así que el TP se comprueba desde la vela siguiente (conservador).
- **Minutos sin datos:** se saltan. La salida por tiempo usa el último cierre conocido.
- **Orden no llenada:** bloquea nuevas señales durante sus 10 velas de vigencia.

**Resultado de la fase A (2022-01 → 2025-08, commit 952d2d9, aplicado mecánicamente;
`results/estudio8/resultado.json`):**

| Hipótesis | Operaciones | «Winrate» (TP antes que SL) / acierto | Resultado | Trimestres positivos |
|---|---|---|---|---|
| H8a contado | 30 169 (12 126 órdenes sin llenar) | 48,8 % | **−0,34 USD/oz** por operación [IC 98,75 %: −0,36; −0,32]; bruto −0,02 R | 0 % |
| H8b contado + MTF | 11 516 | 48,6 % | **−0,34 USD/oz** [−0,37; −0,31] | 0 % |
| H8c binaria 5 min | 54 743 | **49,1 %** [lím. inf. 48,7 %] | EV −0,091 | — |
| H8d binaria 5 min + MTF | 21 347 | **49,3 %** [48,6 %] | EV −0,087 | — |

**Veredicto: ninguna pasa la fase A** (no hay fase B). Las cuatro pierden en todas las sesiones y en
todos los años, de 2022 a 2025.
- **Contado:** antes de costos, las reglas no ganan nada (−0,02 R). El costo optimista de 0,32 USD/oz
  se lleva el resto.
- **Binaria:** la dirección después de la señal acierta **menos** del 50 %; el oro tiende a revertir un
  poco tras una vela a favor de la tendencia.
- La confirmación multitemporal no cambia nada.
- **Estudio 8: SIN SEÑAL. No se recomienda pagar el indicador.**

El desglose por sesión y por año se añadió después de la primera ejecución, porque el pre-registro lo
pedía y faltaba en el código. Es informativo y no cambia ningún criterio.

## Estudio 9 — regla «RSI diario y semanal + estructura 4H + entrada en 15M» de redes sociales (pre-registro, 2026-10-25, ANTES de calcularla)

**Origen:** consejo publicado en un comentario de Facebook que mostró el usuario: «si el RSI toca la línea de
sobrecompra en el gráfico 1D y W, solo dedícate a meter operaciones a la venta y viceversa, confirma la
estructura de 4H y opera en 15M».

**Expectativa declarada:** «SIN SEÑAL». La literatura sobre momentum (Moskowitz, Ooi y Pedersen, 2012)
encuentra que las subidas fuertes tienden a **continuar** durante meses, lo contrario de lo que asume la
regla. Además, los periodos con RSI extremo en diario y semanal son pocos, así que habrá pocos episodios
independientes.

**Instrumentos (familia de 4, Bonferroni α = 0,0125):**
- **H9-BTC** y **H9-ETH:** contado de Binance (`data/raw/estudio3`);
- **H9-XAU** y **H9-EUR:** HistData M1 BID (Enmienda 1).

**Reglas (todo con velas ya cerradas en el momento de decidir):**
- **RSI14 de Wilder** sobre los cierres de la última vela diaria (día UTC) y semanal (lunes a domingo,
  UTC) **completas**.
  - Sobrecompra: los dos ≥ 70 → solo ventas.
  - Sobreventa: los dos ≤ 30 → solo compras.
- **Estructura 4H** (velas de 4 h con cortes en UTC), con la última vela de 4 h cerrada (X) frente a
  la anterior (X−1):
  - **venta:** máximo de X < máximo de X−1 y cierre de X < cierre de X−1 (máximo más bajo y cierre más
    bajo);
  - **compra:** mínimo de X > mínimo de X−1 y cierre de X > cierre de X−1.
- **Ejecución en 15M:**
  - decisión al cierre de las velas de minutos múltiplos de 15 (UTC);
  - binaria a 15 min, entrada en la apertura de t+2 (1 min después, manual): `make_labels(h = 15, d = 2)`;
  - pago 85 %, empate reembolsado;
  - sin solapamiento.

**Periodo:** 2022-01-01 → 2025-08-31. Es una prueba directa: la regla no se entrena. Se necesitan 250 días
de historia previa para el RSI semanal, que se toman de 2021.

**Criterios (cada instrumento):**
1. ≥ 300 operaciones;
2. p binomial unilateral < 0,0125 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. límite inferior del IC 98,75 % del EV por bootstrap de bloques **semanales** > 0 (las operaciones de
   un mismo episodio no son independientes).

**Solo informativo:**
- número de semanas con operaciones (episodios);
- la misma regla sin la confirmación 4H;
- la regla al revés (seguir la tendencia).

**Consecuencias:**
- Si alguna pasa, se pre-registra su confirmación con datos posteriores al 2026-09-01.
- Si ninguna pasa, SIN SEÑAL.

**Resultado (commit a166394, aplicado mecánicamente; `results/estudio9/resultado.json`):**

| Instrumento | Operaciones (episodios: semanas) | Acierto [lím. inf. 95 %] | EV [IC 98,75 % semanal] |
|---|---|---|---|
| BTC/USDT | 1 224 (17) | **47,7 %** [44,9 %] | −0,117 [−0,161; −0,056] |
| ETH/USDT | 592 (9) | **45,9 %** [42,0 %] | −0,150 [−0,234; −0,072] |
| XAU/USD | 594 (15) | **48,0 %** [44,0 %] | −0,112 [−0,206; −0,022] |
| EUR/USD | 524 (11) | **49,3 %** [45,0 %] | −0,086 [−0,164; −0,021] |

**Veredicto:** ninguna pasa. Las cuatro aciertan **menos del 50 %** y pierden con un IC entero por debajo
de 0. **Estudio 9: SIN SEÑAL.**

Informativo:
- **Sin la confirmación 4H:** 47,1–49,6 %; la confirmación no ayuda.
- **Al revés (seguir la tendencia):** 50,7–54,1 %, con EV entre −0,061 y 0,000. Es coherente con el
  momentum, pero no gana y se basa en solo 9–17 semanas. Si se quisiera probar, sería una hipótesis
  nueva con datos nuevos.

## Estudio 10 — oro con correlación negativa y zonas del índice del dólar (pre-registro, 2026-10-25, ANTES de calcularlo)

**Origen:** estrategia de redes que mostró el usuario.
1. Abrir el oro y el índice del dólar (DXY), y ponerle al oro el «coeficiente de correlación» con el DXY.
2. Si la correlación está por debajo de 0 y el oro entra en una zona de demanda mientras el DXY
   **reacciona** en una zona de oferta, buscar compras de oro (al revés, ventas). Si el DXY no ha llegado
   a su zona, esperar.
3. El video afirma: «la mayoría de tus operaciones perdedoras las podrías haber evitado si hubieras
   mirado antes la correlación».

**Base real:** el oro y el dólar suelen moverse en sentido contrario, pero esa relación cambia con el tiempo
y entre regímenes (p. ej., estudio con datos de 5 min de 2017–2019, PMC8566682). Ver que se mueven al revés
en el mismo momento no implica poder anticipar el siguiente movimiento.

**Expectativa declarada:** «SIN SEÑAL». Puede que el filtro mejore algo el acierto de la regla de zonas sola,
pero difícilmente por encima de 54,05 %.

**Datos (velas de 1 min; prueba directa sin ajuste, 2022-01-01 → 2025-08-31, calentamiento desde 2021):**
- **Oro:** XAU/USD de HistData, velas medias (BID + spread supuesto / 2).
- **DXY aproximado:** el índice oficial no está en las fuentes gratuitas de velas de 1 min del proyecto.
  - Se construye con los cierres de 1 min de EUR/USD, USD/JPY y GBP/USD (HistData):
    `ln DXY* = (−0,576·ln EURUSD + 0,136·ln USDJPY − 0,119·ln GBPUSD) / 0,831`.
  - Son los pesos oficiales del ICE de esas tres monedas (83 % del índice), renormalizados. Faltan CAD,
    SEK y CHF (17 %).
  - Solo se usan los minutos con las tres monedas.
- **Velas de 15 min (cortes UTC):** OHLC del oro; para el DXY*, OHLC de sus cierres de 1 min.

**Reglas (velas de 15 min; decisión al cierre de la vela t):**
- **Correlación:** Pearson entre los **cierres** del oro y del DXY* en las 20 últimas velas, como
  `ta.correlation` de TradingView. Condición: < 0.
- **ATR14** de 15 min, para cada activo.
- **Zona de demanda del oro:** L = mínimo de los mínimos de las 96 velas anteriores (24 h, sin incluir t).
  El oro está en la zona si `mín_t ≤ L + 0,5·ATR` y `cierre_t ≥ L`. Zona de oferta: simétrica, con H =
  máximo de los máximos.
- **El DXY* respeta su zona de oferta:** con H' = máximo de sus 96 velas anteriores,
  `máx'_t ≥ H' − 0,5·ATR'`, `cierre'_t < H'` y vela bajista. Demanda: simétrica.
- **Compra de oro:** correlación < 0, oro en zona de demanda y DXY* respetando su oferta. Venta: simétrica.

**Ejecución:**
- binaria; entrada en la apertura del minuto que empieza **1 min después** del cierre de la vela de
  15 min (manual);
- vencimiento de 15 min (**H10a**) o de 60 min (**H10b**);
- pago 85 %, empate reembolsado, sin solapamiento.

**Criterios (cada hipótesis; Bonferroni α = 0,025):**
1. ≥ 300 operaciones; si hay menos, «insuficiente» y no pasa;
2. p binomial unilateral < 0,025 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. límite inferior del IC 97,5 % del EV por bootstrap de bloques semanales > 0.

**Comprobación de lo que afirma el video (pre-registrada, informativa):** con el mismo vencimiento, el
acierto de la regla completa frente a la **regla de zonas del oro sola** (comprar en demanda, vender en
oferta, sin correlación ni DXY). Se informa la diferencia con IC 95 % por bootstrap semanal y la parte de
operaciones perdedoras de la regla sola que el filtro evita.

**Consecuencias:**
- Si alguna pasa, se pre-registra su confirmación con datos posteriores, cuando haya divisas de HistData
  después de 2025-08.
- Si no, SIN SEÑAL.

*Nota de implementación (2026-10-25, antes de ver ningún acierto).* «Velas» son las de 15 min con datos en
el oro y en el DXY*, como en TradingView. La primera ejecución usó la rejilla del calendario, con fines de
semana y la pausa diaria del oro, y no produjo ninguna operación (registro de errores, ítem 40).

**Resultado (commit 24ac3c0, aplicado mecánicamente; `results/estudio10/resultado.json`):**
- En 2022–2025, la correlación de 20 velas entre el oro y el DXY* fue negativa el **79 %** del tiempo
  (media −0,40). La relación existe.

| Hipótesis | Operaciones (semanas) | Acierto [lím. inf. 95 %] | EV [IC 97,5 % semanal] |
|---|---|---|---|
| H10a, 15 min | 1 106 (180) | **48,2 %** [45,3 %] | −0,108 [−0,164; −0,053] |
| H10b, 60 min | 862 (179) | **49,9 %** [46,6 %] | −0,076 [−0,150; −0,004] |

**Veredicto:** ninguna pasa. **Estudio 10: SIN SEÑAL.**

**Lo que afirma el video («la mayoría de tus operaciones perdedoras las podrías haber evitado»):**
- **Regla de zonas del oro sola:** 7 167 operaciones a 15 min, 50,0 % de acierto (60 min: 50,2 %).
- **El filtro de correlación + DXY:**
  - evita el **89 %** de las perdedoras de la regla sola, pero también elimina el **90 %** de las
    ganadoras;
  - las operaciones que deja pasar aciertan 47,6 %; las que quita, 50,3 %;
  - diferencia: −2,7 puntos [IC 95 %: −6,1; +0,9].
- **Conclusión:** el filtro no selecciona mejores operaciones. Solo opera menos. «Evitar perdedoras» no
  sirve si se evitan las ganadoras en la misma proporción.

## Estudio 11 — «regla de la primera vela» con FVG y envolvente, 3:1 (pre-registro, 2026-10-25, ANTES de calcularla)

**Origen:** video de redes que mostró el usuario. Las capturas de comentarios que lo acompañan usan el mismo
lenguaje del «Smart Money Concept»: barridos de liquidez, CHoCH, FVG y retesteo. La regla del video:
1. a las 9:30 de Nueva York, marcar el máximo y el mínimo de la primera vela de 5 min (9:30–9:35);
2. en 1 min, esperar a que el precio **rompa** uno de esos niveles dejando un **FVG** (hueco entre las
   mechas de tres velas);
3. esperar a que el precio **vuelva al FVG** y forme una **vela envolvente**;
4. entrar con riesgo/beneficio fijo **3:1**;
5. el autor dice operar una sola vez al día.

**Evidencia previa:**
- Zarattini y Aziz (SSRN 4416622): un ORB de 5 min en QQQ (2016–2023) da alfa alto antes de spread y
  deslizamiento.
- Una réplica práctica en CFD de índices (2015–2026) reproduce el bruto, pero queda en **cero neto** tras
  costos (blog de MQL5).
- Para los FVG solo hay estudios de vendedores, sin control con placebo publicado.

**Expectativa declarada:** «SIN SEÑAL» tras costos.

**Instrumentos (familia de 3, Bonferroni α = 0,0167):**
- **H11-NQ:** Nasdaq 100 (HistData NSXUSD; spread supuesto 1,0 punto);
- **H11-SPX:** S&P 500 (SPXUSD; 0,5 punto);
- **H11-XAU:** oro (XAUUSD; 0,25 + comisión 0,07 USD/oz), el mercado de la mayoría de las capturas.

Se usan velas medias de 1 min (BID + spread / 2) y la hora de Nueva York (`America/New_York`, con su
horario de verano).

**Reglas exactas:**
- **Rango:** máximo (ORH) y mínimo (ORL) de las velas de 1 min de 9:30 a 9:34. Si falta alguna, no se
  opera ese día.
- **Ruptura con FVG alcista** en la vela k (k ≥ 9:37 y antes de las 11:00):
  - `máx[k−2] < mín[k]`, que es el hueco;
  - `cierre[k−1] > ORH`: la vela del medio rompe el nivel.
  - Zona FVG = [`máx[k−2]`, `mín[k]`]. Bajista: simétrico, con `mín[k−2] > máx[k]` y `cierre[k−1] < ORL`.
- **Retesteo y envolvente:** en una vela j > k (antes de las 11:00):
  - **alcista:**
    - `mín[j] ≤ mín[k]` (toca el FVG);
    - la vela j−1 es bajista y la j es alcista;
    - `apertura[j] ≤ cierre[j−1]` y `cierre[j] ≥ apertura[j−1]` (envuelve el cuerpo).
  - **Cancelación:** el FVG se cancela si, antes, alguna vela cierra por debajo de `máx[k−2]`.
  - Bajista: simétrico.
- **Entrada:** cierre de j.
  - **SL** = mínimo entre `mín[j]` y `máx[k−2]` (en ventas, el máximo de los simétricos).
  - **TP** = entrada + 3 × (entrada − SL).
- **Salida:**
  - TP o SL, desde la vela j+1; si los dos caen en la misma vela, cuenta el SL;
  - si no se toca ninguno, cierre a las 16:00 de Nueva York.
- **Una operación por día:** la del primer FVG que llegue a entrada, en cualquier dirección. Mientras haya
  un FVG pendiente se siguen buscando otros; vale el primero que cumpla.
- **Resultado:**
  - en R (múltiplos del riesgo inicial), neto del costo: `(salida − entrada)·lado − costo`, dividido por
    el riesgo;
  - si el riesgo es menor que el costo, el día no se opera (operación irreal).

**Periodo:**
- **Fase A:** 2022-01-01 → 2025-08-31. Es una prueba directa; la regla no se entrena.
- **Fase B:** 2025-09-01 → 2026-08-31, solo para las que pasen A.

**Criterios (cada instrumento):**
1. ≥ 200 operaciones;
2. límite inferior del IC 98,33 % (bootstrap por semanas) del R neto medio > 0;
3. R neto > 0 en ≥ 60 % de los trimestres.

**Solo informativo:**
- «winrate» (porcentaje de TP);
- días sin operación;
- el ORB simple de Zarattini y Aziz: dirección de la primera vela de 5 min, entrada a las 9:35, salida a
  las 16:00, con el mismo costo.

**Consecuencias:**
- Si alguna pasa las dos fases, se pre-registra su confirmación con datos posteriores a 2026-09.
- Si no, SIN SEÑAL.

**Resultado de la fase A (2022-01 → 2025-08, commit a3d039f, aplicado mecánicamente;
`results/estudio11/resultado.json`):**

| Instrumento | Operaciones | TP / SL | R neto medio [IC 98,33 % semanal] | Trimestres positivos |
|---|---|---|---|---|
| Nasdaq 100 | 588 | 22,8 % / 76,7 % | **−0,18 R** [−0,35; −0,03] | 27 % |
| S&P 500 | 524 | 28,1 % / 71,2 % | **−0,09 R** [−0,26; +0,11] | 47 % |
| Oro | 616 | 22,7 % / 76,6 % | **−0,34 R** [−0,50; −0,18] | 0 % |

**Veredicto:** ninguna pasa la fase A. **Estudio 11: SIN SEÑAL.**
- Con 3:1 hace falta ganar más del 25 % de las veces solo para cubrir los costos. El TP se alcanzó en
  el 23–28 % de los casos.
- En el 30–38 % de los días no hubo entrada.
- El ORB simple de Zarattini y Aziz, informativo, quedó en −0,1 a −0,7 puntos básicos netos por día,
  con 49–51 % de días positivos. Es coherente con la réplica que lo deja en cero tras costos.
- HistData no tiene NSXUSD a partir de 2026-05. No hizo falta la fase B.

## Estudio 12 — ¿el movimiento reciente de ETH ayuda a predecir el minuto siguiente de BTC? (pre-registro, 2026-10-25, ANTES de ver datos posteriores al 2026-10-25)

**Origen:** en el Estudio 7, la herramienta T7-ETH fue la única con una mejora puntual positiva frente al GBM:
- log-loss +0,00026, con un IC 98,75 % de [−0,00048; +0,00101];
- política B con 57,0 % de acierto frente a 55,8 %.

Como esa lectura se hizo **después** de ver los datos, solo puede confirmarse con datos que nadie ha visto.

**Por qué podría existir (mecanismo):**
- **Adelanto entre activos muy relacionados:** cuando llega información común, uno de los dos mercados
  reacciona segundos o minutos antes. Pasa por diferencias de liquidez, de participantes o de latencia de
  los algoritmos de arbitraje.
- **Por qué podría no existir o desaparecer:** ese arbitraje es fácil para los operadores rápidos. Si el
  adelanto fuera grande, ya lo habrían eliminado.

**Hipótesis única H12:** añadir `eth_r1` y `eth_r5` al GBM de BTC a 1 minuto mejora la predicción de la
dirección de la vela siguiente. Las dos variables son rendimientos logarítmicos de ETH/USDT a 1 y 5 min
divididos por su vol60 (la de 5 min por √5), con la definición del Estudio 7.

**Diseño:**
- **Modelos:** GBM del proyecto (`make_prob_model("gbm")`, mismos parámetros).
  - **Referencia:** `FEATURES`.
  - **Prueba:** `FEATURES` + `eth_r1` + `eth_r5`.
  - Mismas filas para los dos.
- **Entrenamiento (una vez):** contado de Binance de BTC y ETH de 1 min, del 2026-10-26 − 12 meses al
  2026-10-25 23:59 UTC. El último 20 % se usa para la calibración isotónica, con purga.
- **Evaluación:** todas las decisiones de 1 min de BTC del **2026-10-26 00:00 UTC al 2027-01-18 00:00 UTC**
  (12 semanas, ~120 000 decisiones).
  - Etiqueta: dirección de la vela siguiente (`make_labels(h = 1, d = 1)`), binaria al 85 %, empate
    reembolsado.
  - Se calcula **una sola vez**, después del 2027-01-18, con los archivos públicos de Binance. No hace
    falta el portátil encendido.

**Criterios (los dos):**
1. Límite inferior **unilateral del 95 %** (cuantil 5 % del bootstrap de bloques diarios) de la mejora de
   log-loss (referencia − prueba), en las decisiones sin empate, > 0.
2. EV de la política B (EV estimado ≥ 0,02, tasa de empates causal de la Fase 1B) de la prueba ≥ EV de la
   referencia, en las mismas decisiones.

**Potencia declarada:**
- Con la variabilidad del Estudio 7, el error estándar de la mejora en ~120 000 decisiones es ≈ 0,0001.
- Si la mejora real fuera la vista (+0,00026), se detectaría con ≈ 85 % de probabilidad.
- Si es menor, lo más probable es «no pasa».

**Solo informativo:**
- acierto y EV de los dos modelos a +10 s de entrada, medidos con velas de 1 s;
- desglose entre semana y fin de semana UTC.

**Consecuencias:**
- **Si pasa:** ETH se incorpora como candidata al modelo registrado. Su efecto en la operación manual
  (+10 s) se confirma con una reproducción pre-registrada aparte, antes de cambiar las señales.
- **Si no pasa:** no se incorpora.

## Estudio 13 — selector multimoneda: cada minuto, la moneda con mayor ganancia esperada (pre-registro, 2026-10-25, ANTES de descargar los datos de las monedas nuevas)

**Origen:** pedido del usuario: «el bot debe analizar todas las monedas y decidir cuál tiene más
probabilidad de acierto en cada momento».

**Por qué podría ayudar:**
- más candidatas significa más minutos con una oportunidad que supere el margen;
- el efecto de microestructura que el GBM detecta en BTC puede existir en otras monedas.

**Por qué podría empeorar:**
- **Maldición del ganador:** elegir el máximo de 7 estimaciones con ruido favorece las sobreestimadas.
- Las monedas menos líquidas tienen más empates y más ruido.
- No todas las plataformas ofrecen todas las monedas a 1 minuto.

La validación fuera de muestra decide.

**Universo fijo (contado de Binance, USDT):** BTC, ETH, SOL, BNB, XRP, DOGE y ADA.

**Diseño (fase de desarrollo):**
- **Por moneda:** GBM del proyecto con `FEATURES`, walk-forward trimestral de la sección 8.
  - Pruebas del 2022-01-01 al 2025-08-31.
  - Entrenamiento con los 12 meses previos: el 20 % final para la calibración isotónica, con purga.
  - Etiquetas `h = 1`, `d = 1`.
  - Tasa de empates causal por moneda, como en la Fase 1B.
- **Selector:**
  - en cada minuto se calcula el EV estimado de cada moneda (binaria al 85 %, empate reembolsado);
  - candidatas: EV ≥ 0,02 (política B);
  - se opera **solo la de mayor EV estimado**: una operación por minuto, como máximo.
- **Comparación:** BTC sola con la política B, en el mismo código y periodo.

**Criterios de la fase de desarrollo (H13, todos):**
1. ≥ 300 operaciones;
2. Wilson 95 % del acierto > 54,05 %;
3. límite inferior del IC 95 % del EV por bootstrap de bloques semanales > 0;
4. EV > 0 en ≥ 60 % de los trimestres;
5. EV por operación del selector ≥ el de BTC sola, que el selector no sea peor.

**Solo informativo:**
- reparto de las elecciones por moneda;
- resultados por moneda sola;
- operaciones por día;
- EV total por día del selector frente a BTC sola.

**Confirmación, solo si pasa la fase de desarrollo:**
- modelos por moneda entrenados con los 12 meses hasta el 2026-10-25;
- evaluados una sola vez con todos los minutos del 2026-10-26 al 2027-01-18, la misma ventana que el
  Estudio 12, con archivos públicos de Binance;
- **aprueba si:**
  - el límite inferior de Wilson 95 % > 54,05 %;
  - el cuantil 5 % del bootstrap semanal del EV es > 0;
  - el EV por operación es ≥ el de BTC sola;
- informativo: entrada a +10 s con velas de 1 s.

**Consecuencia:** solo si confirma, el bot pasa a vigilar las 7 monedas, en modo experimental y en demo.

**Resultado de la fase de desarrollo (commit c2afdae, aplicado mecánicamente; `results/estudio13/dev.json`).**
Prueba 2022-01 → 2025-08, entrada en la apertura de la vela siguiente:

| | Operaciones (por día) | Acierto [lím. inf. 95 %] | EV por operación [IC 95 % semanal] | Trimestres EV > 0 | EV total por día |
|---|---|---|---|---|---|
| **Selector** | 640 735 (478,5) | 56,72 % [56,59 %] | +0,0418 [+0,0354; +0,0475] | 87 % | **+19,99** |
| BTC sola | 219 856 (164,3) | 56,60 % [56,39 %] | **+0,0437** [+0,0360; +0,0509] | 87 % | +7,18 |
| XRP sola | 341 985 (263,5) | 57,46 % [57,28 %] | +0,0526 [+0,0435; +0,0613] | 80 % | +13,86 |
| ETH sola | 80 714 (69,7) | 55,40 % | +0,0239 | 92 % | +1,66 |
| BNB sola | 185 632 (219,4) | 54,98 % | +0,0116 | 90 % | +2,54 |
| SOL sola | 10 407 (10,3) | 55,10 % | +0,0181 | 50 % | +0,19 |
| DOGE sola | 33 248 (30,8) | 54,51 % | +0,0074 | 69 % | +0,23 |
| ADA sola | 11 534 (13,5) | 53,02 % | −0,0169 | 40 % | −0,23 |

Elecciones del selector: XRP 47 %, BTC 25 %, BNB 15 %, ETH 8 %, DOGE 3 %, ADA 1 %, SOL 1 %.

**Veredicto: no pasa.** Cumple los criterios 1–4, pero falla el 5: el EV por operación del selector
(+0,0418) es algo **menor** que el de BTC sola (+0,0437). Según el pre-registro, no hay fase de
confirmación.

**Lectura:**
- El selector multiplica por 2,8 el EV total por día porque encuentra muchas más oportunidades, sobre
  todo en XRP. Pero el criterio fijado era por operación, y no se cambia después de mirar.
- XRP sola parece la más fuerte. Es una observación posterior a ver los datos.
- Las dos ideas (juzgar el selector por EV diario y probar XRP sola) solo pueden probarse como
  **hipótesis nuevas con datos nuevos**.
- Todo esto es con entrada en la apertura de la vela siguiente; con entrada manual a +10 s será menor.

## Estudio 14 — selector multimoneda juzgado por ganancia diaria y XRP sola (pre-registro, 2026-10-25, ANTES de existir datos posteriores al 2026-10-25)

**Origen y advertencia:** las dos hipótesis nacen de **mirar** la fase de desarrollo del Estudio 13:
- el selector multiplicó por 2,8 el EV total por día, aunque su EV por operación fue algo menor que el de
  BTC sola;
- XRP sola fue la más fuerte: 57,46 %, EV +0,0526.

Por eso **solo cuentan datos nuevos**. Ninguna cifra de 2022–2025 sirve como evidencia para ellas.

**Por qué podrían ser reales:**
- la pieza que explica la ventaja de BTC (continuación de la presión del final de la vela, docs/08)
  debería existir en otras monedas;
- XRP tiene un tick grande respecto de su precio, lo que puede volver la presión de corto plazo más
  persistente.

**Por qué podrían fallar:**
- maldición del ganador: XRP pudo ser la mejor por suerte entre 7;
- las ventajas de 2022–2025 se debilitaron en el último año en otros estudios.

**Común a las dos hipótesis:**
- **Universo, modelo, etiquetas y política:** los del Estudio 13 (GBM con `FEATURES`, `h = 1`, `d = 1`, EV
  estimado ≥ 0,02, binaria al 85 %, empate reembolsado).
- **Entrenamiento (una vez):** por moneda, con los 12 meses hasta el 2026-10-25 23:59 UTC. El 20 % final se
  usa para la calibración isotónica.
- **Evaluación:** todos los minutos del **2026-10-26 00:00 UTC al 2027-01-18 00:00 UTC**, con los archivos
  públicos de Binance. Se calcula una sola vez, después del 2027-01-18. Es la misma ventana que los
  Estudios 12 y 13.
- **Corrección:** Bonferroni, α = 0,025 por hipótesis.

**Hipótesis y criterios:**
- **H14a, selector:**
  1. Wilson 95 % > 54,05 %;
  2. cuantil 2,5 % del bootstrap semanal del EV por operación > 0;
  3. EV total por día del selector ≥ el de BTC sola en el mismo periodo.
- **H14b, XRP sola:**
  1. Wilson 95 % > 54,05 %;
  2. cuantil 2,5 % del bootstrap semanal del EV por operación > 0.

**Solo informativo:**
- entrada a +10 s, con velas de 1 s de cada moneda elegida;
- reparto de las elecciones por moneda;
- entre semana frente a fin de semana.

**Consecuencias:**
- **Si H14a aprueba:** el bot pasa a vigilar las 7 monedas en demo. Como sigue siendo con entrada
  inmediata, antes se mide su efecto con entrada manual en una reproducción pre-registrada aparte.
- **Si solo H14b aprueba:** XRP se añade a BTC en demo, con la misma condición.
- **Si no aprueba ninguna:** sigue solo BTC.

## Estudio 15 — presión dentro del minuto con velas de 1 segundo (mejora P1) (pre-registro, 2026-10-25, ANTES de descargar las velas de 1 s)

**Origen:** según el análisis de docs/08 (sección 2), la ventaja del GBM de BTC a 1 minuto sale sobre todo de
`clpos`, dónde cerró la vela dentro de su rango. Es la continuación de la presión de los últimos segundos,
más fuerte con volatilidad baja. El modelo la ve solo de forma indirecta. Las velas de 1 s de Binance
(gratuitas, con volumen comprador agresor) permiten medirla directamente.

**Mecanismo:** las órdenes grandes repartidas en pedazos (flujo con memoria) siguen empujando al inicio del
minuto siguiente. Cuanto más concentrada y unilateral sea la presión al final de la vela, más probable es
que continúe.

**Por qué podría no mejorar:** `clpos` y `r0` ya capturan la mayor parte. Lo que queda puede ser ruido de
segundos.

**Expectativa declarada:** mejora pequeña o nula.

**Hipótesis única H15:** añadir al GBM de BTC/USDT a 1 minuto un bloque fijo de 6 variables medidas
**dentro** de la vela de decisión mejora la predicción de la dirección de la vela siguiente.

**Bloque nuevo.** Todo con las velas de 1 s de la vela de decisión t, segundos 0–59:

| Variable | Definición |
|---|---|
| `s_r5`, `s_r10`, `s_r20` | ln(cierre del segundo 59 / cierre del segundo 59−k), dividido por `vol60 · √(k/60)`, con k = 5, 10, 20 |
| `s_tib10` | 2 · Σ compras agresoras / Σ volumen − 1, en los segundos 50–59 (0 si no hubo volumen) |
| `s_vol10` | Volumen de los segundos 50–59 / volumen del minuto |
| `s_n10` | Operaciones de los segundos 50–59 / operaciones del minuto |

`vol60` es el de `compute_features`. Si al minuto le faltan más de 10 velas de 1 s, sus variables valen
NaN y no hay decisión **en ninguno de los dos modelos**. Cada segundo sin vela toma el cierre anterior y
volumen 0.

**Diseño (fase de desarrollo):**
- **Modelos:** GBM del proyecto. Referencia `FEATURES`; prueba `FEATURES` + el bloque nuevo. Mismas
  decisiones.
- **Etiquetas:** `h = 1`, `d = 1`, binaria al 85 %, empate reembolsado, política B (EV estimado ≥ 0,02).
- **Walk-forward trimestral:** pruebas del 2024-07-01 al 2025-08-31 (5 trimestres), entrenamiento con los
  12 meses anteriores, 20 % de calibración isotónica, purga. Hacen falta velas de 1 s desde 2023-07.

**Criterios (todos):**
1. ≥ 300 operaciones del modelo de prueba;
2. Wilson 95 % > 54,05 %;
3. IC 95 % de la mejora de log-loss (bootstrap de bloques diarios, en todas las decisiones sin empate) con
   límite inferior > 0;
4. EV de la política B del modelo de prueba ≥ el de la referencia;
5. EV > 0 en ≥ 60 % de los trimestres.

**Control obligatorio (ítem 39):** si los dos modelos predicen igual, la ejecución se aborta.

**Confirmación, solo si pasa la fase de desarrollo:**
- los dos modelos se entrenan con los 12 meses hasta el 2026-10-25;
- se evalúan una sola vez con todos los minutos del 2026-10-26 al 2027-01-18 (velas de 1 s de Binance);
- criterios: cuantil 5 % del bootstrap diario de la mejora de log-loss > 0 y EV de la prueba ≥ el de la
  referencia;
- informativo: entrada a +10 s.

**Consecuencia:** solo si confirma, el bloque se incorpora al modelo registrado. Antes, una reproducción
pre-registrada mide su efecto con entrada manual.

**Resultado de la fase de desarrollo (commit 4e9a70b, aplicado mecánicamente; `results/estudio15/dev.json`).**
Prueba 2024-07 → 2025-08, 26 meses de velas de 1 s de Binance, entrada en la apertura de la vela siguiente:

| Modelo | Operaciones política B | Acierto [lím. inf. 95 %] | EV | Acierto en todas las decisiones |
|---|---|---|---|---|
| Referencia (`FEATURES`) | 51 386 | 56,89 % [56,44 %] | +0,048 | 52,00 % |
| **Prueba (+ bloque de 1 s)** | **104 813** | **58,56 % [58,25 %]** | **+0,079** | 52,82 % |

- Mejora de log-loss: **+0,00206** [IC 95 %: +0,00182; +0,00230], unas 7 veces la importancia de `clpos`.
- **Veredicto: PASA los 5 criterios.**
- La ejecución se repitió para guardar las predicciones y dio resultados idénticos.

**Verificación adversaria (informativa; `scripts/verificacion_estudio15.py` → `results/estudio15/verificacion.json`):**

**Sin fuga:** el cierre del segundo 59 coincide con el de la vela de 1 min en el **100 %** de los minutos.
Con un desfase de un minuto coincidiría solo el 2,7 %.

**Etiqueta recalculada solo con velas de 1 s, por retraso de entrada** (políticas B de cada modelo):

| Entrada tras el cierre | Referencia: acierto / EV | Prueba: acierto / EV |
|---|---|---|
| +1 s | 55,99 % / +0,033 | **57,31 % / +0,057** |
| +2 s | 55,69 % / +0,028 | 56,69 % / +0,046 |
| +5 s | 54,93 % / +0,015 | 55,34 % / +0,023 |
| +10 s | 53,96 % / −0,002 | 54,11 % / +0,001 |
| +20 s | 53,26 % / −0,013 | 52,66 % / −0,024 |
| +30 s | 52,55 % / −0,025 | 51,93 % / −0,037 |

**Lectura:**
- El bloque de 1 s **añade información real** y duplica las oportunidades. Pero su ventaja extra, como la
  del modelo base, vive en los **primeros segundos**.
- Con entrada en ≤ 2 s: 56,7–57,3 % y EV casi el doble que la referencia.
- A +5 s la ventaja es pequeña. A +10 s, en este periodo, desaparece en los dos modelos.
- El H5a de octubre de 2026 (56,1 % a +10 s) muestra que eso cambia según el periodo. La confirmación
  pre-registrada decide.
- **Implicación:** el camino a 57–60 % pasa por **entrar en 1–2 segundos**, lo que en la práctica exige
  automatizar.

## Estudio 16 — señal anticipada para que el clic manual caiga al cierre (propuesta P8) (pre-registro, 2026-10-25, ANTES de calcular nada)

**Origen:**
- la ventaja de BTC a 1 minuto vive en los primeros 1–2 s después del cierre de la vela (Estudio 15:
  57,3 % a +1 s, 54,1 % a +10 s);
- no hay plataforma legal con API para automatizar la entrada (docs/03, 2.2).

**Idea:** el bot decide **antes** del cierre, en el segundo k de la vela t, con la información disponible
hasta ese segundo. El usuario hace clic L segundos después; la entrada cae en t + k + L y el contrato vence
60 s más tarde. Con k + L = 60, el clic cae justo al cierre.

**Por qué podría funcionar:** la presión que continúa después del cierre ya está en marcha en los segundos
50–59.

**Por qué podría fallar:** lo que ocurra entre el segundo k y el cierre es información que el modelo ya no
ve. Si la ventaja depende de los últimos segundos exactos, se pierde.

**Expectativa declarada:** acierto menor que con entrada inmediata, pero quizá mayor que el de avisar al
cierre y entrar a +10 s (54,1 % en el desarrollo del Estudio 15).

**Hipótesis (familia de 2, Bonferroni α = 0,025):**
- **H16a:** decisión en el segundo **k = 55**, clic con latencia **L = 5 s**.
- **H16b:** decisión en el segundo **k = 50**, clic con latencia **L = 10 s**.

**Datos:** velas de 1 s de BTC/USDT de Binance (cierre, volumen, compras agresoras y operaciones) de
2023-07 a 2025-08, y velas de 1 min de contado.

**Variables (todas con información hasta el segundo k de la vela t):**
- `FEATURES` de la vela **t−1** (ya cerrada);
- **bloque parcial**, con `P_j` = último precio negociado antes del segundo j de la vela t y `vol60` de
  t−1:

| Variable | Definición |
|---|---|
| `p_ret` | ln(`P_k` / apertura de t) / (`vol60` · √(k/60)) |
| `p_clpos` | (`P_k` − mín. parcial) / (máx. parcial − mín. parcial) en los segundos 0…k−1 (0,5 si el rango es 0) |
| `p_range` | ln(máx. parcial / mín. parcial) / `vol60` |
| `p_r5`, `p_r10`, `p_r20` | ln(`P_k` / `P_{k−j}`) / (`vol60` · √(j/60)), con j = 5, 10, 20 |
| `p_tib10` | 2 · Σ compras agresoras / Σ volumen − 1 en los segundos k−10…k−1 (0 sin volumen) |
| `p_vol10` | Volumen de los segundos k−10…k−1 / volumen de los segundos 0…k−1 |
| `p_n10` | Ídem con el número de operaciones |

Si faltan más de 10 velas de 1 s entre los segundos 0…k−1, no hay decisión.

**Etiqueta (específica de cada hipótesis):**
- entrada = último precio negociado antes de t + k + L;
- salida = último precio negociado antes de t + k + L + 60 s;
- dirección con el redondeo a medio tick del proyecto; empate si no se mueve.
- El modelo se entrena con esa misma etiqueta.

**Modelo y validación:**
- GBM del proyecto, política B (EV estimado ≥ 0,02, binaria 85 %, empate reembolsado).
- Tasa de empates causal: media de 1 440 min de la etiqueta, desplazada 3 minutos.
- Walk-forward trimestral con pruebas del 2024-07-01 al 2025-08-31, 12 meses de entrenamiento, 20 % de
  calibración isotónica y purga.

**Criterios por hipótesis (todos):**
1. ≥ 300 operaciones;
2. p binomial unilateral < 0,025 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. límite inferior del IC 97,5 % del EV (bootstrap semanal) > 0;
5. EV > 0 en ≥ 60 % de los trimestres.

**Comparación informativa:** el modelo de prueba del Estudio 15 avisando al cierre con entrada a +10 s,
en el mismo periodo: 54,11 %, EV +0,001.

**Solo informativo:** sensibilidad a la latencia real. El modelo de cada hipótesis se evalúa con
L ∈ {0, 3, 5, 8, 10, 15} s.

**Confirmación, solo si alguna pasa:**
- se entrena con los 12 meses hasta el 2026-10-25;
- se evalúa una sola vez con todos los minutos del 2026-10-26 al 2027-01-18;
- mismos criterios 2–4, con IC unilateral 97,5 %.
- Antes de usarla en la demo hay que medir la latencia real del usuario.

**Resultado de la fase de desarrollo (commit 6559817, aplicado mecánicamente; `results/estudio16/dev.json`).**
Prueba 2024-07 → 2025-08:

| Hipótesis | Operaciones | Acierto [lím. inf. 95 %] | p | EV [IC 97,5 % semanal] | Trimestres EV > 0 | Veredicto |
|---|---|---|---|---|---|---|
| **H16a**: aviso en el segundo 55, clic a +5 s | 51 738 | **57,33 %** [56,88 %] | 1,5·10⁻⁴⁷ | **+0,056** [+0,039; +0,072] | 5/5 | **PASA** |
| **H16b**: aviso en el segundo 50, clic a +10 s | 27 673 | **57,00 %** [56,39 %] | 1,3·10⁻²¹ | **+0,050** [+0,031; +0,070] | 5/5 | **PASA** |

**Sensibilidad a la latencia real del clic** (informativa; cada modelo con su etiqueta a otras latencias):

| Clic tras el aviso | H16a (aviso en el s 55) | H16b (aviso en el s 50) |
|---|---|---|
| 0 s | 58,1 % / +0,070 | 59,2 % / +0,089 |
| 3 s | 57,8 % / +0,065 | 58,9 % / +0,083 |
| 5 s | **57,3 % / +0,056** | 58,3 % / +0,074 |
| 8 s | 55,8 % / +0,029 | 57,4 % / +0,057 |
| 10 s | 55,2 % / +0,020 | **57,0 % / +0,050** |
| 15 s | 54,3 % / +0,005 | 55,6 % / +0,027 |

**Comparación con avisar al cierre:** en el mismo periodo, el modelo del Estudio 15 avisando al cierre con
clic a +10 s daba 54,1 % y EV +0,001. **Anticipar el aviso recupera la ventaja para la operación manual.**
H16b es la más tolerante: aún con 15 s de demora da 55,6 % y EV +0,027.

**Verificación:**
- el precio «último antes de t+60 s» de las velas de 1 s coincide con el cierre de la vela de 1 min en el
  **100 %** de 1 141 920 minutos (control con un minuto de desfase: 3,9 %);
- las pruebas automáticas confirman que el bloque parcial no cambia si se altera lo que ocurre desde el
  segundo k.

**Siguiente paso pre-registrado:** confirmación con los datos del 2026-10-26 al 2027-01-18. Antes de usarla
en la demo, medir la latencia real del clic del usuario.

## Estudio 17 — Fibonacci («zona dorada») e ICT, desarmados (pre-registro, 2026-10-26, ANTES de calcular nada)

**Origen:** dos transcripciones de videos de redes que trajo el usuario:
1. **Fibonacci:** marcar el impulso (de su inicio a su fin), esperar a que el retroceso toque la «zona
   dorada» del **50–61,8 %** y entrar a favor del impulso. Si la estructura es «irregular», la extensión
   une varios impulsos.
2. **ICT:** «10 conceptos» (FVG, FVG inverso, *order blocks*, liquidez por tiempo, toma de liquidez,
   estructura, quiebre de estructura, máximos y mínimos iguales, premium/descuento y desplazamiento).

**Evidencia previa (2026-10-26):**
- No hay estudios revisados por pares que respalden Fibonacci. Un análisis práctico de 40 243 correcciones
  concluye que la concentración cerca de sus niveles es la que daría el azar.
- El único test sistemático de ICT es un preprint (Mahadzva, 2026: walk-forward, permutación y periodo
  bloqueado en divisas intradía). No encuentra que funcione «tal como se enseña». La toma de liquidez
  predice **continuación**, no la reversión que se enseña.

**Expectativa declarada:** «SIN SEÑAL» en las dos partes.

### Parte A — ¿la zona dorada es especial? (H17-FIB-BTC, H17-FIB-XAU, H17-FIB-EUR; Bonferroni α = 0,0167)

**Datos:** velas de 15 min (UTC) de BTC/USDT (contado de Binance), XAU/USD y EUR/USD (HistData, velas
medias), 2022-01-01 → 2025-08-31. Se usan solo las velas con datos.

**Impulsos (zigzag causal):** umbral = 3 × ATR14 de 15 min.
- Un mínimo de giro queda **confirmado** cuando el cierre sube ≥ umbral sobre el mínimo acumulado desde el
  último máximo de giro; un máximo, de forma simétrica.
- Impulso alcista = del mínimo confirmado L al máximo H, en la vela en que H queda confirmado. Bajista:
  simétrico.

**Retroceso:** desde la confirmación de H, r(t) = (H − mín_t) / (H − L). Bajista: simétrico.

**Eventos:** primer toque de cada zona en ese retroceso, mientras no se toque ni H ni L:
- Z1 = [0,382; 0,5);
- **Z2 = [0,5; 0,618] (dorada)**;
- Z3 = (0,618; 0,786].

El precio de entrada es el borde menos profundo de la zona, en `r_e`.

**Resultado:** a partir de la vela siguiente al toque, qué se alcanza primero:
- H (continuación, acierto) o L (fallo);
- si caen en la misma vela, cuenta fallo;
- sin resolución en 200 velas, el evento se descarta.

**Referencia del azar:** sin tendencia, partiendo de `r_e`, la probabilidad de llegar antes a H es 1 − `r_e`.
**Exceso** = continuación observada − (1 − `r_e`).

**Criterios por instrumento (los dos):**
1. límite inferior del IC 98,33 % (bootstrap semanal) del exceso en Z2 > 0;
2. límite inferior del IC 98,33 % de [exceso Z2 − media(exceso Z1, exceso Z3)] > 0: la zona dorada mejor
   que sus vecinas.

### Parte B — ¿los conceptos ICT y Fibonacci añaden información a nuestro modelo? (H17-ICT, una hipótesis)

**Diseño:** el del Estudio 15. GBM de BTC a 1 min, `FEATURES` frente a `FEATURES` + bloque nuevo, mismas
decisiones, etiquetas `h = 1`, `d = 1`, política B, walk-forward con pruebas 2024-07 → 2025-08.

**Bloque nuevo (10 variables; velas de 1 min, causales, fila t con velas hasta su cierre):**

| Variable | Concepto | Definición |
|---|---|---|
| `ict_sweep_hi` | Toma de liquidez arriba | 1 si `máx_t` > máx(máx de t−60…t−1) y `cierre_t` < ese máximo; si no, 0 |
| `ict_sweep_lo` | Toma de liquidez abajo | 1 si `mín_t` < mín(mín de t−60…t−1) y `cierre_t` > ese mínimo |
| `ict_bos` | Quiebre de estructura | +1 si `cierre_t` > máx(máx de t−60…t−1); −1 si `cierre_t` < mín(mín de t−60…t−1); 0 si no |
| `ict_fvg` | FVG o desplazamiento en t | (`mín_t` − `máx_{t−2}`) / (`c_t`·vol60) si > 0; (`máx_t` − `mín_{t−2}`) / (`c_t`·vol60) si < 0; 0 si no |
| `ict_fvg15` | FVG recientes | Nº de FVG alcistas − Nº de bajistas en las velas t−14…t |
| `ict_pd` | Premium/descuento | (`c_t` − mín de 240) / (máx de 240 − mín de 240) en t−239…t (0,5 si el rango es 0) |
| `ict_eqh` | Máximos iguales | Nº de velas en t−59…t−1 con (máx de 60 − `máx_j`) ≤ 0,1·vol60·`c_t`, sin contar la del máximo |
| `ict_eql` | Mínimos iguales | Ídem con los mínimos |
| `fib_r` | Retroceso actual | Profundidad r del retroceso del último impulso del zigzag de 1 min (umbral 3·ATR14 de 1 min), con signo + si el impulso fue alcista y − si bajista; 0 sin impulso confirmado |
| `fib_gold` | En zona dorada | 1 si \|`fib_r`\| ∈ [0,5; 0,618], 0 si no |

**Criterios (los 5 del Estudio 15):**
1. ≥ 300 operaciones;
2. Wilson 95 % > 54,05 %;
3. IC 95 % de la mejora de log-loss (bootstrap diario) con límite inferior > 0;
4. EV de la prueba ≥ EV de la referencia;
5. EV > 0 en ≥ 60 % de los trimestres.

Control del ítem 39 obligatorio.

**Si la Parte B pasa:** confirmación con los datos del 2026-10-26 al 2027-01-18, como en el Estudio 15.
**Si no pasa ninguna parte:** SIN SEÑAL. Se documenta qué pieza, si alguna, mostró información.

**Resultado (commit a1b2de9, aplicado mecánicamente; `results/estudio17/resultado.json`):**

**Parte A, Fibonacci.** Porcentaje de veces que el precio retoma el impulso antes de volver a su inicio,
frente a lo que daría el azar:

| Instrumento | Z1 (38,2–50 %) | **Z2 dorada (50–61,8 %)** | Z3 (61,8–78,6 %) | Dorada − vecinas [IC 98,33 %] |
|---|---|---|---|---|
| BTC/USDT | 62,7 % vs 61,8 % (656) | **50,0 % vs 50,0 %** (1 257) | 39,2 % vs 38,2 % (1 810) | −0,009 [−0,034; +0,014] |
| XAU/USD | 62,3 % vs 61,8 % (469) | **50,4 % vs 50,0 %** (754) | 39,7 % vs 38,2 % (1 053) | −0,006 [−0,034; +0,023] |
| EUR/USD | 60,5 % vs 61,8 % (517) | **49,8 % vs 50,0 %** (791) | 39,5 % vs 38,2 % (1 010) | −0,002 [−0,032; +0,025] |

**Ninguna pasa.** La zona dorada se comporta **exactamente como el azar** en los tres mercados, y no es
mejor que sus vecinas. El 50 % de «acierto» que se ve en la zona dorada es pura geometría: el precio está a
la misma distancia del fin y del inicio del impulso.

**Parte B, ICT y Fibonacci en el modelo de BTC a 1 min:**

| Modelo | Operaciones | Acierto [lím. inf.] | EV |
|---|---|---|---|
| Referencia | 51 386 | 56,89 % [56,44 %] | +0,048 |
| + bloque ICT/Fibonacci | 65 730 | 56,30 % [55,90 %] | +0,038 |

- Mejora de log-loss: +0,00002 [IC 95 %: −0,00004; +0,00009], que incluye 0.
- **No pasa:** fallan los criterios 3 y 4. El bloque no añade información y baja la ganancia esperada.

**Estudio 17: SIN SEÑAL.**

## Estudio 18 — aviso anticipado con contratos que SÍ existen: BTC a 3, 5 y 15 minutos (pre-registro, 2026-10-27, ANTES de calcular nada)

**Origen:** el usuario comprobó en su plataforma demo (IQ Option) que **no hay BTC/USD a 1 minuto**. Hay
binaria de BTC con vencimiento de **15 minutos** y «blitz» de **3 minutos** como mínimo. La ventaja
validada en desarrollo (Estudios 15 y 16) es a 1 minuto y vive en los primeros segundos. Pregunta: con el
mismo aviso anticipado (segundo 50, clic 10 s después), ¿hay ventaja aprovechable si el contrato dura 3,
5 o 15 minutos?

**Por qué podría haberla:**
- la presión del final de la vela continúa unos segundos;
- la tendencia y la volatilidad de varios minutos (`FEATURES`: rendimientos de 5–240 min, medias, RSI,
  volatilidad) pueden informar plazos más largos.

**Por qué podría no haberla:**
- a 3–15 minutos el efecto de los primeros segundos se diluye en el ruido;
- a 15 minutos los Estudios 2 y 4 no confirmaron ventaja (con entrada a 1 min y sin velas de 1 s).

**Expectativa declarada:** ventaja menor que a 1 minuto; probable «SIN SEÑAL» a 15 minutos.

**Hipótesis (familia de 3, Bonferroni α = 0,0167):**
- **H18-3:** vencimiento de 180 s;
- **H18-5:** 300 s;
- **H18-15:** 900 s.

**Diseño común:**
- **Variables:** las del Estudio 16 con k = 50, es decir, `FEATURES` de la vela t−1 + bloque parcial
  de la vela t hasta el segundo 50.
- **Entrada:** último precio negociado antes de t + 60 s (clic 10 s después del aviso, como H16b).
- **Salida:** último precio negociado antes de t + 60 s + duración. Dirección con redondeo a medio tick;
  empate si no se mueve.
- El modelo de cada hipótesis se entrena con su propia etiqueta.
- **Validación:** GBM del proyecto, política B (EV ≥ 0,02; binaria 85 %; empate reembolsado; tasa de
  empates causal desplazada lo suficiente para que la etiqueta ya sea conocida). Walk-forward con pruebas
  2024-07 → 2025-08, 12 meses de entrenamiento, 20 % de calibración y purga igual a la duración más 2 min.

**Criterios (cada hipótesis, todos):**
1. ≥ 300 operaciones;
2. p binomial unilateral < 0,0167 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. límite inferior del IC 98,33 % del EV (bootstrap semanal) > 0;
5. EV > 0 en ≥ 60 % de los trimestres.

**Solo informativo:**
- **«Una operación a la vez»:** solo se toma una señal si no hay otra abierta. Es lo realista a mano.
  Se informan sus operaciones, acierto y EV.
- **Latencia del clic:** L ∈ {0, 5, 10, 15, 20} s.
- **Pago del 80 %.**

**Consecuencias:**
- Si alguna pasa, se pre-registra su confirmación con los datos del 2026-10-26 al 2027-01-18 y se añade
  esa duración al modo de señales de la demo, marcada «experimental».
- Si ninguna pasa, SIN SEÑAL para esas duraciones.

**Resultado de la fase de desarrollo (commit e286b2c, aplicado mecánicamente; `results/estudio18/dev.json`).**
Prueba 2024-07 → 2025-08, aviso en el segundo 50 y clic a +10 s:

| Hipótesis | Operaciones (por día) | Acierto [lím. inf. 95 %] | p | EV [IC 98,33 %] | Una a la vez: ops/día, acierto, EV |
|---|---|---|---|---|---|
| H18-3 (3 min) | 30 680 (84) | 54,09 % [53,53 %] | — | +0,001 [−0,016; +0,018] | 55/día, 53,5 %, −0,010 |
| H18-5 (5 min) | 22 691 (54) | **54,70 %** [54,05 %] | 0,025 | +0,012 [−0,016; +0,039] | 26/día, 54,0 %, −0,000 |
| H18-15 (15 min) | 69 206 (162) | 54,19 % [53,82 %] | 0,24 | +0,002 [−0,021; +0,025] | 28/día, 54,1 %, +0,001 |

**Veredicto: ninguna pasa.** Las tres quedan en ~54 %, justo en el punto de equilibrio con pago del 85 %.
**Estudio 18: SIN SEÑAL** con pago del 85 %.

**Lectura:**
- La ventaja de BTC está concentrada en el **contrato de 1 minuto** (57,0 % en el Estudio 16). A 3–15
  minutos se diluye hasta el empate económico.
- Con pago del 80 % todas pierden: EV entre −0,025 y −0,015.
- **Observación posterior a ver los datos (no es evidencia):** el punto de equilibrio baja si el pago es
  mayor. Con 54,1–54,7 % de acierto, un pago del **90 %** daría EV de +0,028 a +0,039 por operación. Si
  la plataforma paga ≥ 90 % en esas duraciones, haría falta un estudio nuevo con ese pago, confirmado con
  datos nuevos.

## Estudio 19 — vencimiento fijo cada 15 minutos: entrar en el último tramo (pre-registro, 2026-10-27, ANTES de calcular nada)

**Origen:**
- en la plataforma del usuario (IQ Option), la binaria de BTC vence **cada 15 minutos** con pago del
  **87 %**, es decir, equilibrio en 53,48 %;
- según la guía de la plataforma, se puede comprar hasta una línea punteada antes del vencimiento.

**Idea:** si el vencimiento es a hora fija (:00, :15, :30, :45 UTC), entrar R minutos antes convierte el
contrato en uno de R minutos. La ventaja de BTC es mayor cuanto más corto el plazo (Estudio 16: 57,0 % a
1 min; Estudio 18: ~54 % a 3–15 min).

**Expectativa declarada:**
- R = 1 debería parecerse al Estudio 16 (≈ 57 %);
- R = 2–5, entre 54 y 56 %.

El usuario debe confirmar el R mínimo que permite la plataforma.

**Diseño (fase de desarrollo):**
- **Señal:** aviso en el segundo 50 de la vela t; entrada = último precio negociado antes de t + 60 s
  (clic ≤ 10 s); salida = último precio antes del vencimiento, en t + 60 s + R·60 s.
- **Solo se evalúan las velas t** con (minuto de t + 1 + R) múltiplo de 15, es decir, las que dejan el
  vencimiento exactamente en un cuarto de hora.
- **Variables:** las del Estudio 16 con k = 50.
- **Modelo:** GBM entrenado con la etiqueta de duración R·60 s en **todas** las velas (la hora del reloj
  no cambia el contrato). Walk-forward con pruebas 2024-07 → 2025-08, 12 meses de entrenamiento, 20 % de
  calibración y purga.
- **Política:** EV estimado ≥ 0,02 con el **pago del 87 %**, empate reembolsado.

**Hipótesis (familia de 4, Bonferroni α = 0,0125):**
- **H19-R1:** R = 1;
- **H19-R2:** R = 2;
- **H19-R3:** R = 3;
- **H19-R5:** R = 5.

**Criterios (cada una, todos):**
1. ≥ 300 operaciones;
2. p binomial unilateral < 0,0125 frente a 53,48 %;
3. Wilson 95 % > 53,48 %;
4. límite inferior del IC 98,75 % del EV (bootstrap semanal) > 0;
5. EV > 0 en ≥ 60 % de los trimestres.

**Solo informativo:** latencia del clic L ∈ {0, 5, 10, 15} s y pago del 85 %.

**Confirmación:** para la R que el usuario confirme como la mínima disponible, se usa el mismo modelo
congelado:
- **R = 1:** el modelo ya congelado del Estudio 16, `BTCUSDT-anticipada-k50-L10-35b764`, porque su
  etiqueta es idéntica;
- **R > 1:** un modelo congelado nuevo, entrenado con los 12 meses hasta el 2026-10-25.

Se evalúa una sola vez con los datos del 2026-10-26 al 2027-01-18.

**Consecuencia:** si pasa el desarrollo, la demo avisa solo en esas velas, con la hora de vencimiento a
elegir. Siempre solo en demo.

**Resultado de la fase de desarrollo (commit 75102ce, aplicado mecánicamente; `results/estudio19/dev.json`).**
Prueba 2024-07 → 2025-08, pago del 87 %, solo velas alineadas al cuarto de hora:

| Hipótesis | Operaciones (por día) | Acierto [lím. inf. 95 %] | EV [IC 98,75 %] | Latencia 0 / 5 / 10 / 15 s |
|---|---|---|---|---|
| **H19-R1** (1 min antes) | 2 769 (7,3) | **55,42 %** [53,47 %] | **+0,033** [−0,013; +0,079] | 57,4 / **58,1** / 55,4 / 53,2 % |
| H19-R2 | 3 025 (7,4) | 53,24 % [51,44 %] | −0,004 | 54,2 / 53,9 / 53,2 / 50,9 % |
| H19-R3 | 2 576 (6,3) | 53,69 % [51,75 %] | +0,004 | 53,6 / 53,4 / 53,7 / 52,1 % |
| H19-R5 | 2 417 (6,6) | 53,22 % [51,22 %] | −0,005 | 52,7 / 52,7 / 53,2 / 50,6 % |

**Veredicto:** ninguna pasa los criterios estrictos. **R = 1 es la única con ventaja puntual.** No
alcanza significación porque las velas alineadas son 1 de cada 15 (≈ 7 operaciones al día). Su etiqueta
es la misma del Estudio 16 (H16b: 57,00 % con 27 673 operaciones, que sí pasó); el subconjunto alineado
queda 1,6 puntos por debajo, dentro de lo esperable por azar con 2 769 operaciones.

**Consecuencia práctica:**
- Si la plataforma deja comprar la binaria de 15 min con ≥ 1 min hasta el vencimiento, la demo puede
  usar el modelo congelado H16b en modo `--cuarto 1 --pago 87`.
- Es solo práctica: la confirmación de H16b con datos nuevos sigue siendo la que decide (enero de 2027).
- R ≥ 2 no tiene ventaja: no se usa.

## Estudio 20 — repetición mes a mes «como si no hubiera pasado» (2025-09 → 2026-10) (pre-registro, 2026-10-27, ANTES de calcular nada)

**Origen (pedido del usuario, 2026-10-27):** probar mes a mes lo corrido del mercado, decidiendo cada mes
solo con la información anterior, para ver si de verdad «se habría acertado».

**Periodo:** del 2025-09-01 al 2026-10-25 (14 meses; octubre de 2026 incompleto). Este tramo **nunca se usó
para elegir ni ajustar** el modelo del Estudio 16 (su desarrollo fue 2024-07 → 2025-08), pero **no es virgen**:
- la Fase 1B evaluó allí (2025-09 → 2026-08) otro modelo GBM de BTC a 1 min (56,4 %);
- el Estudio 5 evaluó otro modelo con datos desde el 2026-10-04 (H5a 56,11 %);
- el modelo congelado de la demo se entrenó con 2025-10-26 → 2026-10-25, pero nunca se evaluó allí.

Por eso es una **verificación de solidez**, no una confirmación. La confirmación sigue siendo la de
2026-10-26 → 2027-01-18 (Estudios 12, 14, 15, 16 y 19), que este estudio **no mira**.

**Diseño:**
- **Modelo:** exactamente el de H16b (variables `FEATURES` de la vela anterior + bloque parcial de 1 s
  hasta el segundo 49, k = 50; etiqueta: último precio antes de t + 60 s contra último precio antes de
  t + 120 s, con clic a +10 s). GBM con la misma semilla.
- **Repetición mensual:** para cada mes M, se entrena con los 12 meses anteriores al inicio de M (último
  20 % para calibrar, con purga) y se aplica solo a M. Nada de M ni de meses posteriores entra en el
  entrenamiento, la calibración ni la estimación de empates (tasa móvil de 1 440 minutos, desplazada).
- **Datos:** velas de 1 s y 1 min de Binance (data.binance.vision), las mismas fuentes que el Estudio 16.
- **Política:** EV estimado ≥ 0,02, empate reembolsado.

**Hipótesis (familia de 2, Bonferroni α = 0,025):**
- **H20a:** contrato de 1 min en todas las velas, pago del 85 % (equilibrio 54,05 %).
- **H20b:** solo las velas que dejan el vencimiento en un cuarto de hora exacto (modo `--cuarto 1` de la
  demo, binaria de 15 min de la plataforma del usuario), pago del 87 % (equilibrio 53,48 %).

**Criterios (cada una, todos):**
1. ≥ 300 operaciones;
2. p binomial unilateral < 0,025 frente al equilibrio;
3. límite inferior de Wilson 95 % > equilibrio;
4. límite inferior del IC 97,5 % del EV (bootstrap por semanas) > 0;
5. EV > 0 en ≥ 60 % de los meses.

**Expectativa declarada:** si la ventaja del Estudio 16 se mantiene, H20a ≈ 55–57 %. Riesgo conocido: en
los Estudios 2–4 las ventajas de ~55 % hasta 2025 desaparecieron en el último año.

**Solo informativo (no decide nada):**
- tabla mes a mes (operaciones, acierto, EV);
- latencia del clic L ∈ {0, 5, 10, 15} s;
- **selectividad:** acierto y EV si solo se operara cuando la probabilidad del modelo es ≥ 0,56 / 0,58 /
  0,60 / 0,62 (menos señales, ¿más acierto?). Usar un umbral así exigiría un pre-registro propio.

**Consecuencia:**
- si H20a o H20b no pasan, la demo sigue siendo solo práctica y se informa con claridad;
- si pasan, se refuerza (sin sustituir) la confirmación de enero de 2027.

**Resultado (commit 2958e67, aplicado mecánicamente; `results/estudio20/resultado.json`).** Se repitió con
la misma semilla para guardar las predicciones: resultado idéntico.

| Hipótesis | Operaciones (por día) | Acierto [lím. inf. 95 %] | EV [IC 97,5 %] | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|---|
| **H20a** (1 min, pago 85 %) | 22 129 (52,8) | **57,60 %** [56,91 %] | **+0,059** [+0,038; +0,075] | 10 de 14 | **PASA** |
| H20b (cuarto de hora, pago 87 %) | 2 174 (6,1) | 54,90 % [52,69 %] | +0,024 [−0,019; +0,068] | 9 de 14 | no pasa |

Mes a mes (H20a): 61,6 / 56,0 / 52,2 / 55,0 / 61,1 / 51,8 / 53,2 / 56,3 / 61,2 / 53,1 / 59,7 / 58,8 /
58,6 / 58,7 % (2025-09 → 2026-10). Latencia del clic 0 / 5 / 10 / 15 s: 58,9 / 59,2 / 57,6 / 55,8 %.

**Selectividad (informativo):** al operar solo cuando la probabilidad del modelo alcanza un umbral,

| Umbral | 2025-09 → 2026-10 | Verificación 2024-07 → 2025-08 (mismo esquema mensual, periodo ya usado) |
|---|---|---|
| todas | 57,60 % (22 129) | 56,92 % (28 160) |
| p ≥ 0,58 | 60,15 % (9 640) | 58,49 % (12 026) |
| **p ≥ 0,60** | **62,53 %** [61,10 %] (5 185), EV +0,135 | **59,71 %** [58,21 %] (4 494), EV +0,096 |
| p ≥ 0,62 | 62,58 % (1 754) | 61,68 % (2 254) |

Con p ≥ 0,60 las señales se concentran en algunos meses (en 2026-01 y 2026-04/05/06 no hubo ninguna: la
calibración de esos modelos no llegó a 0,60). De los meses con ≥ 100 señales, todos quedaron entre 57 y
66 %. Hipótesis nueva, sin decidir nada aquí: Estudio 21.

**Verificación del «efecto cuarto de hora»:** en los Estudios 19 y 20 las velas alineadas al cuarto de hora
quedaron por debajo del total, pero la comparación mezclaba dos cosas. Con pago 87 % el filtro de EV admite
señales de menor probabilidad. Con la misma regla, la diferencia casi desaparece:

| Regla | Periodo | Alineadas | Resto |
|---|---|---|---|
| pago 85 % | 2025-09 → 2026-10 | 56,6 % (1 279) | 57,7 % (18 539) |
| pago 85 % | 2024-07 → 2025-08 | 56,6 % (1 702) | 56,9 % (24 353) |
| pago 87 % | 2024-07 → 2025-08 | 55,9 % | 56,0 % |

Conclusión: no hay un efecto especial del cuarto de hora. El modo `--cuarto 1` pierde sobre todo porque
tiene 15 veces menos señales, no porque esas velas sean peores.

## Estudio 21 — umbral de confianza p ≥ 0,60 con el modelo congelado (pre-registro, 2026-10-27, ANTES de ver datos posteriores al 2026-10-25)

**Origen:** Estudio 20, parte informativa. Con p ≥ 0,60 se obtuvo 62,53 % (2025-09 → 2026-10) y 59,71 %
(2024-07 → 2025-08), es decir, menos señales y más acierto en los dos periodos.

**Diseño:**
- **Modelo:** el congelado `BTCUSDT-anticipada-k50-L10-35b764` (SHA-256 5ebfa485…), sin reentrenar.
- **Etiqueta:** la de H16b (aviso en el segundo 50, clic a +10 s, contrato de 1 min).
- **Datos:** velas de 1 s y 1 min de Binance del 2026-10-26 al 2027-01-18, los mismos de la confirmación
  del Estudio 16.
- **Política:** EV ≥ 0,02 y además probabilidad de la dirección ≥ 0,60; pago 85 %, empate reembolsado.

**Hipótesis H21 (familia de 1, α = 0,05). Criterios (todos):**
1. ≥ 200 operaciones;
2. p binomial unilateral < 0,05 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. límite inferior del IC 95 % del EV (bootstrap por semanas) > 0.

**Declarado de antemano:** la meta del usuario (60 %) se informa aparte (¿acierto puntual ≥ 60 %? ¿límite
inferior ≥ 58 %?), pero **no** decide la hipótesis.

**Solo informativo:** modo cuarto de hora con pago 87 % (muestra demasiado pequeña para decidir) y
latencias 0 / 5 / 15 s.

**Consecuencia:** la demo gana la opción `--umbral 0.60` desde ya, **solo como práctica**. Si H21 pasa, el
umbral queda como la forma recomendada de usar la demo.

## Estudio 22 — estrategias de comunidades de binarias (Brasil, Rusia, Asia, bots de GitHub), desarmadas y probadas mes a mes (pre-registro, 2026-10-27, ANTES de calcular nada)

**Origen:** pedido del usuario (2026-10-27): investigar cómo «aciertan» los canales que envían señales todos
los días. Un investigador reunió las reglas exactas de unas 40 estrategias (catálogo local en
`data/raw/senales_terceros/CATALOGO_ESTRATEGIAS.md`; fuentes: blogs y PDF brasileños, repositorios de bots
de IQ Option / Pocket Option, smart-lab.ru, winoptionweb). Se descartan las que no tienen regla escrita,
las que repintan (ZigZag, fractales, Super Signals) y las de índices sintéticos.

**Convenciones:**
- color de la vela = signo de cierre − apertura (doji = 0);
- cuadrante = bloque de 5 velas de 1 min alineado al reloj (minuto % 5 = 0 → posición 1);
- entrada en la apertura de la vela objetivo y salida en su cierre (aproximación optimista: el clic real
  llega después);
- solo se opera si existen todas las velas que la regla mira y la vela objetivo es la inmediata siguiente
  en el reloj;
- se mide la **primera entrada (G0)**; el ciclo con gale se informa aparte.

**Instrumentos y datos:** BTC/USDT (Binance contado, 1 min); EUR/USD, GBP/USD, USD/JPY y XAU/USD (HistData,
1 min, precio bid).

**Periodo principal:** 2025-09-01 → 2026-10-25, mes a mes. **Informativo:** 2021-01 → 2025-08.

**Reglas (20 por instrumento; 100 hipótesis, Holm α = 0,05):**
- *Cuadrantes (1 min):*
  - MHI1, MHI2 y MHI3 minoría: posiciones 3–5 del cuadrante anterior → contra la mayoría en la posición
    1 / 2 / 3;
  - MHI1, MHI2 y MHI3 mayoría: a favor;
  - Milhão mayoría y minoría: las 5 velas del cuadrante anterior → posición 1;
  - Vituxo mayoría: posiciones 1–3 del anterior → posición 3;
  - Torres Gêmeas: posición 5 = color de la 1 del mismo cuadrante;
  - Três Vizinhos: posición 4 = color de la 3;
  - Padrão 23: posición 2 = color de la 1;
  - Melhor de 3: mayoría de las posiciones 2–4 del anterior → posición 3;
  - 3x1: minoría de las posiciones 1–3 → posición 5;
  - C3: posición 1 = color de la posición 1 del anterior;
  - Moonwalker: posición 1 = opuesto de la posición 3 del anterior;
  - «3 velas» de Bullex: en la posición 1, si las 3 velas anteriores son iguales → contra.
- *Indicadores (1 min, se evalúa la vela siguiente a la señal):*
  - SMA3/SMA8 + 3 cierres seguidos (bot de Pocket Option);
  - EMA20/EMA50 + RSI14 con zona neutra y filtro de rango (bot de Pocket Option);
  - EMA5/EMA20 + RSI14 > 50 (guías de Quotex).

Si alguna vela mirada es doji, no se opera.

**Hipótesis aparte (3 por instrumento, en la misma familia de Holm, que queda en 115):**
- Bollinger (20, 2) con reversión, vencimiento 3 min, solo 21–24 UTC (smart-lab);
- catalogación por horario (D = 10 días, horarios con ≥ 80 % de un color → al día siguiente);
- Turn Over: vela de 15 min de `:45` → contra en la de `:00`, vencimiento 15 min.

**Criterio para que una regla «funcione» (todos):**
1. ≥ 300 operaciones en el periodo principal;
2. acierto G0 (sin dojis) con p de Holm < 0,05 frente a 54,05 % (pago 85 %);
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 60 % de los meses.

**Solo informativo:**
- acierto con doji contado como pérdida;
- ciclo con 2 gales (apuestas 1 / 2,18 / 4,74) y su EV;
- placebo con la misma regla desplazada 1–4 minutos (sin alineación al reloj);
- el periodo 2021–2025.

**Expectativa declarada:** ~50 % en todas. Los catálogos de estas comunidades reconocen que sus patrones
dan cerca del 50 % a largo plazo. Si alguna mayoría de BTC supera el 50 %, se esperará que lo explique la
continuación ya conocida (`clpos`, Estudio 16), no la posición en el reloj.

**Consecuencia:** lo que pase se tratará como hipótesis nueva solo para datos posteriores al 2026-10-25,
con pre-registro propio. Lo que no pase se documenta en docs/06 como desarmado.

## Estudio 23 — auditoría de canales de señales de Telegram con precios reales (pre-registro, 2026-10-27, ANTES de cruzar ninguna señal con precios)

**Origen:** pedido del usuario: «ingresa a una plataforma donde envíen trading todos los días, busca su lógica,
su patrón». Un investigador leyó, sin cuenta, las vistas web públicas de unos 70 canales de Telegram
(`t.me/s/<canal>`) y extrajo 55 887 señales a CSV (`data/raw/senales_terceros/`; informe en `INFORME.md` de
esa carpeta). Las 33 186 que no son OTC se pueden cruzar con precios reales.

**Qué se mide:** si las señales, tal como se publicaron **antes** de la hora de entrada, aciertan más que el
azar y más que el equilibrio con pago del 85 %.

**Reglas de lectura (fijas):**
- **Zona horaria:**
  - la declarada por el canal;
  - si no la declara y es brasileño: UTC−3 (Brasil no tiene horario de verano desde 2019);
  - si no: la que el investigador anotó como inferida.
- **Fecha de entrada:**
  - si el texto trae la fecha completa, se usa esa;
  - si trae día/mes sin año, se toma el año que deja la fecha más cerca de la publicación;
  - si trae solo la hora, se toma la primera vez que llega esa hora local **después** de la publicación.
- **Solo cuentan las señales publicadas antes de la hora de entrada.** Las publicadas después (resultados
  «a posteriori») se excluyen y se cuentan aparte.
- **binomo_vip_ind** («Entry time: Now»): entrada al inicio del minuto siguiente a la publicación,
  vencimiento 5 min.
- **Resultado:** precio de apertura de la vela de 1 min de la hora de entrada contra el cierre de la última
  vela del vencimiento (HistData, bid, 1 min). Cuenta como empate si es igual. Se exige que existan las
  velas de inicio y de fin.
- **Pares:** los que HistData publica. Solo se mide la primera entrada (G0). El gale se informa aparte.

**Hipótesis:** una por canal con ≥ 300 señales verificables (Holm sobre los canales). Para cada canal:
- **H23-azar:** acierto G0 > 50 % (p de Holm < 0,05);
- **H23-rentable:** límite inferior de Wilson 95 % > 54,05 %.

**Informativo:**
- acierto declarado por el canal frente al medido en las mismas señales: ¿cuántas marcan «WIN» cuando el
  precio dice pérdida?
- acierto con otras zonas horarias (de −5 a +1 h respecto de la usada), como control: si el canal dice la
  verdad sobre su hora, el máximo debería caer en la hora usada;
- canales con menos de 300 señales.

**Expectativa declarada:** ~50 % en todos. El acierto que publican sale de la martingala (G1/G2) y de
editar los resultados.

**Nota de implementación (2026-10-27, antes de cruzar precios):**
- si una señal no trae vencimiento, se usa el vencimiento más frecuente que declara ese mismo canal
  (afecta sobre todo a VIPBinary_signals: 894 de 943 sin vencimiento, listas en marcas de 5 min; los 49 que
  lo declaran dicen 5 min);
- los pares sin datos en HistData (cripto de Quotex, CHFNZD) se cuentan como no verificables.

**Resultado del Estudio 22 (commit de la corrección del ítem 42, aplicado mecánicamente; `results/estudio22/resultado.json`).**
Periodo 2025-09 → 2026-10, 5 instrumentos, 115 hipótesis: **ninguna pasa** (todas con p de Holm = 1).

| Familia | Reglas × instrumentos | Operaciones | Acierto G0 (mín. / mediana / máx.) | 2021–2025 (mediana) | Ciclo con 2 gales |
|---|---|---|---|---|---|
| Cuadrantes (MHI, Milhão, Torres, Padrão 23, C3…) | 85 | 6,57 millones | 48,9 / **50,0** / 51,3 % | 50,0 % | acierta 84,5–88,8 %, **EV −0,13 a −0,51** |
| Placebo (las mismas reglas sin alinear al reloj) | — | — | mediana 50,0 % | — | — |
| Indicadores de bots (SMA3/8, EMA20/50+RSI, EMA5/20+RSI) | 15 | 978 418 | 47,6 / 48,9 / 50,0 % | 48,9 % | EV −0,24 a −0,54 |
| Catalogación por horario (≥ 80 % en 10 días → día siguiente) | 5 | 195 307 | 50,0 / 51,1 / 51,5 % | 51,1 % | EV −0,19 a −0,45 |
| Turn Over (15 min) | 5 | 37 241 | 51,1 / 51,6 / 52,4 % | 51,9 % | — |
| Bollinger con reversión, 3 min, 21–24 UTC | 5 | 16 098 | 53,3 / 54,6 / **55,6 %** (GBP/USD) | 54,7 % | — |

**Lectura:**
- La posición en el reloj no aporta nada: las reglas alineadas y el placebo dan lo mismo (50,0 %).
- El «85–89 %» que anuncian sale del gale, y con gale se pierde entre 13 y 51 centavos por ciclo.
- La catalogación elige horarios que acertaron ≥ 80 % en 10 días; al día siguiente aciertan ~51 %.
- **Única pieza con información:** la reversión nocturna de Bollinger en divisas (54,6–55,6 % en 2025–2026 y
  54,7–57,6 % en 2021–2025). Pero:
  - con el empate contado como pérdida (contrato digital) baja a 51,5–52,8 %;
  - los datos son solo bid y a esas horas el diferencial del bróker es mayor;
  - se debilita (GBP/USD: 57,6 % → 55,6 %).

  Queda como candidata (P10 en docs/08). Solo se probaría con un pre-registro propio, datos nuevos y el pago
  y la regla de empate reales del intermediario a esas horas.

## Estudio 24 — ¿ETH o BTC/USDC se adelantan unos segundos a BTC/USDT? (pre-registro, 2026-10-27, ANTES de descargar sus velas de 1 s)

**Origen:** informe de microestructura del 2026-10-27 (local, `data/raw/senales_terceros/MICROESTRUCTURA.md`):
- entre mercados de cripto, el que lidera explica parte del retorno del rezagado en segundos (Albers y
  otros, 2021);
- el régimen de comisiones decide qué par de BTC lidera dentro de Binance.

El Estudio 3 miró ETH y el perpetuo a escala de minutos, sin resultado. Aquí se mira **dentro del minuto,
hasta el segundo 49**, que es lo que el aviso del segundo 50 puede usar.

**Variables nuevas** (último precio antes de t + 50 s, igual que el Estudio 16; normalizadas con la
volatilidad de 60 min de BTC de la vela anterior):
- **ETH/USDT:** retornos de 5, 10 y 20 s, y su diferencia con los de BTC/USDT en esas mismas ventanas;
- **BTC/USDC:** diferencia de precio con BTC/USDT (en pb) en el segundo 49, su cambio en 10 s, y la
  diferencia de retornos de 10 s.

**Hipótesis (Bonferroni α = 0,025):**
- **H24a:** H16b + variables de ETH;
- **H24b:** H16b + variables de BTC/USDC.

**Diseño:**
- el mismo GBM, la misma semilla, la etiqueta de H16b (clic +10 s) y la política (EV ≥ 0,02, pago 85 %);
- repetición mensual con 12 meses de entrenamiento (Estudio 20);
- **desarrollo:** 2024-07 → 2025-08;
- **verificación:** 2025-09 → 2026-10-25.

**Criterios (cada hipótesis, todos):**
1. desarrollo: mejora media del log-loss por minuto > 0, con límite inferior del IC 97,5 % (bootstrap por
   semanas) > 0;
2. desarrollo: EV por operación de la política ≥ el del modelo base;
3. verificación: mejora del log-loss > 0 (puntual) y EV ≥ el del base.

**Consecuencia:** si pasa, un modelo congelado nuevo con los 12 meses hasta el 2026-10-25 y confirmación
con 2026-10-26 → 2027-01-18. Si no pasa, se documenta como desarmado.

**Resultado del Estudio 23 (aplicado mecánicamente; `results/estudio23/resultado.json`).** La primera ejecución
se detuvo antes de calcular nada (zona horaria vacía leída como NaN); se corrigió la comprobación.

| Canal (idioma, años) | Señales verificables publicadas antes de la entrada | Acierto G0 medido [lím. inf.] | Declarado por el canal: G0 / con gale | «WIN» declarado que el mercado real contradice |
|---|---|---|---|---|
| gotraderssinaisfree (pt, 2024–26) | 8 295 | 49,3 % [48,2] | sin resultados | — |
| mestredossinaiis (pt, 2021–23) | 6 316 | 50,9 % [49,6] | 58,8 % / 86,8 % | 36,5 % |
| Tigers_Iqoption, lista gratuita (pt, 2022–23) | 1 916 | 49,2 % [46,9] | 54,2 % / 83,5 % | 51,0 % |
| Unidos (pt, 2025–26) | 1 397 | 51,5 % [48,9] | sin resultados | — |
| sinaisOBM5 (pt, 2020) | 1 190 | 49,5 % [46,7] | 53,9 % / 90,0 % | 48,4 % |
| sinaistraderpassos (pt, 2021–22) | 859 | 48,5 % [45,2] | 49,9 % / 91,4 % | 19,7 % |
| binomo_vip_ind (en, 2025) | 320 | 45,3 % [40,0] | sin resultados | — |
| PocketSignalsM1, fxrealbot, quotexsignals2814 | 89–117 cada uno | 42,7–53,2 % | 49–68 % / 77–99 % | 36–48 % |

**Veredicto:**
- **H23-azar y H23-rentable: ningún canal pasa** (8 evaluados, Holm).
- Con 20 000 señales publicadas por adelantado, el acierto real de la primera entrada es el de una moneda
  al aire (49–51 %). El «83–99 %» que anuncian es el acierto **con gale**.
- **Control de zona horaria:** con cualquier desplazamiento de −5 a +1 h, todos siguen entre 47 y 53 %. No
  hay una hora «correcta» escondida que les dé ventaja.
- Tigers publicó 9 372 de sus 11 472 señales **después** de la hora de entrada (las «premium», ya con
  resultado); VIPBinary, 875 de 943.
- Los «WIN» declarados no concuerdan con el mercado real en el 20–51 % de los casos. Los precios de otra
  fuente explican parte del desacuerdo; un 50 % equivale a no tener relación con el mercado (precio propio
  del bróker o resultado inventado).

**Resultado del Estudio 24 (commit e09beae, aplicado mecánicamente; `results/estudio24/resultado.json`).**

| Hipótesis | Periodo | Mejora del log-loss [IC 97,5 %] | Acierto base → nuevo | EV base → nuevo | Veredicto |
|---|---|---|---|---|---|
| H24a (+ ETH) | desarrollo | +0,00024 [+0,00011; +0,00037] | 56,92 → 56,59 % | +0,049 → +0,043 | **no pasa** (criterios 2 y 4) |
| | verificación | +0,00030 [+0,00018; +0,00042] | 57,83 → 57,05 % | +0,063 → +0,050 | |
| H24b (+ BTC/USDC) | desarrollo | +0,00007 [−0,00003; +0,00015] | 56,92 → 56,87 % | +0,049 → +0,048 | **no pasa** |
| | verificación | +0,00015 [+0,00004; +0,00025] | 57,83 → 57,09 % | +0,063 → +0,051 | |

**Lectura:** los segundos de ETH contienen un poco de información (el log-loss mejora en los dos periodos),
pero repartida en minutos de poca confianza. Al sumarla, el modelo dispara más señales mediocres y el acierto
de la política baja. El base del Estudio 24 (57,83 %) difiere del Estudio 20 (57,60 %) porque exige que
existan también los segundos de ETH y de USDC (misma muestra para comparar).

## Estudio 25 — reversión nocturna (Bollinger 20, 2; 3 min; 21–24 UTC) en 24 pares que el Estudio 22 no usó (pre-registro, 2026-10-27, ANTES de calcularla en esos pares)

**Origen:** en el Estudio 22, la única regla de comunidades con algo de información fue la de smart-lab.ru:
- 54,6–55,6 % en EUR/USD, GBP/USD y USD/JPY (2025–2026), sin pasar la corrección de Holm;
- 54,7–57,6 % en 2021–2025.

Para no reutilizar los mismos mercados, se prueba en pares distintos: es una réplica fuera de muestra
*entre mercados*.

**Pares (24, fijos):** AUDCAD, AUDCHF, AUDJPY, AUDNZD, AUDUSD, CADCHF, CADJPY, CHFJPY, EURAUD, EURCAD, EURCHF,
EURGBP, EURJPY, EURNZD, GBPAUD, GBPCAD, GBPCHF, GBPJPY, GBPNZD, NZDCAD, NZDCHF, NZDJPY, NZDUSD, USDCAD. Datos:
HistData de 1 min, bid (`data/raw/histdata_pares/`).

**Periodo:** 2025-09-01 → 2026-10-23 (último día publicado).

**Regla (idéntica al código del Estudio 22, `indicator_rules`):**
- al cierre de la vela s, entre las 21:00 y las 23:59 UTC: si el cierre está por encima de la banda superior
  de Bollinger (20, 2) → PUT; si está por debajo de la inferior → CALL;
- resultado = apertura de s + 1 contra cierre de s + 3;
- una operación a la vez.

**Hipótesis H25 (una, con todos los pares juntos). Criterios (todos):**
1. ≥ 1 000 operaciones;
2. p binomial unilateral < 0,05 frente a 54,05 % (pago 85 %, empate reembolsado);
3. límite inferior de Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 60 % de los meses.

**Declarado de antemano:**
- se informa también el acierto con el empate contado como pérdida (contrato digital) y por par, por hora y
  frente al azar (50 %);
- de noche, en pares poco líquidos, los precios bid de HistData pueden tener ruido de cotización que imita
  la reversión. Por eso, aunque pase, **solo** se llevaría a la demo tras comprobar en la plataforma el pago
  y la regla de empate a esas horas (16:00–19:00 en Bogotá).

**Expectativa:** si el efecto es real, ~54–55 %; es decir, cerca del equilibrio y probablemente **no** rentable.

**Resultado de H25 (commit del código del Estudio 25, aplicado mecánicamente; `results/estudio25/resultado.json`).**
Con los criterios pre-registrados, **PASA**:
- 71 438 operaciones; acierto **57,30 %** [56,93 %]; EV +0,058;
- los 14 meses con EV > 0;
- con el empate contado como pérdida, 54,96 %.

**Pero la advertencia declarada de antemano se confirma.** Las dos direcciones no se comportan igual:

| Momento | CALL (precio bajo la banda) | PUT (sobre la banda) |
|---|---|---|
| 0–5 min después de las 17:00 de Nueva York (cierre diario, el diferencial se abre) | **75,5 %** | 62,0 % |
| 5 min antes de las 17:00 | 21,9 % | 79,5 % |
| A más de 60 min del cierre | **61,6 %** | 53,2 % |

Una reversión de verdad sería parecida en las dos direcciones. Con precios solo bid, cuando el diferencial
se abre el bid «cae» sin que el mercado se mueva, y vuelve cuando se cierra. Eso regala aciertos a las CALL.
**No se puede declarar operable** con datos bid.

### Verificación de H25 con precio medio (pre-registro, 2026-10-27, ANTES de descargar los ticks)

- **Datos:** ticks de HistData (bid y ask) de los 6 pares con mayor acierto en H25 (EURGBP, EURCHF, EURAUD,
  GBPCAD, CHFJPY, EURJPY) y de los meses 2026-04 → 2026-09. Con ellos se construyen velas de 1 min con el
  **precio medio** (bid + ask) / 2; se usa el último tick de cada minuto.
- **Regla:** la misma de H25, sobre esas velas.
- **Criterio (todos):**
  1. acierto con precio medio > 54,05 % con límite de Wilson > 54,05 %;
  2. diferencia entre CALL y PUT < 5 puntos.

  Si no se cumple, H25 se declara **artefacto del precio bid** y P10 se descarta.
- **Informativo:** el mismo cálculo con el bid de los ticks, para comprobar que reproduce lo de las velas de
  HistData.

## Estudio 26 — aviso anticipado con umbral de confianza en otras monedas (pre-registro, 2026-10-27, ANTES de descargar sus velas de 1 s)

**Origen:**
- en BTC, filtrar por confianza (p ≥ 0,60) subió el acierto a 60–62 % (Estudio 20, informativo);
- en el Estudio 13 (modelo sin anticipación, entrada al cierre), XRP, SOL y DOGE mostraron el mismo patrón
  al exigir más EV (XRP 62,9 % con EV ≥ 0,12; SOL 61,7 %; DOGE 61,0 %), y ETH 58,1 %. BNB y ADA casi no
  tenían señales de alta confianza.

Elegir estas 4 monedas usa lo visto en el Estudio 13 (periodo 2022–2025); la prueba es en 2025-09 → 2026-10,
que el Estudio 13 no tocó.

**Monedas (fijas):** XRP/USDT, SOL/USDT, ETH/USDT y DOGE/USDT (Binance contado).

**Modelo:** la receta de H16b para cada moneda, sin cambiar nada:
- `FEATURES` de sus velas de 1 min y bloque parcial de sus velas de 1 s hasta el segundo 49;
- etiqueta: último precio antes de t + 60 s contra último precio antes de t + 120 s;
- GBM con la misma semilla;
- repetición mensual 2025-09 → 2026-10-25, con 12 meses de entrenamiento y 20 % de calibración (Estudio 20).

**Política:** EV ≥ 0,02 (pago 85 %) **y** probabilidad de la dirección ≥ 0,60.

**Hipótesis (una por moneda; Bonferroni α = 0,0125). Criterios (todos):**
1. ≥ 300 operaciones;
2. p binomial < 0,0125 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 60 % de los meses con operaciones;
5. **robustez contra el «rebote» del último precio:** en monedas de precio bajo, el último precio salta entre
   compra y venta. Con la etiqueta recalculada usando el **promedio de los 5 últimos cierres de 1 s** antes
   de t + 60 y de t + 120, el acierto en las mismas operaciones debe seguir > 54,05 %.

**Informativo:**
- todas las señales sin umbral;
- el tamaño relativo del tic de precio de cada moneda;
- un selector conjunto (cuántas señales al día suman las 4 monedas + BTC).

**Consecuencia:** lo que pase se confirmará con modelos congelados y datos posteriores al 2026-10-25 (nuevo
pre-registro). Solo demo.

**Nota de implementación (antes de descargar):** la etiqueta de H16b redondea con el tic de BTC (0,01 USD). En
cada moneda se usa su propio tic de Binance (XRP 0,0001; SOL 0,01; ETH 0,01; DOGE 0,00001). Con el de BTC,
casi todos los minutos de XRP y DOGE quedarían como empate.

**Resultado de la verificación con precio medio (`results/estudio25/verificacion_precio_medio.json`): PASA.**

| Precio | Operaciones | Acierto [lím. inf.] | Empate = pierde | CALL | PUT |
|---|---|---|---|---|---|
| **Medio** (ticks bid + ask) | 7 640 | **59,78 %** [58,66 %] | 58,08 % | 60,6 % | 59,0 % |
| Bid de los ticks | 7 500 | 59,96 % | 57,04 % | 62,0 % | 58,0 % |

**Lectura:**
- La asimetría se debía al bid; con precio medio, la reversión nocturna es simétrica y se mantiene.
- Hay dos límites:
  1. los 6 pares se eligieron por ser los mejores del Estudio 25 (sesgo de selección);
  2. se supuso entrada en la apertura exacta de la vela siguiente.

## Estudio 27 — reversión nocturna en divisas: operatividad con clic humano y los 24 pares (pre-registro, 2026-10-27, ANTES de descargar más ticks)

**Diseño:**
- **Datos:** ticks de HistData (precio medio) de los 24 pares del Estudio 25, 2026-04 → 2026-09.
- **Regla:** la de H25, con dos cambios:
  - la señal se conoce al cierre de la vela s (último tick antes de s + 60 s);
  - **la entrada es el precio medio del último tick antes de s + 60 s + L** (L = demora del clic), y el
    vencimiento es exactamente 3 min después de la entrada (último tick antes de entrada + 180 s).
- **Hipótesis (Bonferroni α = 0,025):**
  - **H27a:** L = 5 s;
  - **H27b:** L = 10 s.
- **Criterios (cada una, todos):**
  1. ≥ 1 000 operaciones;
  2. p < 0,025 frente a 54,05 % (pago 85 %);
  3. Wilson 95 % > 54,05 %;
  4. EV > 0 en ≥ 5 de los 6 meses;
  5. CALL y PUT a menos de 5 puntos entre sí.
- **Informativo:**
  - L = 0, 2, 20 y 30 s;
  - el acierto con el empate contado como pérdida;
  - los equilibrios con pagos del 70, 75 y 80 % (57,1 %; 57,1 %; 55,6 %) — de noche las plataformas suelen
    bajar el pago;
  - acierto por par y por hora.
- **Confirmación (si pasa):** las mismas reglas con los ticks de 2026-10-26 → 2027-01-18 en cuanto HistData los
  publique (sale cada mes), una sola vez.
- **Condición para la demo:** que el usuario confirme en su plataforma que esos pares se pueden operar sin
  OTC entre las 16:00 y las 19:00 de Bogotá, con vencimiento de 3 min, y el pago real a esas horas.

**Nota de implementación del Estudio 27 (antes de descargar):** un precio de entrada o de salida solo vale si su
último tick tiene ≤ 60 s de antigüedad; si no, la operación no se cuenta. La señal se calcula con velas de 1 min
del precio medio, construidas con los mismos ticks.

**Resultado del Estudio 26 (commit 83d434e, aplicado mecánicamente; `results/estudio26/resultado.json`).**

| Moneda | Con p ≥ 0,60: operaciones | Acierto [lím. inf.] | Etiqueta robusta | Sin umbral (robusta) | Veredicto |
|---|---|---|---|---|---|
| **ETH/USDT** | 653 | **58,80 %** [54,97 %], EV +0,087 | 60,62 % | 54,80 % (55,13 %) | **PASA** |
| XRP/USDT | 0 (la probabilidad máxima fue 0,576) | — | — | 54,75 % (54,43 %) | no pasa |
| SOL/USDT | 0 (máx. 0,578) | — | — | 54,35 % (54,54 %) | no pasa |
| DOGE/USDT | 0 | — | — | 51,44 % (51,80 %) | no pasa |

**Lectura:**
- Con aviso anticipado y clic a +10 s, el modelo de las otras monedas casi nunca está seguro. El 62,9 % de XRP
  del Estudio 13 venía de entrar justo al cierre.
- ETH pasa, pero con pocas señales (653 en 14 meses). Hipótesis para confirmar con modelo congelado y datos
  nuevos.

**Resultado del Estudio 27 (commit 8d2abb4, aplicado mecánicamente; `results/estudio27/resultado.json`).**
24 pares, precio medio de ticks, 2026-04 → 2026-09:

| Hipótesis | Clic | Operaciones | Acierto [lím. inf.] | Empate = pierde | CALL / PUT | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|---|---|---|
| **H27a** | +5 s | 31 195 | **57,58 %** [57,03 %] | 56,15 % | 58,1 / 57,1 % | 6 de 6 | **PASA** |
| **H27b** | +10 s | 31 166 | **57,17 %** [56,61 %] | 55,71 % | 57,6 / 56,7 % | 6 de 6 | **PASA** |

**Informativo:**
- **Por clic:** 0 s 59,5 %; 2 s 58,0 %; 20 s 56,4 %; 30 s 55,8 %.
- **Por hora (UTC, clic +10 s):** 21 h 54,2 %; **22 h 62,3 %**; 23 h 54,8 %. De abril a septiembre (horario de
  verano de Nueva York), 22 UTC es una hora después del cierre de Nueva York, es decir, las 17:00 de Bogotá.
- **Mejores pares (clic +10 s):** GBPCAD 61,9 %, EURCHF 61,4 %, CADCHF 60,1 %, EURAUD y EURGBP 59,0 %.
  Peores: NZDUSD 53,3 %, NZDCAD 54,4 %.
- **Equilibrio según el pago:** 80 % → 55,6 % (rentable); 75 % → 57,1 % (justo); 70 % → 58,8 % (no).
- **Señales:** unas 200 por día hábil entre los 24 pares.

**Advertencias:**
- Es precio medio de HistData. Cada plataforma tiene su propio precio, y de noche su diferencial y su pago
  pueden ser peores.
- La confirmación con datos posteriores al 2026-10-25 sigue pendiente (pre-registrada).

## Estudio 28 — reversión nocturna en invierno: ¿ventana UTC fija o anclada al cierre de Nueva York? (pre-registro, 2026-10-28, ANTES de descargar los ticks de invierno)

**Origen:**
- el Estudio 27 usó solo meses de verano en Nueva York (2026-04 → 2026-09), con el cierre de las 17:00 NY a
  las 21:00 UTC. La mejor hora fue la siguiente al cierre (22 UTC, 62,3 %);
- el 2026-11-01 Nueva York pasa a invierno: el cierre queda a las 22:00 UTC (las 17:00 en Bogotá). La
  bitácora del 2026-10-28 propuso esta prueba.

**Datos:** ticks de HistData (precio medio), los mismos 24 pares, **2025-11 → 2026-03** (invierno en Nueva
York; meses no usados en los Estudios 25 y 27 con precio medio).

**Regla:** la de H27b (Bollinger 20, 2 sobre velas de 1 min de precio medio; reversión; clic a +10 s;
vencimiento 3 min desde la entrada; una operación a la vez). Solo cambia la ventana horaria.

**Hipótesis (Bonferroni α = 0,025):**
- **H28a:** ventana fija de 21:00 a 23:59 UTC (la actual);
- **H28b:** ventana anclada a Nueva York: de las 17:00 a las 19:59 hora de Nueva York (en invierno, de 22:00 a
  00:59 UTC).

**Criterios (cada una, todos):**
1. ≥ 1 000 operaciones;
2. p < 0,025 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 4 de los 5 meses;
5. CALL y PUT a menos de 5 puntos.

**Regla de decisión para el modo en vivo (fijada ahora):**
- si H28b pasa y su acierto es ≥ al de H28a, la ventana se ancla a Nueva York: **de las 17:00 a las 19:59
  NY**, es decir, de 16:00 a 18:59 en Bogotá en verano y de 17:00 a 19:59 en invierno;
- si no, se mantiene la ventana UTC.

**Informativo:**
- acierto por hora contada desde el cierre de Nueva York, juntando verano e invierno;
- acierto según la volatilidad del día anterior (por encima o por debajo de la mediana), de la bitácora.

**Resultado del Estudio 28 (commit 9592c1a, aplicado mecánicamente; `results/estudio28/resultado.json`).**
Invierno de Nueva York, 2025-11 → 2026-03, 24 pares, precio medio de ticks, clic a +10 s:

| Hipótesis | Ventana | Operaciones | Acierto [lím. inf.] | CALL / PUT | Veredicto |
|---|---|---|---|---|---|
| **H28a** | 21:00–23:59 UTC (fija) | 26 832 | **56,79 %** [56,20 %] | 57,3 / 56,3 % | **PASA** |
| H28b | 17:00–19:59 Nueva York | 28 472 | 55,37 % [54,79 %] | 55,1 / 55,7 % | pasa |

**Decisión según la regla fijada de antemano:** la ventana del modo en vivo queda en **UTC fija**, es decir, de
**16:00 a 18:59 en Bogotá todo el año** (Colombia no cambia de hora). La ventaja **no** se ancla al cierre de
Nueva York.

**Informativo:**
- **Acierto por hora:**

  | Estación | 17:00 NY | 18:00 NY | 19:00 NY |
  |---|---|---|---|
  | Invierno | 61,7 % (= 22 UTC) | 54,5 % | 51,4 % |
  | Verano | 54,5 % | 62,3 % (= 22 UTC) | 54,8 % |

  La hora fuerte es **siempre las 22 UTC (17:00 en Bogotá)**, en las dos estaciones.
- **Volatilidad del día anterior:** alta 55,1 %, baja 55,6 %; no cambia nada.

## Estudio 29 — confirmación de la reversión nocturna con datos nuevos (pre-registro, 2026-10-28, ANTES de existir los datos)

**Datos:** ticks de HistData (precio medio) del 2026-10-26 al 2027-01-18, de los 24 pares, en cuanto HistData
los publique (sale cada mes). Se evalúa **una sola vez**, con todo el periodo.

**Regla:** la de H27b/H28a (ventana 21–24 UTC, Bollinger 20, 2; reversión; clic a +10 s; vencimiento de 3 min;
una operación a la vez). El código es `study28.pair_rows` con la ventana H28a, sin cambios.

**Hipótesis (Holm α = 0,05):**
- **H29a:** toda la ventana 21:00–23:59 UTC;
- **H29b:** solo la hora fuerte, 22:00–22:59 UTC. Es *post hoc* de los Estudios 27 y 28, por eso se confirma aquí.

**Criterios (cada una):**
1. ≥ 500 operaciones (H29a) / ≥ 200 (H29b);
2. p de Holm < 0,05 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. CALL y PUT a menos de 5 puntos.

**Informativo:** el diario del modo en vivo (precio de Deriv y clics reales del usuario) se compara con lo que
dice HistData para los mismos minutos.

## Estudio 30 — ¿la reversión de Bollinger funciona en otras horas y en otros mercados? (pre-registro, 2026-10-28, ANTES de calcularla fuera de 21–24 UTC y fuera de divisas)

**Origen:** el pedido del usuario de buscar más piezas como la reversión nocturna (Estudios 27 y 28). Hasta
hoy la regla solo se midió entre las 21 y las 24 UTC. Su explicación (poca liquidez) predice que podría
aparecer en otras horas tranquilas (sesión asiática) y no en las horas de mucha liquidez (Londres y Nueva
York).

**Regla:** la de H27b/H28a, sin cambiar nada salvo la hora y el mercado: Bollinger (20, 2) sobre velas de 1 min
de precio medio, reversión, clic a +10 s, vencimiento 3 min desde la entrada, una operación a la vez por
instrumento.

**Datos:**
- **Divisas:** ticks de HistData ya descargados (24 pares, 2025-11 → 2026-09, 11 meses).
- **Otros mercados:** ticks de HistData de oro (XAUUSD) y S&P 500 (SPXUSD) del mismo periodo, y BTC/USDT
  con velas de 1 s de Binance (precio negociado; el tic de BTC es despreciable).

**Hipótesis (24, Holm α = 0,05):**
- **Parte A (21):** divisas, cada hora UTC de 0 a 20 por separado (la hora de entrada t de la operación);
- **Parte B (3):** ventana nocturna 21–24 UTC en XAUUSD, SPXUSD y BTCUSDT.

**Criterios (cada una, todos):**
1. ≥ 1 000 operaciones (Parte B: ≥ 500);
2. p de Holm < 0,05 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 8 de los 11 meses;
5. CALL y PUT a menos de 5 puntos.

**Expectativa declarada:**
- horas de Asia (0–6 UTC): acierto parecido a la noche (~55 %);
- horas de Londres y Nueva York (7–20 UTC): ~50 %, o incluso continuación (< 50 %);
- oro y S&P: dudoso; BTC: sin reversión (su ventaja conocida es la continuación).

**Consecuencia:** lo que pase se confirma con datos posteriores al 2026-10-25 (se suma a la familia del Estudio 29)
antes de llevarlo al modo en vivo.

**Resultado del Estudio 30 (aplicado mecánicamente; `results/estudio30/resultado.json`): ninguna de las 24 pasa.**

| Grupo | Acierto (clic +10 s, 3 min) | Comentario |
|---|---|---|
| Divisas 0–6 UTC (Asia) | 51,9–53,4 % | por debajo del equilibrio, contra lo esperado |
| Divisas 7–15 UTC (Londres / Nueva York) | 50,9–52,9 % | casi azar |
| Divisas 16–20 UTC | 52,6–53,6 % | por debajo del equilibrio |
| Oro (21–24 UTC) | 52,4 % (1 680 ops) | asimétrico (CALL 55,7 / PUT 49,3) |
| S&P 500 (21–24 UTC) | 48,0 % (924 ops) | no |
| BTC/USDT (21–24 UTC) | 54,5 % (3 800 ops), Wilson 52,9 % | no supera el equilibrio |

**Lectura:**
- En divisas hay una reversión pequeña a toda hora (51–54 %), pero solo entre las 21 y las 24 UTC llega a ser
  rentable (56,8–57,2 %, Estudios 27 y 28).
- La ventaja no es «cualquier hora tranquila»: está en ese tramo concreto, el que sigue al cierre de Nueva York,
  justo cuando abren Sídney y Wellington.
- El modo en vivo se queda como está.

## Estudio 31 — solidez de los parámetros de la reversión nocturna (pre-registro, 2026-10-28, SOLO INFORMATIVO, ANTES de calcularlo)

**Pregunta:** ¿el 57 % depende de los números exactos (20 velas, 2 desviaciones, 3 min) o se sostiene con
valores vecinos? Si solo funciona en un punto aislado, es frágil (sobreajuste); si funciona en una zona, es más
creíble.

**Rejilla:** ventana 21–24 UTC, 24 pares, precio medio de ticks, clic a +10 s, 2025-11 → 2026-09:
- velas de la banda N ∈ {14, 20, 30};
- desviaciones K ∈ {1,5; 2; 2,5};
- vencimiento ∈ {1, 2, 3, 5} min.

En total, 36 combinaciones.

**Criterio de solidez, declarado de antemano:** la regla se considera sólida si las combinaciones vecinas de
(20, 2, 3 min) —cambiando un solo parámetro a la vez: N 14 y 30, K 1,5 y 2,5, vencimiento 2 y 5 min; 6 en total (corregido antes de ejecutar: decía 5 por un error de conteo)— superan todas el 54,05 % (Wilson, límite
inferior > 52 %).

**No decide nada:** el modo en vivo **no** cambia de parámetros por este estudio. Un cambio exigiría
pre-registrarlo y confirmarlo con datos nuevos.

**Resultado del Estudio 31 (`results/estudio31/resultado.json`): SÓLIDA.**

Acierto con clic a +10 s, 21–24 UTC, 24 pares, 2025-11 → 2026-09:

| N, K | 1 min | 2 min | 3 min | 5 min |
|---|---|---|---|---|
| 14, 1,5 | 53,7 % | 54,5 % | 55,3 % | 55,6 % |
| 14, 2,0 | 54,6 % | 55,5 % | 56,0 % | 56,9 % |
| 14, 2,5 | 55,9 % | 57,1 % | 57,7 % | 58,5 % |
| 20, 1,5 | 54,1 % | 55,0 % | 55,9 % | 56,9 % |
| **20, 2,0 (regla actual)** | 54,9 % | 56,0 % | **57,0 %** | 57,8 % |
| 20, 2,5 | 56,4 % | 58,0 % | 59,0 % | 59,8 % |
| 30, 1,5 | 54,3 % | 55,6 % | 56,5 % | 57,7 % |
| 30, 2,0 | 55,4 % | 56,9 % | 58,3 % | 59,5 % |
| 30, 2,5 | 57,1 % | 58,7 % | 60,4 % | **61,3 %** (21 302 ops) |

**Lectura:**
- La superficie es suave y monótona: más acierto con bandas más anchas (precio más extremo), más velas y
  vencimiento más largo.
- No hay picos aislados, que serían la huella del sobreajuste; las 6 vecinas pasan.
- La de 1 min con la regla actual queda justo en el equilibrio (54,9 %): no conviene usar 1 min.
- Elegir ahora la mejor casilla sería *post hoc*. Por eso se añade a la confirmación como hipótesis aparte.

**Enmienda al Estudio 29 (2026-10-28, ANTES de existir los datos de confirmación):**
- se añade **H29c**: N = 30, K = 2,5, vencimiento 5 min (la casilla más fuerte del Estudio 31), con ≥ 200
  operaciones;
- la familia del Estudio 29 pasa a 3 hipótesis (Holm).

El modo en vivo ofrecerá esta variante como **opción de práctica** (útil también si la plataforma solo deja
vencimientos de 5 min), sin dejar de usar la regla actual por defecto.

## Estudio 32 — auditoría PROSPECTIVA de canales de señales (pre-registro, 2026-10-29, ANTES de capturar ninguna señal nueva)

**Origen:** el usuario no cree que quienes «aciertan 60 % o más todos los días» tiren al azar. El Estudio 23
miró el pasado de 21 canales (49–51 % en la primera entrada), pero el pasado se puede editar o borrar. Aquí se
vigila **hacia adelante**: cada hora se guarda lo que publican los canales (`.github/workflows/vigilancia_canales.yml`,
`src/tradingbot/data/telegram_publico.py`), con la hora de Telegram y la nuestra, y cada día se cruza con precios
reales. Nadie puede corregir después lo que ya guardamos.

**Canales:** los de `config/canales_vigilados.txt`. La investigación diaria puede añadir más, pero cada canal
entra en la evaluación solo con las señales capturadas **después** de añadirlo.

**Lectura de señales (reglas fijas):**
- Cada línea del mensaje que contenga a la vez:
  - un par de divisas verificable en Deriv (los 25 `frx…`, escrito con o sin «/»);
  - una hora HH:MM;
  - una dirección: CALL / PUT / BUY / SELL / COMPRA / VENDA / VENTA / UP / DOWN, o los emojis 🟩 🟥 ⬆ ⬇ 🔼 🔽.
- **Vencimiento:** el marcado en la línea o en el mensaje (M1 / M5 / M15). Si no hay ninguno, la señal no es
  verificable.
- **Se excluyen** las líneas o los mensajes que digan «OTC».
- **Zona horaria:** la anotada para el canal en la lista. Sin zona, ninguna señal del canal es verificable.
- **Fecha de entrada:** la primera vez que llega esa hora local **después** de la publicación (regla del Estudio 23).
- **Resultado:** apertura de la vela de 1 min de la entrada frente al cierre de la última vela del vencimiento
  (velas de precio medio de la API pública de Deriv); empate si son iguales. Solo cuenta la primera entrada (G0);
  la martingala no se cuenta como acierto.

**Hipótesis (una por canal con ≥ 100 señales verificadas; Holm entre canales):**
- **H32-azar:** acierto G0 > 50 %;
- **H32-rentable:** límite inferior de Wilson 95 % > 54,05 % (pago 85 %).

**Evaluación formal:** una sola vez, el 2027-01-31, con las señales publicadas entre el 2026-10-29 y el 2027-01-25.
Antes de esa fecha solo se informan tablas descriptivas mensuales, sin veredicto.

**Si algún canal pasa:** se pre-registra un estudio para desarmar sus señales (horario, par, dirección frente
al movimiento reciente, posición en las bandas, etc.) y buscar qué dato usa.

**Nota sobre datos reservados:** auditar canales de terceros con precios posteriores al 2026-10-25 **no** evalúa
ninguna estrategia propia, así que se permite. Nunca se calculan aquí aciertos de los Estudios 12–29.

**Expectativa declarada:** ~50 % en todos, como en el Estudio 23.

## Estudio 33 — variables de «reloj» (cuarto de hora y hora de financiación) en el modelo de BTC 1 min (pre-registro, 2026-10-29, ANTES de calcularlas)

*Renumerado de 32 a 33 el mismo día, antes de ejecutar nada: el número 32 ya lo usaba la auditoría prospectiva de canales.*

**Origen:** bitácora del 2026-10-26 y del 2026-10-27 (propuesta repetida dos días, nunca probada):
- Kim y Hansen (preprint de 2026, futuros de cripto; https://arxiv.org/abs/2607.09426, **no se pudo leer el
  texto completo**, solo su resumen en la bitácora y en buscadores): el volumen, la volatilidad y la dependencia
  serial del flujo de órdenes y de los retornos se concentran en los minutos :00, :15, :30 y :45, sobre todo en
  sus primeros 10 s; según un resumen de prensa (https://cryptoslate.com/?p=559513, **no se pudo leer**: dominio
  bloqueado en este entorno), el efecto sigue al quitar las horas de financiación;
- Binance liquida la financiación de los perpetuos a las 00:00, 08:00 y 16:00 UTC.

El modelo actual ve la hora del día (`tod_sin`, `tod_cos`) y el día de la semana, pero **no** la posición del
minuto dentro del cuarto de hora ni la distancia a la financiación.

**Datos:** velas de 1 min del contado BTC/USDT de Binance (data.binance.vision, archivos mensuales), 2021-01 →
2026-09. Nada posterior al 2026-10-25.

**Modelo base (sin cambios):** el de los Estudios 7 y 13 — GBM con `FEATURES`, horizonte 1 min, entrada en la
apertura de la vela siguiente (d = 1), walk-forward trimestral con 12 meses de entrenamiento, 20 % de calibración
isotónica, misma semilla, política B (EV estimado ≥ 0,02; pago 85 %; empate reembolsado; probabilidad de empate
estimada de forma causal como en el Estudio 13).

**Bloque nuevo (8 variables, todas de calendario, calculadas sobre el minuto que se opera, t + 1):**
- `k_q15`: 1 si ese minuto empieza en :00, :15, :30 o :45;
- `k_m5`: 1 si empieza en un múltiplo de 5 que no es cuarto de hora;
- `k_ph15_sin`, `k_ph15_cos`: fase del minuto dentro del cuarto de hora (minuto mod 15);
- `k_hora0`: 1 si empieza en :00;
- `k_fund_min`: minutos hasta la próxima financiación (00/08/16 UTC), dividido por 480;
- `k_fund0`: 1 si el minuto empieza exactamente a una hora de financiación;
- `k_fund_post`: 1 si está entre 1 y 5 minutos después de una hora de financiación.

**Hipótesis única H33 (α = 0,05; una sola familia, sin más pruebas):** base + bloque de reloj mejora al base.

**Criterios (todos):**
1. **desarrollo** (prueba 2022-01 → 2025-08): mejora media del log-loss por minuto > 0, con límite inferior del IC
   95 % (bootstrap por semanas) > 0;
2. desarrollo: EV por operación de la política ≥ el del base;
3. **verificación** (prueba 2025-09 → 2026-09): mejora del log-loss > 0 (puntual) y EV ≥ el del base.

**Informativo (no decide):** acierto y número de operaciones del base y del nuevo en los minutos `k_q15` = 1 frente
al resto, y en las horas de financiación.

**Limitación declarada:** el modelo base entra en la apertura (sin demora). La ráfaga del cuarto de hora vive en
los primeros 10 s, que el aviso del segundo 50 con clic a +10 s (H16b) no puede aprovechar igual. Si H33 pasa, la
pieza se lleva a H16b solo con un estudio nuevo pre-registrado y confirmación con datos posteriores al
2026-10-25.

**Expectativa declarada:** SIN SEÑAL o mejora muy pequeña (< 0,5 puntos de acierto). Dos indicios en contra: la
hora del día ya está en el modelo, y en el Estudio 24 una mejora del log-loss no se tradujo en mejor política.

## Estudio 34 — réplica de la reversión nocturna en un año nunca usado (2024-09 → 2025-08) y filtro de diferencial (pre-registro, 2026-10-29, ANTES de descargar ningún tick de ese periodo)

**Origen:** diseño de la rutina autónoma del 2026-10-29 (docs/10, idea 5).
- **Réplica:** los Estudios 27, 28 y 31 usaron 2025-11 → 2026-09. El año 2024-09 → 2025-08 **nunca** se miró con
  precio medio en los 24 pares (el Estudio 22 usó solo 4 pares, con bid). Es una réplica limpia en otro periodo.
- **Filtro:** tras el cierre de Nueva York los brókeres abren el diferencial (CME 2026; BidFX vía financefeeds).
  Un diferencial abierto puede fabricar movimientos del precio medio que ninguna plataforma paga. Si la ventaja
  sobrevive solo con diferencial normal, es más creíble y más operable.

**Datos:** ticks de HistData (bid y ask) de los 24 pares de los Estudios 25 y 27, 2024-09 → 2025-08 (12 meses;
incluye inviernos y veranos de Nueva York).

**Reglas comunes (las de H27b/H28a):** Bollinger sobre velas de 1 min de precio medio, señal al cierre de la vela s,
reversión, ventana 21:00–23:59 UTC (hora de la vela de entrada), clic a +10 s, una operación a la vez por par,
precio válido si su último tick tiene ≤ 60 s.

**Hipótesis (Holm α = 0,05 entre las tres):**
- **H34a:** regla base (N = 20, K = 2, vencimiento 3 min);
- **H34b:** H34a solo cuando el diferencial (ask − bid) del último tick antes del cierre de s es ≤ 1,5 veces la
  mediana, en los 20 días hábiles anteriores del mismo par, de las medianas de diferencial por minuto entre las 21 y
  las 24 UTC (si no hay 20 días previos, la señal no cuenta);
- **H34c:** variante fuerte (N = 30, K = 2,5, vencimiento 5 min; H29c).

**Criterios (cada una, todos):**
1. ≥ 1 000 operaciones (H34c: ≥ 500);
2. p de Holm < 0,05 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 9 de los 12 meses;
5. CALL y PUT a menos de 5 puntos.

**Informativo:**
- acierto por decil del diferencial relativo;
- acierto a las 22 UTC;
- acierto con el empate contado como pérdida;
- acierto por par.

**Expectativa declarada:** H34a ~55–57 % si el efecto es estable; H34b igual o algo mayor; H34c ~58–60 %.
**Consecuencia:** si H34a no se replica, la reversión nocturna pierde credibilidad y la demo nocturna queda solo
como observación hasta la confirmación del Estudio 29.

## Estudio 35 — confirmación de ETH con aviso anticipado y umbral p ≥ 0,60 (pre-registro, 2026-10-29, ANTES de entrenar el modelo y de ver datos posteriores al 2026-10-25)

**Origen:** Estudio 26: ETH/USDT con la receta de H16b y p ≥ 0,60 pasó en 2025-09 → 2026-10 (653 operaciones,
58,80 % [54,97 %], etiqueta robusta 60,62 %). Docs/10, idea 2.

**Modelo congelado (se entrena UNA vez, hoy):**
- la receta exacta de `train_frozen` (BTC, Estudio 16), aplicada a ETH/USDT: 12 meses (2025-10-26 → 2026-10-25),
  último 20 % para calibrar con purga, GBM con semilla 2024;
- etiqueta de H16b: clic a +10 s, contrato de 1 min, tic de 0,01;
- archivo `config/modelos/ETHUSDT_senal_anticipada_k50.pkl`, con su SHA-256 en `config/senal_anticipada_eth.json`.

**Datos de confirmación:** velas de 1 s y 1 min de Binance del 2026-10-26 al 2027-01-18. Se evalúa una sola vez
después del 2027-01-18. El registro diario automático guarda las señales y su resultado cada día, con los aciertos
sellados igual que BTC.

**Hipótesis H35 (familia de 1, α = 0,05). Política:** EV ≥ 0,02 (pago 85 %) y probabilidad de la dirección ≥ 0,60.

**Criterios (todos):**
1. ≥ 100 operaciones;
2. p binomial unilateral < 0,05 frente a 54,05 %.

**Informativo:**
- Wilson 95 %;
- EV;
- la etiqueta robusta (promedio de los 5 últimos segundos);
- todas las señales sin umbral.

**Potencia declarada:** con ~140 operaciones esperadas (≈ 47 al mes en el Estudio 26), un acierto real del 59 % se
detectaría solo la mitad de las veces. Un «no pasa» por pocas operaciones no refuta la idea; se informaría como «sin
muestra suficiente» y se extendería con un pre-registro nuevo.

**Nota del Estudio 35 (2026-10-29, tras congelar el modelo, sin mirar ningún resultado).** Modelo
`ETHUSDT-anticipada-k50-L10-02b1e4` (SHA-256 71aaa021…; ajuste 412 346 y calibración 103 808 minutos; q = 0,0258).

En sus primeros 3 días (2026-10-26 → 28), la probabilidad máxima de la dirección fue 0,546–0,551. En el Estudio 26
llegaba a 0,61. Por eso no hubo ninguna señal con EV ≥ 0,02 y, menos aún, con p ≥ 0,60. Solo se miraron
probabilidades, no aciertos.

Si sigue así, H35 terminará con «sin muestra suficiente». No se cambia nada: el modelo y el umbral quedan
congelados.

## Estudio 36 — ¿la reversión nocturna existe en el precio de un bróker (Deriv)? (pre-registro, 2026-10-29, ANTES de descargar velas históricas de Deriv)

**Origen:** docs/10, idea 7. Los Estudios 25–31 midieron con precios de HistData. Una plataforma de binarias liquida
con su propio precio. Deriv es un bróker con API pública: si la ventaja también aparece en su precio medio, es más
probable que exista en otras plataformas (y la demo en vivo usa precisamente Deriv).

**Datos:** velas de 1 min de precio medio de la API pública de Deriv (`ticks_history`, granularidad 60), 19 pares
(los de Deriv entre los 24 de los Estudios 25 y 27), 2026-04-01 → 2026-09-30 (los mismos meses que el Estudio 27),
ventana 21:00–23:59 UTC.

**Regla:** Bollinger (20, 2), señal al cierre de la vela s, reversión, una operación a la vez por par. Solo hay velas
de Deriv, no ticks: la entrada es la **apertura** de la vela t = s + 1 min (L = 0) y la salida, el cierre de la vela
t + 2 (3 min). En el Estudio 27 el equivalente con HistData (L = 0) dio 59,5 %; con el clic a +10 s, 57,2 %.

**Hipótesis H36 (familia de 1). Criterios (todos):**
1. ≥ 1 000 operaciones;
2. p binomial < 0,05 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. CALL y PUT a menos de 5 puntos.

**Informativo:**
- variante fuerte (30 / 2,5 / 5 min);
- coincidencia de señales con HistData en el mismo par y minuto, y del resultado en las señales comunes;
- acierto con el empate contado como pérdida;
- hora 22 UTC.

**Expectativa declarada:** 56–60 %. Si el precio de Deriv no muestra la ventaja, la demo en vivo pierde su base y se
anotaría como advertencia mayor.

**Resultado del Estudio 34 (commit 954284d, aplicado mecánicamente; `results/estudio34/resultado.json`).**
Año 2024-09 → 2025-08, nunca usado; 24 pares; precio medio de ticks; clic a +10 s:

| Hipótesis | Operaciones | Acierto [lím. inf.] | Empate = pierde | CALL / PUT | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|---|---|
| **H34a** (regla actual, 3 min) | 65 119 | **56,21 %** [55,82 %], EV +0,039 | 55,23 % | 56,6 / 55,9 % | **12 de 12** | **PASA** (se replica) |
| H34b (solo con diferencial normal) | 41 268 | 53,27 % [52,78 %], EV −0,014 | 52,24 % | 53,5 / 53,1 % | 3 de 12 | no pasa |
| **H34c** (30 / 2,5 / 5 min) | 23 594 | **59,59 %** [58,95 %], EV +0,101 | 58,85 % | 60,2 / 59,0 % | **12 de 12** | **PASA** |

**Hallazgo clave (informativo): la ventaja vive en los minutos de diferencial muy abierto.** Acierto de H34a por
decil del diferencial relativo (diferencial en la señal ÷ referencia nocturna de los 20 días previos):

| Decil | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| Diferencial relativo hasta | 0,67 | 0,77 | 0,85 | 0,95 | 1,09 | 1,48 | 2,61 | 4,39 | 7,33 | 61 |
| Acierto | 54,0 % | 52,9 % | 52,9 % | 53,3 % | 54,1 % | 53,3 % | 53,8 % | **60,1 %** | **63,1 %** | **65,9 %** |

**Lectura:**
- La reversión nocturna se replica en otro año, pero su mecanismo es de **microestructura**. Cuando el
  diferencial se abre 3–60 veces lo normal (poca liquidez tras el cierre de Nueva York), el **precio medio** se mueve
  porque cambia una de las dos puntas y luego vuelve. Con diferencial normal, el acierto (~53–54 %) queda por
  debajo del equilibrio.
- Que una plataforma de binarias pague ese movimiento depende de **qué precio usa** y de si a esas horas baja el pago
  o suspende la operación. Es la mayor duda práctica de P10. El Estudio 36 (precio de Deriv) y la confirmación del
  Estudio 29 la acotan.
- Hora 22 UTC: 61,7 %.
- Mejores pares: GBPAUD 60,1 %, EURGBP 59,0 %. Peores: USDCAD 52,9 %, NZDUSD 53,4 %.

## Estudio 37 — ¿la ventaja de BTC a 1 min existe en el precio de otra bolsa (Coinbase)? (pre-registro, 2026-10-29, ANTES de descargar velas de Coinbase)

**Origen:** el Estudio 34 mostró que una ventaja puede depender de cómo se forma el precio en una fuente concreta.
El modelo de BTC aprende y se juzga con el último precio de Binance (BTC/USDT). Las plataformas de binarias usan su
propio precio, a menudo un índice de varias bolsas. Si la continuación del final de la vela es un movimiento real de
BTC, también debe verse en Coinbase (BTC/USD).

**Señales:** las de H20a (Estudio 20): predicciones mes a mes 2025-09-01 → 2026-10-25 (`results/estudio20/predicciones.parquet`,
calculadas solo con datos de Binance), con la misma política: EV ≥ 0,02 con pago del 85 % y la tasa de empates de
Binance. Son las mismas 22 129 operaciones.

**Resultado con Coinbase:** velas de 1 min de BTC-USD de la API pública de Coinbase Exchange. La señal se decide en
el segundo 50 de la vela t y el clic a +10 s cae en su cierre. Por eso, resultado = signo(cierre de la vela t + 1 −
cierre de la vela t) en Coinbase (empate si son iguales). Si falta alguna de las dos velas, la operación no se cuenta.

**Hipótesis (Bonferroni α = 0,025):**
- **H37a:** todas las señales de H20a;
- **H37b:** solo las de probabilidad ≥ 0,60.

**Criterios (cada una, todos):**
1. ≥ 300 operaciones;
2. p binomial < 0,025 frente a 54,05 %;
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 60 % de los meses.

**Informativo:**
- en cuántas operaciones coinciden los resultados de Binance y Coinbase;
- el acierto cuando no coinciden.

**Expectativa declarada:** algo menos que en Binance (57,6 % / 62,5 %). Un acierto cercano al 50 % indicaría que la
ventaja es propia del precio de Binance y no un movimiento de BTC.

**Resultado del Estudio 37 (aplicado mecánicamente; `results/estudio37/resultado.json`): NO PASA. Advertencia mayor.**

| Hipótesis | Operaciones | Acierto con Coinbase [lím. inf.] | Mismas señales con Binance | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|---|
| H37a (todas) | 22 030 | **52,22 %** [51,55 %] | 57,60 % | 0 de 14 | no pasa |
| H37b (p ≥ 0,60) | 5 148 | **53,75 %** [52,35 %] | 62,53 % | 4 de 10 | no pasa |

**Informativo:**
- el resultado coincide entre Binance y Coinbase en el 88,2 % de las operaciones;
- cuando no coincide, Binance da la razón al modelo el 67,1 % de las veces.

**Lectura:**
- La mayor parte de la ventaja del modelo de BTC (5–9 puntos de 7–12) **es propia del último precio de Binance** en
  esos segundos. No es un movimiento de BTC visible en otra bolsa grande.
- En Coinbase queda un resto de información (52–54 %), por debajo del equilibrio.
- Consecuencia práctica: una plataforma que liquide con su propio precio (índice de varias bolsas) probablemente
  **no** pague la ventaja medida con Binance. Los Estudios 5, 16, 20 y 21 siguen siendo válidos **para el precio de
  Binance**; su utilidad real depende del precio de liquidación de cada plataforma.
- Siguiente: medir con el precio de un bróker (Deriv, Estudio 38).

## Estudio 38 — señales de BTC juzgadas con el precio de un bróker (Deriv, cryBTCUSD) (pre-registro, 2026-10-29, ANTES de descargarlo)

**Origen:** el Estudio 37. Las plataformas de binarias liquidan con su propio precio. Deriv es un bróker con API
pública, y su precio de BTC es lo más parecido disponible.

**Diseño:** idéntico al Estudio 37:
- las señales de H20a;
- resultado = signo(cierre de la vela t + 1 − cierre de la vela t) con las velas de 1 min de `cryBTCUSD` de Deriv;
- periodo 2025-09-01 → 2026-10-25, o el tramo que Deriv tenga disponible (se informa la cobertura).

**Hipótesis (Bonferroni α = 0,025):**
- **H38a:** todas;
- **H38b:** p ≥ 0,60.

**Criterios:** los del Estudio 37 (≥ 300 operaciones, p < 0,025, Wilson > 54,05 %, EV > 0 en ≥ 60 % de los meses).

**Expectativa declarada:** parecido a Coinbase (52–54 %).

**Resultado del Estudio 36 (commit a0921d8, aplicado mecánicamente; `results/estudio36/resultado.json`): PASA.**

| Precio | Operaciones | Acierto [lím. inf.] | Empate = pierde | CALL / PUT |
|---|---|---|---|---|
| **Deriv, regla actual (H36)** | 22 981 | **56,35 %** [55,69 %], EV +0,040 | 53,64 % | 56,3 / 56,4 % |
| Deriv, variante 30 / 2,5 / 5 min | 8 669 | 60,67 % [59,62 %], EV +0,119 | 58,75 % | 61,3 / 60,0 % |
| HistData, mismas reglas (L = 0) | 24 778 | 57,43 % | 55,94 % | 57,7 / 57,2 % |

**Hallazgo clave:**
- Las señales de las dos fuentes **casi no coinciden**: solo 1 565 caen en el mismo par y minuto, y en ellas la
  dirección coincide el 45,9 % de las veces (como el azar). Cada fuente tiene sus propios saltos de diferencial, y la
  reversión ocurre **dentro de cada fuente**.
- Junto con el Estudio 34, la conclusión es que la reversión nocturna es un fenómeno del precio de cada proveedor en
  las horas de poca liquidez.
- **Consecuencia práctica:** las señales deben calcularse **con el mismo precio con el que liquida la plataforma**.
  Las señales del modo en vivo (precio de Deriv) solo son coherentes para operar en Deriv. Para otra plataforma
  (por ejemplo, IQ Option), la regla tendría que aplicarse sobre su propio gráfico (Bollinger 20, 2 en velas de
  1 min, de 16:00 a 19:00 en Bogotá).
- Hora 22 UTC con Deriv: 55,7 %.

**Resultado del Estudio 38 (aplicado mecánicamente; `results/estudio38/resultado.json`): NO PASA.** Cobertura del historial
de Deriv para `cryBTCUSD`: desde el 2025-10-29 (un año); los meses anteriores no existen en su API.

| Hipótesis | Operaciones | Acierto con Deriv [lím. inf.] | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|
| H38a (todas) | 17 560 | **52,36 %** [51,61 %] | 3 de 13 | no pasa |
| H38b (p ≥ 0,60) | 3 690 | **53,20 %** [51,55 %] | 3 de 9 | no pasa |

**Lectura:**
- Coincide con Coinbase (Estudio 37). El resultado es el mismo que en Binance en el 87,7 % de las operaciones,
  pero la ventaja se queda en Binance.
- **Conclusión firme:** el modelo de BTC a 1 min (Estudios 15, 16, 20 y 21) predice el **último precio de Binance**,
  no el precio de BTC que usan otras bolsas y brókeres. Para una plataforma de binarias que liquida con su propio
  precio, su acierto esperado es ~52–53 %, por debajo del equilibrio.
- Las confirmaciones pre-registradas siguen su curso (miden lo que dicen medir, con Binance), pero **no** son una
  recomendación para operar en otra plataforma.

## Estudio 39 — reversión nocturna operable en Deriv: su precio, 22–24 UTC, vencimiento 15 min (pre-registro, 2026-10-29, ANTES de calcularla a 15 min)

**Origen:**
- el Estudio 36 mostró que la reversión existe con el precio de Deriv (56,4 % a 3 min; 60,7 % a 5 min);
- la API de Deriv (`contracts_for` y `proposal`, 2026-10-29) muestra que:
  - en divisas, el «sube/baja» (CALL/PUT) dura **como mínimo 15 min**;
  - Deriv **no deja operar de 20:50 a 22:00 UTC**.

Por eso la única versión operable en Deriv es: su precio, entradas de **22:00 a 23:59 UTC** y vencimiento de 15 min.
Además, señal y pago usarían el mismo precio.

**Datos:** las velas de 1 min de Deriv ya descargadas para el Estudio 36 (`data/raw/deriv_velas/`, 19 pares,
2026-04 → 2026-09, 19:30–00:10 UTC). Es el mismo periodo, con un vencimiento que no se había calculado.

**Regla:**
- Bollinger sobre velas de 1 min de Deriv; señal al cierre de la vela s; reversión;
- entrada en la apertura de la vela t = s + 1 (L = 0), solo si t está entre las 22:00 y las 23:59 UTC;
- salida en el cierre de la vela t + 14 (15 min);
- una operación a la vez por par (15 min).

**Hipótesis (Bonferroni α = 0,025):**
- **H39a:** N = 20, K = 2;
- **H39b:** N = 30, K = 2,5.

**Criterios (cada una, todos):**
1. ≥ 500 operaciones;
2. p < 0,025 frente a 54,05 % (pago 85 %);
3. Wilson 95 % > 54,05 %;
4. CALL y PUT a menos de 5 puntos.

El pago real de Deriv a esas horas se consultará con `proposal` y se informará el equilibrio correspondiente.

**Expectativa declarada:** dudosa. A 15 min, el rebote del diferencial pesa menos y el movimiento real del mercado
pesa más.

**Consecuencia:** solo si pasa, se pre-registra su confirmación con datos de Deriv posteriores al 2026-10-25 y se
propone al usuario una demo **automática** en Deriv con su API oficial (cuenta demo y token del usuario, guardado
solo en `.env`).

**Resultado del Estudio 39 (aplicado mecánicamente; `results/estudio39/resultado.json`): NO PASA.**

| Hipótesis | Operaciones | Acierto [lím. inf.] | CALL / PUT | 22 UTC | 23 UTC |
|---|---|---|---|---|---|
| H39a (20 / 2) | 8 697 | 53,83 % [52,77 %] | 53,1 / 54,6 % | 56,7 % | 51,2 % |
| H39b (30 / 2,5) | 4 214 | 53,36 % [51,84 %] | 53,4 / 53,4 % | 57,3 % | 50,6 % |

**Lectura:**
- A 15 min la reversión se diluye, y Deriv no deja operar en su tramo más fuerte (20:50–22:00 UTC).
- La hora de las 22 UTC (56,7–57,3 %) es una lectura *post hoc*: solo vale como hipótesis para datos nuevos
  (Estudio 40).
- Pago de Deriv a 15 min en esas horas: por consultar con `proposal` después de las 22:00 UTC (a las 21:00 UTC la API
  respondió «Trading is not available from 20:50:00 to 22:00:00»).

**Nota (2026-10-29, 22:05 UTC; consulta `proposal` a 15 min en los 19 pares, CALL y PUT):** Deriv no da precio.
Respondió en las 38 consultas: «Trading on forex contracts with duration less than 5 hours is not available from
21:00:00 to 23:59:59». Es decir:
- de 20:50 a 22:00 UTC no se opera nada;
- de 21:00 a 23:59 UTC no se opera ningún contrato de divisas de **menos de 5 horas**.

La premisa del Estudio 39 («de 22:00 a 23:59 UTC sí se puede operar») era **falsa**: se dedujo del primer mensaje sin
comprobarlo a las 22:00 (registro de errores, ítem 49). El resultado del Estudio 39 no cambia (no pasa). Conclusión:
**en Deriv la reversión nocturna de divisas no se puede operar a ninguna hora útil**, porque la ventaja existe solo de
21 a 24 UTC (Estudio 30) y a 5 horas o más no tiene sentido. No hay pago que informar.

## Estudio 40 — confirmación: reversión en Deriv de 22:00 a 22:59 UTC a 15 min (pre-registro, 2026-10-29, ANTES de ver datos de Deriv posteriores al 2026-10-25)

**Origen:** Estudio 39, lectura *post hoc* por hora.

**Regla:** la de H39a (Bollinger 20, 2 sobre velas de 1 min de Deriv; reversión; entrada en la apertura de t;
vencimiento de 15 min; una a la vez por par), solo con t de 22:00 a 22:59 UTC, en los 19 pares.

**Datos:** velas de Deriv del 2026-10-26 al 2027-01-18. Deriv guarda un año, así que se descargan después.
Evaluación **única** después del 2027-01-18.

**Hipótesis H40 (α = 0,05). Criterios (todos):**
1. ≥ 300 operaciones;
2. p < 0,05 frente al equilibrio del **pago real** de Deriv a esa hora (consultado con `proposal` antes de evaluar;
   si no se puede consultar, 85 %);
3. Wilson 95 % por encima de ese equilibrio.

**Consecuencia:** si pasa, se propone al usuario una demo automática en Deriv con su API oficial.

**Nota (2026-10-29, 22:05 UTC, después del pre-registro y antes de ver datos nuevos):** Deriv no permite contratos de
divisas de menos de 5 horas de 21:00 a 23:59 UTC (nota del Estudio 39). Por eso la consecuencia anterior **no se puede
cumplir**: el Estudio 40 se conserva sin cambios (regla, datos, criterios y fecha), pero solo como medida científica de
si la reversión de las 22 UTC con el precio de Deriv persiste a 15 min. Aunque pase, **no** se propondrá ninguna
operación en Deriv. Como no hay pago real a esa hora, el criterio 2 usa el 85 % (equilibrio 54,05 %), tal como prevé
el propio pre-registro.

## Estudio 41 — señales de BTC juzgadas con el precio que parece usar IQ Option: promedio de Binance, Bybit y OKX (pre-registro, 2026-10-30, ANTES de descargar velas de Bybit y OKX del periodo)

**Origen: captura del usuario** (IQ Option, Bitcoin «Binaria», 2026-10-29 23:06:57 Bogotá = 2026-10-30 04:06:57 UTC).

En la captura:
- precio 77 925,99;
- abajo, compra/venta 77 925,5690 / 77 925,5680. Tiene 4 decimales y 0,001 de diferencial: es un precio
  **calculado**, no el libro de una bolsa.

Precios de las bolsas en ese segundo (Binance y OKX, velas de 1 s) o en el cierre de ese minuto (el resto):

| Bolsa | Precio |
|---|---|
| Binance | 77 934,00 |
| OKX | 77 925,0 |
| Bybit | 77 918,9 |
| Bitget | 77 929,12 |
| KuCoin | 77 930,6 |
| Gate | 77 917,8 |
| Coinbase (en dólares) | 77 725,46 |

- El promedio de Binance, Bybit y OKX da 77 925,97; el de las seis bolsas en USDT, 77 925,9.
- Las 31 velas de 1 min de la captura (22:36–23:06 Bogotá), leídas en píxeles (±2 USD), se parecen más a ese
  promedio que a Binance solo, que va unos 10 USD más arriba.

Conclusión provisional: IQ Option liquida BTC con un **promedio de bolsas en USDT**, de composición exacta desconocida.

**La binaria de BTC de IQ Option (lo que muestra la misma captura):**
- vencimiento fijo (23:15);
- la compra se cierra 5 min antes (a las 23:06:57 quedaban 3:03 para comprar);
- pago 87 %.

Es el caso R = 5 del Estudio 19: 53,22 % con el precio de Binance, por debajo del equilibrio de 53,48 %.
Consecuencia directa de un resultado ya medido (no es un estudio nuevo): **la binaria de BTC de IQ Option no tiene
ventaja con nuestro modelo**, ni siquiera con el precio de Binance. Queda por saber qué duraciones y pago tiene el
«blitz» de BTC (se pidió al usuario).

**Pregunta del Estudio 41:** la ventaja de 1 min, ¿sobrevive al promedio de varias bolsas en USDT?
- Es un diagnóstico: si no sobrevive a 1 min, menos sobrevivirá a 3–5 min.
- La respuesta decide si el modelo de BTC sirve en IQ Option o si hay que aprender con su precio reconstruido
  (idea 0 de docs/10).

**Señales:** las de H20a (las mismas de los Estudios 37 y 38): predicciones mes a mes 2025-09-01 → 2026-10-25
(`results/estudio20/predicciones.parquet`), política EV ≥ 0,02 con pago del 85 %.

**Precio de juicio:**
- velas de 1 min de BTC/USDT al contado de Binance, Bybit y OKX, de sus API públicas;
- precio compuesto = promedio simple de los tres cierres del minuto. Si falta alguna de las tres, la operación no se
  cuenta;
- resultado = signo(compuesto de la vela t + 1 − compuesto de la vela t), con la misma alineación que los Estudios 37
  y 38: la señal se decide en el segundo 50 de la vela t y el clic a +10 s cae en su cierre. Empate si la diferencia
  es menor de 0,005.

**Hipótesis (Bonferroni α = 0,025):**
- **H41a:** todas las señales de H20a, juzgadas con el compuesto;
- **H41b:** solo las de probabilidad ≥ 0,60.

**Criterios (cada una, todos):**
1. ≥ 300 operaciones;
2. p binomial < 0,025 frente a 54,05 % (pago 85 %, como en los Estudios 37 y 38);
3. Wilson 95 % > 54,05 %;
4. EV > 0 en ≥ 60 % de los meses.

**Informativo:**
- las mismas señales juzgadas con Bybit solo, con OKX solo y con Binance (velas de su API, como referencia);
- coincidencia de resultados entre Binance y el compuesto, y acierto cuando no coinciden.

**Expectativa declarada:** entre Coinbase (52,2 %) y Binance (57,6 %). El compuesto incluye a Binance con un tercio del
peso.

**Consecuencia:**
- Si H41a o H41b pasa: se pre-registra un estudio del blitz de BTC con la duración y el pago reales que dé el usuario.
- Si ninguna pasa: el modelo de BTC no sirve con el precio de IQ Option. Solo quedaría entrenar un modelo nuevo con
  el precio compuesto (idea 0), con pre-registro propio.

## Estudio 42 — blitz de BTC de IQ Option (3 min, pago 86 %): modelo que aprende con el precio compuesto (pre-registro, 2026-10-30, ANTES de ver el resultado del Estudio 41 y de calcular nada a 3 min con el compuesto)

**Origen:** segunda captura del usuario (IQ Option, Bitcoin «Blitz», 2026-10-29 23:15:34 Bogotá = 04:15:34 UTC):
- vencimiento fijo de **3 min desde la compra** (no se puede cambiar);
- beneficio 86 %, así que el equilibrio es 1/1,86 = 53,76 %;
- precio 78 210,15 (compra/venta con 4 decimales). Un instante antes de una caída brusca, Binance marcaba 78 218,26 y
  OKX 78 213,1. Con Bybit cerca de 78 199, el promedio de las tres da unos 78 210: **otra vez el promedio, no Binance**.

Es la idea 0 de docs/10 («aprender con el precio de la plataforma») aplicada al único contrato corto de BTC que tiene
el usuario. La binaria (5–20 min, pago 87 %) ya quedó sin ventaja (Estudio 41, R = 5 del Estudio 19).

**Precio compuesto:** promedio simple de los cierres de 1 min de BTC/USDT al contado de Binance, Bybit y OKX, con las
mismas velas y la misma caché que el Estudio 41 (`data/raw/bolsas_usdt/`), ampliadas hacia atrás hasta 2024-08 para
entrenar.

**Etiqueta:**
- decisión en el segundo 50 de la vela t; clic a +10 s, que cae en el cierre de t;
- el blitz dura 3 min, así que resultado = signo(compuesto(t + 3) − compuesto(t)), con los cierres de cada minuto;
- empate si la diferencia es menor de 0,005.

**Variables:** las del modelo H16b / Estudio 20 (vela anterior de Binance y bloque parcial hasta el segundo 50 con
velas de 1 s de Binance) más tres del compuesto, todas conocidas en el segundo 50 de t (vol = exp(lvol60) de la vela
t − 1, como en las demás):
1. `c_r1` = log(compuesto(t − 1) / compuesto(t − 2)) / vol;
2. `c_r3` = log(compuesto(t − 1) / compuesto(t − 4)) / (vol · √3);
3. `c_disp` = diferencia en puntos básicos entre Binance y el compuesto al cierre de t − 1, menos su media de los 60
   minutos anteriores (qué bolsa va adelantada).

**Modelo y periodo:** la receta del Estudio 20, sin cambios salvo la etiqueta:
- GBM mes a mes, periodo de prueba 2025-09-01 → 2026-10-25;
- cada mes se entrena solo con los 12 meses anteriores (el último 20 % para calibrar), con purga de 5 min porque la
  etiqueta dura 3;
- mismos ajustes de `config/research.toml`;
- tasa de empates estimada con las 1 440 etiquetas anteriores ya conocidas (desfase de 5 min).

**Política:** EV estimado ≥ 0,02 con pago del 86 % y empate reembolsado (con el compuesto casi no hay empates).

**Hipótesis (Bonferroni α = 0,025):**
- **H42a:** todas las operaciones de la política;
- **H42b:** solo las de probabilidad ≥ 0,60.

**Criterios (cada una, todos):**
1. ≥ 300 operaciones;
2. p < 0,025 frente a 53,76 %;
3. Wilson 95 % > 53,76 %;
4. intervalo del EV (bootstrap por semanas, 97,5 %) por encima de 0;
5. EV > 0 en ≥ 60 % de los meses.

Las operaciones de 3 min se solapan (una por minuto). Por eso el criterio 4 usa bloques semanales.

**Informativo:**
- una a la vez (sin operaciones solapadas);
- referencia: el mismo modelo entrenado con la etiqueta de **Binance** a 3 min y juzgado con el compuesto. Mide si
  aprender con el precio de la plataforma ayuda;
- acierto en el horario del usuario (21:00–01:00 Bogotá).

**Expectativa declarada:** dudosa. A 3 min, con el precio de Binance, el modelo dio 54,1 % (Estudio 18, otro periodo).

**Consecuencia:**
- Si H42a o H42b pasa: se pre-registra su confirmación con datos posteriores al 2026-10-25 (evaluación única después
  del 2027-01-18) y se construye un modo de práctica para el blitz (aviso en el segundo 50 con el precio compuesto).
- Si no pasa: el blitz de BTC de IQ Option queda **sin señal**.

El resultado del Estudio 41 se lee después de este commit y no cambia este diseño.

**Resultado del Estudio 41 (aplicado mecánicamente; `results/estudio41/resultado.json`; las tres bolsas completas,
604 805 minutos cada una): H41a NO PASA (solo por el criterio de los meses); H41b PASA.**

| Hipótesis | Operaciones | Acierto con el compuesto [lím. inf.] | EV (pago 85 %) | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|---|
| H41a (todas) | 22 129 | **55,48 %** [54,81 %] | +0,026 | 8 de 14 (57 %) | no pasa (criterio 4) |
| H41b (p ≥ 0,60) | 5 185 | **58,64 %** [57,26 %] | +0,081 | 9 de 10 | **pasa** |

Las mismas señales juzgadas con cada bolsa por separado (informativo):

| Precio de juicio | Todas | p ≥ 0,60 |
|---|---|---|
| Binance | 57,60 % | 62,53 % |
| OKX | 54,90 % | 57,43 % |
| Bybit | 54,26 % | 57,00 % |
| Compuesto (promedio de las tres) | 55,48 % | 58,64 % |
| *Coinbase (Estudio 37, en dólares)* | *52,22 %* | *53,75 %* |
| *Deriv (Estudio 38, en dólares)* | *52,36 %* | *53,20 %* |

- El resultado coincide entre Binance y el compuesto en el 92,6 % de las operaciones. Cuando no coincide, Binance da
  la razón al modelo el 59,1 % de las veces.
- En H41b no hubo señales con p ≥ 0,60 en 2026-01, 2026-04, 2026-05 ni 2026-06: se concentran en algunos meses, como
  ya se vio en el Estudio 20.

**Lectura:**
- Una parte grande de la ventaja **sí sobrevive** en las otras bolsas en USDT (OKX, Bybit) y en su promedio. Se pierde
  en las bolsas en dólares (Coinbase, Deriv). Probablemente las bolsas en USDT siguen a Binance en los mismos
  segundos, y las de dólares tienen su propio ruido (más la diferencia entre USDT y dólar).
- Para IQ Option, que liquida con un promedio en USDT, el filtro p ≥ 0,60 daría ~58,6 % **a 1 min**. Pero IQ Option no
  tiene BTC a 1 min. Su contrato corto es el blitz de 3 min (Estudio 42, ya pre-registrado).
- Es desarrollo con datos ya usados por el modelo (2025-09 → 2026-10-25). La confirmación con datos nuevos es el
  Estudio 43.

## Estudio 43 — confirmación: señales de alta confianza juzgadas con el precio compuesto (pre-registro, 2026-10-30, ANTES de mirar velas de Bybit u OKX posteriores al 2026-10-25)

**Señales:** las del Estudio 21, es decir, el modelo congelado `BTCUSDT-anticipada-k50-L10-35b764` con p ≥ 0,60 y la
política de H16b, del 2026-10-26 al 2027-01-18. Son las que guarda el registro diario (`results/registro/btc/`), con
los aciertos sellados.

**Precio de juicio:** el compuesto del Estudio 41: promedio simple de los cierres de 1 min de BTC/USDT al contado de
Binance, Bybit y OKX, con la misma alineación. Las velas se descargan después del 2027-01-18.

**Hipótesis H43 (α = 0,05). Criterios (todos):**
1. ≥ 300 operaciones;
2. p < 0,05 frente a 54,05 % (pago 85 %);
3. Wilson 95 % > 54,05 %.

**Evaluación:** una sola vez, después del 2027-01-18, junto con el Estudio 21. Si hay menos de 300 operaciones, se
informa el conteo y se espera hasta llegar a 300, con un máximo de 6 meses.

**Consecuencia:** si pasa, queda confirmado que las señales de 1 min de alta confianza sirven con un precio promedio
en USDT, como el de IQ Option. Aun así, solo serían operables donde exista un contrato de 1 min con ese precio.

**Resultado del Estudio 42 (aplicado mecánicamente; `results/estudio42/resultado.json`): H42a PASA; H42b no pasa
(pocas operaciones).**

| Hipótesis | Operaciones (por día con señal) | Acierto [lím. inf.] | EV por operación [IC 97,5 %] | Meses con EV > 0 | Veredicto |
|---|---|---|---|---|---|
| H42a (política EV ≥ 0,02 al 86 %) | 13 066 (34) | **55,34 %** [54,48 %] | +0,029 [+0,013; +0,048] | 12 de 13 | **pasa** |
| H42b (p ≥ 0,60) | 242 | 60,33 % [54,05 %] | +0,122 [−0,005; +0,208] | 2 de 2 | no pasa (< 300 y IC del EV) |

Equilibrio: 53,76 %. En 2025-09 la política no hizo ninguna operación. El único mes negativo fue 2026-05 (52,6 %).

**Informativo (H42a):**

| Variante | Operaciones | Acierto | EV |
|---|---|---|---|
| Una a la vez (sin solaparse) | 9 545 | 55,22 % [54,22 %] | +0,027 [+0,008; +0,045] |
| Referencia: el mismo modelo entrenado con la etiqueta de Binance | 26 239 | 54,88 % | +0,021 |
| Solo en el horario del usuario (21:00–01:00 Bogotá) | 1 589 (5 por noche) | 56,81 % [54,36 %] | +0,057 [+0,007; +0,103] |

**Lectura:**
- Con el precio que usa IQ Option, reconstruido como el promedio de Binance, Bybit y OKX, el blitz de BTC de 3 min
  muestra una ventaja **pequeña pero estable** en desarrollo: 55,3 % frente al 53,8 % necesario. Equivale a unos
  +3 centavos por cada dólar apostado.
- **Aprender con el precio de la plataforma ayuda.** El modelo entrenado con el promedio gana más por operación que el
  entrenado con Binance (+0,029 frente a +0,021) y es más selectivo.
- En el horario del usuario el acierto fue mayor (56,8 %), pero es una lectura *post hoc*, con pocas operaciones.
- Es desarrollo: los meses de prueba se predicen sin mirar el futuro, pero el diseño ya se conocía. **Falta la
  confirmación con datos nuevos (Estudio 44).** Hasta entonces, solo práctica en la cuenta demo.
- Supuestos que la confirmación no puede comprobar:
  - el promedio de tres bolsas es una aproximación del precio de IQ Option, verificada en dos momentos;
  - el clic cae 10 s después del aviso, es decir, el blitz empieza al cierre de la vela;
  - el pago sigue en 86 %.

## Estudio 44 — confirmación del blitz de BTC con el precio compuesto (pre-registro, 2026-10-30, ANTES de entrenar el modelo congelado y de mirar datos posteriores al 2026-10-25)

**Modelo congelado:**
- la receta exacta del Estudio 42 (mismas variables, etiqueta del compuesto a 3 min, GBM y calibración);
- entrenado **una sola vez** con los 12 meses del 2025-10-26 al 2026-10-25, el último 20 % para calibrar, con purga
  de 5 min;
- se guarda en `config/modelos/BTCUSDT_blitz3_compuesto.pkl`; el SHA-256 y los datos del entrenamiento van en
  `config/senal_blitz.json`;
- no se vuelve a entrenar ni se cambia hasta la evaluación. El modo de práctica usa este mismo modelo.

**Política:** la de H42a: EV estimado ≥ 0,02 con pago del 86 %. La tasa de empates es la del entrenamiento (con el
compuesto es casi cero).

**Datos:** del 2026-10-26 al 2027-01-18:
- velas de 1 s de Binance (archivos diarios públicos), para las variables del segundo 50;
- cierres de 1 min de Binance, Bybit y OKX, para las variables y el resultado con el compuesto.

Se descargan después del 2027-01-18.

**Hipótesis (Bonferroni α = 0,025):**
- **H44a:** todas las horas;
- **H44b:** solo el horario del usuario: decisión de 02:00 a 05:59 UTC (21:00–00:59 Bogotá).

**Criterios (cada una, todos):**
1. ≥ 300 operaciones;
2. p < 0,025 frente a 53,76 %;
3. Wilson 95 % > 53,76 %.

Si H44b no llega a 300 operaciones, se informa el conteo y se espera hasta llegar, con un máximo de 6 meses.

**Evaluación:** una sola vez, después del 2027-01-18.

**Consecuencia:**
- Si pasa, el aviso del blitz queda confirmado para seguir practicando en la cuenta demo.
- Operar con dinero real sigue prohibido sin una autorización expresa y específica del usuario.
- Si no pasa, el blitz de BTC queda sin señal y se retira el modo de práctica.

## Estudio 45 — «Le di $1 000 a ChatGPT»: cinco estrategias típicas de BTC, elegir las dos mejores y ver qué pasa después (pre-registro, 2026-10-30, ANTES de calcular nada)

**Origen:** audio de un video corto que mandó el usuario (85 s, transcrito en local). El autor pidió a ChatGPT cinco
estrategias «rentables» para Bitcoin, las pasó a Pine Script y las probó en TradingView sobre el pasado:
- tres perdieron;
- dos ganaron +927 % y +1 588 % en 6 meses («500 dólares serían 8 440; 44 dólares al día»).

No dice las reglas, la temporalidad, el apalancamiento ni las comisiones.

**Qué se mide:** el método, no sus cifras.
1. Elegir las 2 mejores de 5 estrategias en un periodo pasado, ¿predice algo del periodo siguiente?
2. ¿Cuánto apalancamiento hace falta para que una estrategia corriente dé +927 % o +1 588 % en 6 meses, y qué
   caída sufre por el camino?

**Las cinco estrategias** (las que ChatGPT suele proponer para BTC; fijadas antes de calcular). Todas compran y
venden en largo, sin apalancamiento, sobre velas de **4 h** de BTC/USDT de Binance, y deciden al cierre de la vela
para operar desde la siguiente:
1. **Cruce de EMA 9/21:** dentro mientras la EMA 9 esté por encima de la EMA 21.
2. **RSI (14):** entra cuando el RSI cruza hacia arriba el 30; sale cuando cruza hacia abajo el 70.
3. **MACD (12, 26, 9):** dentro mientras el MACD esté por encima de su señal.
4. **Bollinger (20, 2):** entra cuando el cierre queda bajo la banda inferior; sale cuando supera la media de 20.
5. **Supertrend (ATR 10, multiplicador 3):** dentro mientras la tendencia sea alcista.

Referencia: comprar y mantener.

**Costos:** 0,1 % por lado (comisión de contado de Binance); informativo: sin costos (lo que TradingView usa por
defecto).

**Datos y ventanas:**
- velas de 1 min de BTC/USDT de Binance del 2020-12 al 2026-10-25, agrupadas en 4 h;
- semestres consecutivos desde el 2021-01-01, con el último del 2026-04-25 al 2026-10-25, el equivalente a «hace 6
  meses» del video;
- no se usa nada posterior al 2026-10-25.

**Procedimiento:** en cada semestre k se eligen las 2 estrategias con mayor rendimiento, con costos. Se mide su
rendimiento en el semestre k + 1 y se compara con el promedio de las 5 y con comprar y mantener.

**Hipótesis H45 (α = 0,05):** en el semestre siguiente, las 2 elegidas rinden más que el promedio de las 5. Se usa
una prueba de signos sobre los pares de semestres, unilateral.

**Informativo:**
- en el último semestre: el rendimiento de cada estrategia;
- el apalancamiento constante que haría falta para llegar a +927 % y +1 588 %, y la mayor caída del capital con ese
  apalancamiento;
- lo mismo con velas de 1 h.

**Expectativa declarada:** H45 no pasa. Las elegidas no deberían destacar después (los Estudios 8, 9, 17 y 22 ya
mostraron que estos indicadores no tienen ventaja). Las cifras del video deberían requerir mucho apalancamiento o
errores de prueba.

**Nota de implementación (2026-10-30, antes de calcular):**
- Los semestres van anclados al final: el último es [2026-04-26, 2026-10-26), es decir, incluye el 25 de octubre
  completo. Los anteriores retroceden de 6 en 6 meses, y el primero empieza el 2021-04-26.
- Los meses previos (desde 2020-12) solo sirven para calentar los indicadores.
- Cada vela de 4 h cuenta en el semestre en que abre.

**Resultado del Estudio 45 (aplicado mecánicamente; `results/estudio45/resultado.json`): H45 NO PASA.**

| Temporalidad | Las 2 elegidas superan al promedio de las 5 en el semestre siguiente | p (signos) |
|---|---|---|
| 4 h (principal) | 6 de 10 | 0,377 |
| 1 h (informativo) | 8 de 10 | 0,055 |

Con 4 h, el promedio de las elegidas en el semestre siguiente fue **+2,7 % por semestre**. Comprar y mantener dio
+10,0 % en los mismos 10 semestres.

**Último semestre (2026-04-26 → 2026-10-25, «hace 6 meses» del video), 4 h, sin apalancamiento:**

| Estrategia | Con costos (0,1 %) | Sin costos | Operaciones |
|---|---|---|---|
| MACD | +9,9 % | +18,6 % | 38 |
| Supertrend | +2,7 % | +5,5 % | 13 |
| Bollinger | 0,0 % | +4,9 % | 24 |
| EMA 9/21 | −8,2 % | −2,6 % | 29 |
| RSI 30/70 | −8,5 % | −7,8 % | 3 |
| *Comprar y mantener* | *+3,3 %* | | |

- Ninguna de las dos mejores llega a +927 % ni con 50 veces de apalancamiento: el capital se liquida antes, aun sin
  contar los movimientos dentro de cada vela.
- **Lectura adicional (*post hoc*, `results/estudio45/maximo_con_apalancamiento.json`):** se tomó, en cada semestre
  desde 2021, la mejor estrategia y el mejor apalancamiento **después** de conocer el resultado, es decir, la
  elección más tramposa posible. El máximo fue +687 % (RSI con 10×, 2023-04 → 2023-10), con una caída del 86 % por el
  camino. Nunca se llega a +927 % ni a +1 588 %.

**Lectura:**
- Pedir estrategias a ChatGPT, probarlas en el pasado y quedarse con las que salieron bien no predice el futuro: las
  elegidas rinden en el semestre siguiente como las demás.
- Cifras de +927 % o +1 588 % en 6 meses con estas estrategias exigen al menos una de estas cosas:
  - mucho apalancamiento y un semestre muy favorable, con caídas de 60–90 % por el camino;
  - errores de la prueba de TradingView: sin comisiones, mirar el futuro con `request.security` o repintado,
    rellenos imposibles (docs/07);
  - elegir el periodo y los parámetros después de ver el resultado.
- Además el método mezcla tres sesgos: probar varias y mostrar las mejores (5 → 2), mirar solo el pasado y no
  restar costos.
- Nada de esto aplica al blitz: es otro mercado (contado o futuros con apalancamiento), no opciones de pago fijo.
