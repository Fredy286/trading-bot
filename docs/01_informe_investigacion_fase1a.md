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
