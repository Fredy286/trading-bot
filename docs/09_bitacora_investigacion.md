# Bitácora de investigación diaria

Bitácora automática (tarea `investigacion-diaria-trading-bot`): cada día se anota qué se buscó, qué se halló
(con fuente) y qué evaluaciones se acercan. Solo se investiga y se propone; no se ejecutan estudios ni se miran
datos posteriores al 2026-10-25 (reservados para los Estudios 12, 14 y 15).

## 2026-10-26

**Temas buscados:** (1) flujo de órdenes y predictibilidad de BTC a segundos/minutos; (2) adelanto entre
mercados (spot/perpetuo/otras bolsas); (3) estacionalidad por hora y regímenes de volatilidad en BTC a 1 min.
Rotar mañana a: financiación / interés abierto / liquidaciones y deterioro de estrategias.

**Hallazgos**

1. *«The Quarter-Hour Effect»* (preprint arXiv, jul-2026). Datos: operaciones de 6 perpetuos de Binance.
   Mecanismo: ráfagas de volumen y volatilidad en los minutos «redondos» (1, 5, 15 min) por algoritmos
   (las operaciones se vuelven menos «redondas» en esos momentos). Dice que el retorno de apertura es
   predecible fuera de muestra y que el desbalance de órdenes en la apertura del cuarto de hora predice 4–12 h;
   los desbalances de 1 y 5 min casi no predicen. Tamaño del efecto: NO se pudo leer (solo el resumen);
   costos no mencionados. Fuente: https://arxiv.org/abs/2607.09426 (versión completa no leída:
   https://arxiv.org/html/2607.09426v2). Evidencia: preprint, sin revisión de pares.
   - ¿Se puede probar? Sí, con velas de 1 min/1 s de Binance (periodo ≤ 2026-10-25).
   - Hipótesis comprobable (para un futuro pre-registro): ¿la dirección de la vela que arranca en minuto
     :00/:15/:30/:45 (o la presión `clpos` de la vela anterior) se comporta distinto al resto de minutos?
     Es decir, añadir al GBM la variable «minuto del reloj (mod 5, mod 15)» y comparar log-loss fuera de
     muestra (walk-forward trimestral, periodo limpio). Cautela: el efecto ya reportado es a 4–12 h, no a 1 min.
2. *Polymarket–Binance (OpenMarket)* (preprint, 2026): los precios de Polymarket reaccionan a grandes
   movimientos de Binance tras ~347 ms de mediana; los autores no hallan ventaja operable fuera de muestra.
   Fuente: https://arxiv.org/pdf/2607.26245. Confirma lo que ya sabíamos: lo que se adelanta es del orden de
   milisegundos, fuera del alcance de una entrada manual; sin pieza nueva para el bot.
3. Estacionalidad horaria de BTC (Quantpedia, blog sobre datos horarios de Gemini 2015–2022):
   https://quantpedia.com/the-seasonality-of-bitcoin/ — rendimientos distintos por hora y mejores en días de
   alta volatilidad, pero es *backtest dentro de muestra* sin prueba fuera de muestra: tratar como pista, no
   como evidencia. Útil solo como idea de variable (hora UTC × régimen de volatilidad); el modelo ya usa
   volatilidad. Estudio de apoyo sobre momentum intradía de BTC (liquidez, no información):
   https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/
   (solo leído el resumen del buscador).

**Qué NO hay:** ningún estudio serio con resultados fuera de muestra a 1 min para BTC con costos. Las cifras de
la búsqueda (p. ej. R² de 0,094 a 1 s con desbalance de órdenes, arXiv 2308.14235) son de ajuste dentro de muestra
a 1–10 s y no se pueden operar con un clic manual.

**Propuesta del día (la única que merece atención):** variable de «minuto del reloj» (mod 5 / mod 15) para el
GBM de 1 min, solo como hipótesis nueva pre-registrada y evaluada con datos ≤ 2026-10-25 en desarrollo, y
confirmada después con los datos nuevos. Prioridad baja frente a P1/P8 (ya en marcha).

**Pendientes con fecha**
- H5b del Estudio 5: la muestra de fines de semana debería completarse con el fin de semana del 25-oct;
  lanzar «Estudio 5» en GitHub Actions con `end` = 2026-10-26 (lo hace la sesión principal con Fredy; no ejecutado aquí).
- Estudios 12, 14 y 15 (confirmación): evaluar una sola vez después del 2027-01-18.
- `tbot senal entrenar`: pendiente en cuanto Binance publique el 1m/1s del 2026-10-25.

## 2026-10-27

**Temas buscados:** (1) liquidaciones e interés abierto como predictores de corto plazo en BTC; (2) deterioro
de estrategias (*alpha decay*) en cripto de alta frecuencia; (3) efecto de la hora de pago de la financiación
(*funding*) de los perpetuos sobre el precio, el volumen y el spread. Rotar mañana a: validación fuera de muestra
(métodos) y regímenes de liquidez en divisas/oro.

**Hallazgos**

1. *Liquidaciones e interés abierto:* **nada nuevo que sirva.** Lo que aparece son noticias y blogs de
   vendedores que cuentan casos después de ocurridos (p. ej. el interés abierto subió de ~38 000 a ~47 000
   millones USD antes de la caída del 10-oct-2025), sin ninguna prueba fuera de muestra:
   https://whale-alert.io/stories/b18701fb9e3a7e/Weeks-of-rising-leverage-falling-exchange-supply-preceded-Oct-10-2025-19B-Bitcoin-long-liquidation-early-warning-signs-to-watch ;
   https://blog.amberdata.io/leverage-liquidations-the-31b-deleveraging (umbral del 5 % de
   liquidaciones/interés abierto, sin validar). Confirma lo de docs/08 (1.3): sirven para horas o días, no
   para 1 min, y no hay historial gratuito evento a evento.
2. *Deterioro de estrategias:* sin estudio serio nuevo para cripto a segundos/minutos. Lo más cercano:
   - T-KAN para libro de órdenes (preprint arXiv 2601.02310): mide cómo cae la capacidad de predicción al
     alargar el horizonte, pero con datos de libro tipo acciones, no cripto. https://arxiv.org/pdf/2601.02310
     (solo leído el resumen del buscador).
   - Un informe informal en un repositorio (26 monedas, datos horarios): las estrategias que mejor salían
     dentro de muestra fueron las que más empeoraron fuera de ella. Es un blog técnico, no evidencia:
     https://gitea.com/botdoggy42/exploring-backup/src/branch/master/sr_shitcoin/STRATEGY_COMPARISON.md
   Lección ya incorporada en el proyecto (McLean y Pontiff, docs/08 1.2): por eso se confirma con datos nuevos.
3. *Hora de pago de la financiación* — Ruan y Streltsov (Cornell), *Perpetual Futures Contracts and
   Cryptocurrency Market Quality/Microstructure* (documento de trabajo; resumen en blog de la universidad,
   feb-2025, sin revista indicada). Datos: Huobi (que suspendió perpetuos en 2021), Binance, OKEx, KuCoin,
   Bibox. Mecanismo: el volumen y el spread del **contado** forman una «U» dentro del ciclo de 8 h: más altos
   cerca de la hora del pago y más bajos en medio. No mide rendimientos ni dirección; **no da tamaños del
   efecto** en la página leída. Fuente: https://business.cornell.edu/centers/?p=5984 (el artículo completo no se leyó).
   - ¿Se puede probar? Sí: Binance 1 min/1 s trae volumen y número de operaciones; la hora del pago en
     BTCUSDT perpetuo es 00:00, 08:00 y 16:00 UTC (dato a verificar en la documentación de Binance para todo el
     periodo, porque algunos contratos cambiaron a ciclos de 4 h).
   - Por qué podría importar al bot: la ventaja vive en la continuación de la presión del final de la vela y
     es más fuerte con volatilidad baja (docs/08, sección 2). Si cerca del pago hay más volumen y más spread,
     la presión puede ser más «ruidosa» (rebote entre compra y venta) o más «informada»; no se sabe el signo.
   - Hipótesis comprobable (para un futuro pre-registro, no ejecutada): añadir al GBM de 1 min la variable
     «minutos hasta el próximo pago de financiación» (0–479) y su interacción con `clpos`, y probar si baja el
     log-loss fuera de muestra (walk-forward trimestral con datos ≤ 2026-10-25), más confirmación con datos
     nuevos. Conviene agruparla con la variable de «minuto del reloj» (mod 5/15) de ayer en **una sola familia
     de variables de reloj**, para no multiplicar pruebas. Expectativa honesta: SIN SEÑAL o efecto < 0,5 puntos.

**Propuesta del día:** familia «reloj» (minuto mod 5/15 + minutos hasta el pago de financiación) como una
sola hipótesis nueva, prioridad baja frente a la confirmación de P1/P8. No se propone nada de liquidaciones.

**Pendientes con fecha**
- **H5b del Estudio 5: sigue sin evaluarse** (solo existe `results/estudio5/verdict.json` del 2026-10-24).
  Con el fin de semana del 25-oct la muestra debería llegar a 2 500: lanzar «Estudio 5» en GitHub Actions con
  `end` = 2026-10-26 (lo hace la sesión principal con Fredy; no ejecutado aquí).
- Estudios 12, 14, 15 y 16 (confirmación): evaluación única después del 2027-01-18.
- El modelo de señales anticipadas ya quedó congelado el 2026-10-26 (pendiente de ayer, cerrado).

## 2026-10-28

**Temas buscados:** (1) liquidez y reversión en divisas después del cierre de Nueva York (base de P10);
(2) métodos de validación fuera de muestra (validación cruzada purgada, Sharpe deflactado, probabilidad de
sobreajuste); (3) predictibilidad de muy corto plazo y regímenes de liquidez en oro. Rotar mañana a:
cambios de régimen de volatilidad en cripto (fines de semana, noticias macro) y adelanto oro ↔ dólar.

**Hallazgos**

1. *Krohn, Mueller y Whelan, «Foreign Exchange Fixings and Returns Around the Clock»* (documento de trabajo
   del Banco de Canadá 2021-48; no es revista revisada por pares). PDF leído:
   https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf . Ya estaba citado en docs/02 para
   los *fixings*; lo nuevo hoy es lo que dice **para P10 (reversión nocturna)**:
   - Datos: 9 divisas del G10 contra el dólar, 1999–2019, datos intradía (versiones previas a 5 min) y flujo
     de órdenes de una plataforma entre bancos.
   - Mecanismo: los bancos que dan liquidez acumulan inventario y lo cubren; cuando hay poca capacidad de
     riesgo, el precio se pasa y luego vuelve (reversión). Es el mismo mecanismo que proponemos para P10.
   - Tamaño: ~2,5 pb por día alrededor de los *fixings* (ventanas de horas), t de 4,5 a 11,7; sin costos
     rinde, con costos «la mayor parte de la ganancia desaparece» (según los autores).
   - Dato útil: **las reversiones son más fuertes cuando la volatilidad previa es alta** (lo contrario que
     en BTC 1 min, donde la continuación es más fuerte con volatilidad baja).
   - Además, entre el cierre de Nueva York y el *fixing* de Tokio (9:55 en Tokio = 00:55 UTC) el dólar tiende
     a subir; es una deriva lenta de horas, no sirve para 3 min.
   - Fuente complementaria (CME, 2026, «When FX futures pause»): describe que los bancos reducen riesgo al
     cierre de su libro y muchos proveedores de liquidez se retiran. **No se pudo leer** (tiempo de espera
     agotado): https://www.cmegroup.com/news/2026/when-fx-futures-pause.html

   **Aviso práctico importante para P10 (no es un resultado, es calendario):** el Estudio 27 usó abril →
   septiembre, todo con horario de verano de Nueva York, cuando el cierre de Nueva York es a las 21 UTC. Su
   mejor hora fue las 22 UTC (una hora después del cierre). **El 2026-11-01 Nueva York vuelve a su horario de
   invierno**: el cierre pasa a las 22 UTC (17:00 de Bogotá, que no cambia de hora). Si el efecto va ligado al
   cierre de Nueva York, la «mejor hora» se correría a las 23 UTC (18:00 de Bogotá) en todo el periodo de
   confirmación (2026-10-26 → 2027-01-18). La regla pre-registrada usa 21–24 UTC fijo y cubre ambas horas, así
   que **no hay que cambiarla**; pero:
   - en la demo no conviene concentrarse en las 17:00 de Bogotá por lo visto en verano;
   - el resultado de la confirmación puede salir algo distinto por esta causa, y conviene saberlo de antemano.

   **Hipótesis comprobable (para un futuro pre-registro, no ejecutada):** «la reversión nocturna se ancla al
   cierre de Nueva York, no a la hora UTC». Prueba: con HistData de los 24 pares de 2021 → 2026-03 (incluye
   varios inviernos y veranos; nada posterior al 2026-10-25), comparar el acierto por «horas desde el cierre de
   Nueva York» frente a «hora UTC». Segunda pieza, del documento: ¿la reversión es mayor con volatilidad del
   día anterior alta? Ambas como una sola familia, con Holm, y confirmación con datos nuevos.

2. *Validación fuera de muestra (validación cruzada purgada combinatoria, Sharpe deflactado, probabilidad de
   sobreajuste):* **nada nuevo.** Solo explicaciones de manual y páginas de herramientas, ningún método nuevo de
   2025–2026. El proyecto ya usa lo esencial (pre-registro, walk-forward, periodo bloqueado, Holm/Bonferroni,
   registro de pruebas; docs/01 y docs/08 1.2 ya citan a Bailey y López de Prado). Fuentes:
   https://en.wikipedia.org/wiki/Purged_cross-validation ; https://www.luxalgo.com/library/concept/probability-of-backtest-overfitting/
   (blog de vendedor). Una idea menor: llevar un conteo total de hipótesis probadas en los Estudios 1–27 para
   reportarlo junto a cada «pasa» (cuántas cosas se probaron antes de encontrar esta).

3. *Oro a muy corto plazo:* **nada que sirva.** Solo comentarios de TradingView del tipo «barrido de
   liquidez» (sin pruebas) y una tesis de pregrado con datos diarios
   (https://eprints.umm.ac.id/id/eprint/25133/). Coincide con los Estudios 8, 10 y 17: sin señal en oro.

**Propuesta del día:** solo una, de prioridad media porque toca P10, la pieza que pasó el desarrollo: estudio
nuevo «horas desde el cierre de Nueva York» + volatilidad previa, con datos de divisas hasta 2026-03. Antes de eso,
lo más útil es que Fredy anote en la demo la hora de Bogotá de cada señal nocturna desde el 1-nov.

**Pendientes con fecha**
- **H5b del Estudio 5: sigue sin evaluarse** (solo hay `results/estudio5/verdict.json` del 2026-10-24). Lanzar
  «Estudio 5» en GitHub Actions con `end` = 2026-10-26 (sesión principal con Fredy; no ejecutado aquí).
- **2026-11-01:** cambio de horario de Nueva York (ver hallazgo 1).
- Confirmación del Estudio 27 (P10): cuando HistData publique los ticks de nov-2026 → ene-2027 (sale cada mes),
  una sola vez con datos 2026-10-26 → 2027-01-18.
- Estudios 12, 14, 15, 16 y 21 (confirmación): evaluación única después del 2027-01-18.

## 2026-10-29 (autónoma)

**Preparación:** la cola de estudios (`config/cola_estudios.txt`) estaba vacía: no había resultados sin documentar.
Este entorno **no llega** a data.binance.vision, api.binance.com ni histdata.com (el proxy rechaza la conexión), y
no hay datos locales; tampoco se pudieron abrir arxiv.org ni cryptoslate.com. Por eso el estudio de hoy se deja
en la cola de GitHub Actions.

**Temas buscados:** (1) regímenes de volatilidad de BTC y fines de semana a alta frecuencia; (2) liquidez y
diferencial en divisas alrededor del cambio de día de las 17:00 de Nueva York (base de P10); (3) dependencia de
los retornos de 1 min según volatilidad, hora y desbalance de órdenes; (4) comportamiento del precio alrededor
de la financiación de los perpetuos (00/08/16 UTC). Rotar mañana a: noticias macro programadas en divisas y
adelanto oro ↔ dólar.

**Hallazgos**
1. *Volatilidad de BTC por día y hora:* nada nuevo y útil para 1–15 min. De Nicola (Ledger, 2021,
   https://ledger.pitt.edu/ojs/ledger/article/view/213) halla autocorrelación negativa a 1–4 h, no a 1 min;
   Karim y otros (IRFA 2024, https://ideas.repec.org/a/eee/finana/v96y2024ipas1057521924005490.html) estudian
   la relación retorno–volatilidad de 1 min a diario. Un informe de industria citado por Blockworks
   (https://blockworks.co/news/bitcoins-price-predictable-study) dice que el viernes es más volátil; sin método
   verificable. Leído solo el resumen del buscador.
2. *Cambio de día en divisas (17:00 NY):* solo páginas de brókeres y foros (p. ej.
   https://blackbull.com/en/education-hub/understanding-roll-over-and-widening-spreads-2,
   https://financefeeds.com/bidfx-research-finds-liquidity-gap-in-fx-markets-between-4-pm-and-6-pm-est/): el
   diferencial se abre varios pips unos minutos (de 5 min a 1 h según el relato) porque los bancos reinician
   sus motores de precios. **Ninguna fuente mide si el precio revierte después.** Para P10 confirma el riesgo
   práctico ya anotado: en la demo, mirar el diferencial real del bróker justo después de las 17:00 NY.
3. *Reloj de cuarto de hora en cripto:* Kim y Hansen (preprint, julio 2026, https://arxiv.org/abs/2607.09426,
   **no leído completo**; ya citado el 2026-10-26) y un resumen de prensa (https://cryptoslate.com/?p=559513,
   **no se pudo abrir**): el volumen y el movimiento se concentran en los minutos :00/:15/:30/:45, sobre todo en
   sus primeros 10 s, y el efecto sigue al quitar las horas de financiación. Las páginas de brókeres confirman
   la financiación de Binance a las 00, 08 y 16 UTC (p. ej. https://www.sharpe.ai/funding-rates/exchange/binance).

**Estudio del día — Estudio 33 (pre-registro aea2c8b, código a1598a3):** la «familia de reloj» propuesta el
26 y el 27 de octubre, en una sola hipótesis. Al GBM de BTC 1 min (el de los Estudios 7 y 13) se le añaden 8
variables de calendario del minuto que se opera: ¿es :00/:15/:30/:45?, ¿múltiplo de 5?, su fase dentro del
cuarto de hora, ¿es en punto?, minutos hasta la financiación, ¿es la hora de financiación o los 5 min siguientes?
Pasa solo si mejora el log-loss (IC 95 % > 0) y el EV de la política en el desarrollo (2022-01 → 2025-08) y,
además, en la verificación (2025-09 → 2026-09). Datos solo hasta 2026-09. **No ejecutado aquí** (sin acceso a
Binance): orden `tbot research study33` en la cola; GitHub Actions la corre a las 10:00, 16:00 o 22:00 de Bogotá.
Expectativa declarada: sin señal o < 0,5 puntos.

**Nota técnica:** los Estudios 25, 27, 28, 30 y 31 no tienen comando `tbot research studyNN` (se ejecutaron por
otra vía), así que la cola no puede repetirlos; el Estudio 33 sí lo tiene y descarga sus propios datos.

**Incidencia de subida:** el primer intento de push recibió 403 (sin permiso de escritura). En un reintento el permiso
ya funcionaba, pero mientras tanto la sesión principal había usado el número 32 (auditoría prospectiva de canales) y
pedía subir a `claude/rutina-AAAA-MM-DD`. Se rehízo todo sobre la rama actual como **Estudio 33** (antes de ejecutar
nada) y se subió a `claude/rutina-2026-10-29`; `integrar_rutina.yml` lo lleva a la rama principal si pasan las pruebas.

**Pendientes con fecha**
- **2026-10-30:** documentar el resultado del Estudio 33 en docs/01 (tabla + veredicto), docs/08 (P12) y
  CLAUDE.md. Si la orden falla en Actions, revisar el registro del flujo «Cola de estudios».
- **2026-11-01:** cambio de horario de Nueva York (sin cambios en la regla de P10: ventana UTC fija).
- H5b del Estudio 5: sigue sin evaluarse (sesión principal con Fredy).
- Estudios 12, 14, 15, 16, 19, 21 y 29 (confirmación): evaluación única después del 2027-01-18.

**Para Fredy**
- Hoy busqué si la hora exacta del reloj (los minutos :00, :15, :30, :45 y la hora en que se pagan las
  financiaciones) ayuda a adivinar el siguiente minuto de BTC. Un estudio reciente dice que en esos minutos
  hay ráfagas de movimiento.
- Dejé la prueba escrita y congelada (Estudio 33). La corre GitHub sola hoy; aquí no hay acceso a Binance.
- Espero honestamente que no cambie nada; si mejora, habría que confirmarlo con datos nuevos.
- Para las señales nocturnas: justo después de las 17:00 de Nueva York los brókeres abren el diferencial; en la
  demo fíjate si el precio salta en esos minutos.
- No cambió nada en el bot ni en las señales.

### 2026-10-29 (autónoma, segunda ejecución)

Tema del jueves: reversión nocturna en divisas. Una segunda ejecución de la rutina diseñó un estudio (réplica de la
reversión nocturna en 2024-09 → 2025-08, un año que nunca se miró con precio medio, y un filtro de «diferencial
normal»). Al ir a subirlo vio que la primera ejecución ya había integrado el Estudio 33 (reloj). Por la regla de
**un estudio nuevo al día**, no se subió: quedó como idea 5 en docs/10, con el diseño completo y sin ningún dato real
visto (solo una prueba con datos inventados, que dio ~50 %, como debe). Incidente anotado en docs/04 (ítem 45).

Fuentes del mecanismo (el diferencial se abre tras las 17:00 de Nueva York): CME, «When FX futures pause» (2026),
https://www.cmegroup.com/articles/2026/when-fx-futures-pause.html (no se leyó completo; resumen del buscador);
BidFX según https://financefeeds.com/bidfx-research-finds-liquidity-gap-in-fx-markets-between-4-pm-and-6-pm-est/
(prensa del sector: de 16:00 a 18:00 EST pasa menos del 0,6 % del volumen diario).

**Para Fredy:** nada cambia hoy. La próxima prueba de la reversión nocturna ya está diseñada: repetirla en otro año y
comprobar que no sea un efecto de los minutos en que el bróker abre el diferencial.


## 2026-10-30 (autónoma)

Tema del viernes: canales de señales.

**Estado de la vigilancia (Estudio 32):** el flujo de captura sí corre (última captura 2026-10-30 05:37 UTC, 12
canales). La auditoría con precios aún no ha juzgado ningún día: el registro diario del 29 corrió antes de que hubiera
un día completo, y el del 30 (06:40 UTC) todavía no aparece en la rama a las 12:15 UTC (horarios de GitHub poco
fiables, ítem 46). `tbot canales tabla` está vacía; no hay nada que leer, y de todos modos no habrá veredicto antes
del 2027-01-31.

**Lectura a mano de lo capturado (sin precios):** de 12 canales, solo **2** dan señales verificables con las reglas
del pre-registro: gotraderssinaisfree (63 señales con entrada entre el 29 y el 31 de octubre) y QuotexSignalfreee (14).
Los demás publican casi todo en OTC (PocketSignalsM15 100 %, PocketOptionSignalsM5 ~90 %), solo resultados después de
la hora (GavinVIPResults, PocketSignalsM1, pocket_option_signals6), pares que Deriv no tiene (quotexsignals2814:
USD/COP) o no publican desde antes del 29 (Unidos, QuotexSignalsM1). Además aparecieron dos fallos de lectura:
el texto se cortaba a 500 caracteres y las listas fechadas publicadas tarde se movían al día siguiente.
→ **Enmienda 1 del Estudio 32** (a35670a, antes de auditar ningún día) y su código con pruebas; registro de errores 50.

**Búsqueda de canales nuevos:** sin resultado útil. Desde este entorno no se abren t.me ni los directorios de canales
(tlmtr.io): «host no permitido». Las búsquedas web solo devolvieron copiadores de señales para MetaTrader y
denuncias de estafas con canales de binarias (p. ej. https://www.forexpeacearmy.com/community/threads/binary-options-investment-scam-on-telegram.62568/post-348346,
https://forums.babypips.com/t/scam-alert-usdjpy-master-telegram-channel/883700; solo resúmenes del buscador). No se
añadió ningún canal: no se pudo comprobar que publiquen antes de la entrada ni que no sean OTC.

**Estudio nuevo:** ninguno (no había material que lo justificara).

**Pendientes con fecha**
- 2026-10-31: comprobar que el registro diario auditó el 29 y el 30 (`results/auditoria_canales/dias_auditados.txt`).
- Sesión local con Fredy: buscar 3–5 canales nuevos con listas NO OTC fechadas (t.me sí abre desde su PC).
- 2026-11-01: cambio de horario de Nueva York (la ventana nocturna es UTC fija: sin cambios).
- Estudios 12, 14, 15, 16, 19, 21 y 29: evaluación única después del 2027-01-18; canales: 2027-01-31.

**Para Fredy**
- Hoy revisé los canales de señales que el bot vigila cada hora. De 12, solo 2 publican señales que se puedan
  comprobar (con hora antes de entrar y sin OTC). Los otros publican OTC o solo «ganamos» después.
- Arreglé dos fallos antes de que contaran: se cortaban las listas largas y algunas señales se juzgaban el día
  equivocado. Todavía no se ha juzgado ninguna señal, así que nada cambia en los resultados.
- No pude buscar canales nuevos: desde la nube no se abre Telegram. Si me pasas nombres de canales que publiquen
  listas de divisas normales (no OTC), los agrego.
- El bot y las señales no cambiaron.


## 2026-10-31 (autónoma)

Tema del sábado: robustez y calidad.

**Tarea previa (paso 0.4):** el Estudio 33 (variables de «reloj») estaba en [hechas] desde el 2026-10-29 con su
resultado en `results/estudio33/`, pero nunca se había documentado en docs/01. Quedó documentado mecánicamente:
**NO PASA** — el log-loss mejora en desarrollo y verificación, pero el EV de la política baja (0,0437 → 0,0435;
verificación 0,0408 → 0,0395). El cuarto de hora parecía fuerte en desarrollo (57,9 %), pero en el último año baja a
55,2 % con un IC del EV que incluye 0. Actualizados docs/08 (P12) y docs/10 (idea 1, cerrada).

**Flujos de GitHub (consultados con la API de Actions a las ~12:20 UTC):** todos los últimos en verde. Vigilancia de
canales: última captura 2026-10-31 09:32 UTC. Cola de estudios: corrió a las 09:16 UTC (sin pendientes). Pruebas:
verdes en los 5 últimos commits. Registro diario: el último es el del 2026-10-30 13:28 UTC (registró el 29 y auditó
los canales del 29); el de hoy todavía no había corrido (está programado a las 06:40 UTC y GitHub lo viene lanzando
unas 7 h tarde, ítem 46). No es una falla: `tbot registro pendientes` recupera los días que falten.

**Revisión de código (fugas de futuro, unidades de tiempo, zonas horarias), en Estudios 41, 42, 47, `live/blitz.py`,
`live/registro.py`, `live/nocturna.py` y Estudio 32:**
- Sin fugas de futuro: las variables del compuesto usan solo cierres hasta t − 1; la purga entre ajuste y calibración
  cubre los 5 min de la etiqueta; la probabilidad de empate se estima con 5 min de retraso.
- Horario del usuario bien convertido (21:00–01:00 Bogotá = 02:00–06:00 UTC). HistData (velas y ticks) usa EST fijo
  sin horario de verano: +5 h es correcto todo el año. La ventana nocturna en vivo es UTC fija (Estudio 28): el cambio
  de hora de Nueva York de mañana (2026-11-01) no la mueve.
- Corregido (ítem 51): la referencia en vivo del blitz juzgaba el empate con otra regla que el estudio. Impacto mínimo.
- Anotado (ítem 52): la vela de las 23:59 UTC queda sin resultado en el registro diario (1 de 1 440 minutos; hasta hoy
  ninguna señal cayó ahí). No se tocaron los archivos sellados.
- Riesgo menor: la vigilancia de canales usa desfases horarios fijos. GavinVIPResults está en −5; si su hora fuera la
  de Nueva York, hasta hoy era −4. Ese canal solo publica resultados después de la hora (no aporta señales
  verificables), así que no cambia nada; revisar si algún día publica señales.

**Estudio nuevo:** ninguno (el tema del día es revisar, no probar estrategias).

**Pendientes con fecha**
- 2026-11-01: confirmar que el registro diario registró el 30 y el 31 (`results/registro/btc/`) y auditó los canales.
- 2026-11-01 (domingo): resumen semanal para Fredy y repriorizar docs/10.
- Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44 y 46: evaluación única después del 2027-01-18; canales: 2027-01-31.

**Para Fredy**
- Hoy revisé que todo lo automático esté funcionando: sí funciona (captura de canales, cola de estudios y pruebas).
- La prueba del «reloj» (minutos :00/:15/:30/:45) no mejora el bot: parecía buena hasta 2025 y en el último año no.
- Arreglé un detalle pequeño en el modo blitz: cómo decide un empate. No cambia las señales.
- Mañana cambia la hora en Nueva York; la ventana de divisas usa hora fija, así que no se mueve.
- El bot y las señales no cambiaron.



## 2026-11-01 (autónoma)

Tema del domingo: resumen semanal y repriorizar docs/10.

**Comprobaciones:** sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y todo lo hecho ya documentado
(el Estudio 33 se documentó ayer). Registro diario (API de Actions): 4 ejecuciones, todas en verde; la última,
2026-10-31 13:00 UTC, registró hasta el 30 de octubre. El 31 entrará con la ejecución de hoy (GitHub la lanza ~6 h
tarde, ítem 46; `tbot registro pendientes` recupera los días que falten). Conteos (sin aciertos, sello hasta el
2027-01-19), 26 → 30 de octubre: BTC 170 señales (7 con p ≥ 0,60; 6 de cuarto de hora), **ETH 0**, nocturna 927
(fuerte 377; 22 UTC 314). Canales: 12 vigilados; auditados el 29 y el 30.

### Resumen de la semana (2026-10-26 → 2026-11-01)

**Qué se aprendió**
1. **El precio manda.** Las señales de BTC solo funcionan con el precio de Binance o de un promedio de bolsas en USDT.
   Con Coinbase (52,2 %) o con el BTC de Deriv (52,4 %) se pierden (Estudios 37–38).
2. **IQ Option desarmado:** liquida BTC con un promedio con pesos (Binance 0,34, Gate 0,37, OKX 0,22, Bybit 0,07;
   Estudio 47, leído de 275 velas de capturas). Su binaria de 15 min no tiene ventaja; su **blitz de 3 min (pago 86 %)
   sí la tiene en desarrollo: 55,3 %** frente al 53,8 % necesario (Estudios 42 y 47). Modelo congelado y modo de práctica.
3. **Reversión nocturna de divisas:** se replica en otro año (Estudio 34), pero vive en los minutos con diferencial
   muy abierto; Deriv no deja operar en esas horas y cobra la reversión en el pago → no operable allí.
4. **No funcionan:** variables de reloj (33), ETH/USDC como ayuda a BTC (24), estrategias de «ChatGPT» (45), los
   indicadores clásicos y los canales de Telegram auditados.

**Qué está en marcha (automático)**
- Registro diario de señales (BTC, ETH, nocturna), sellado hasta el 2027-01-19.
- Vigilancia de 12 canales cada hora y su auditoría (veredicto el 2027-01-31).
- Cola de estudios y esta rutina diaria.

**Próximas fechas**
- 2027-01-19: evaluación única de las confirmaciones (Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44 y 46) y
  apertura del registro.
- 2027-01-31: veredicto de los canales (Estudio 32).

**Repriorización de docs/10:** primero, el precio de la plataforma (blitz con el precio reconstruido); segundo,
verificar en la demo el precio, el empate y el pago del blitz (necesita a Fredy); luego traders verificados y canales.
ETH baja de prioridad (0 señales en 5 días). Las ideas cerradas quedan en su propia tabla para no repetirlas.

**Estudio nuevo:** ninguno (domingo de resumen).

**Pendientes con fecha**
- 2026-11-02: confirmar que el registro del 31 de octubre y del 1 de noviembre quedó guardado.
- Sesión local con Fredy: anotar precios de entrada del blitz en la demo (`tbot blitz comparar`) y buscar canales no OTC.

**Para Fredy**
- Esta semana el bot aprendió que lo más importante es usar el MISMO precio que tu plataforma.
- Descubrimos cómo calcula IQ Option el precio de BTC (un promedio de 4 bolsas).
- Con ese precio, el «blitz» de 3 minutos acierta 55 % en el pasado; hace falta 54 % para no perder. Es poco margen
  y falta confirmarlo con datos nuevos en enero.
- Si quieres ayudar: en la demo, anota el precio de entrada de algunas operaciones blitz; así comprobamos el precio.
- Las divisas de noche no se pueden operar en Deriv. El bot y las señales no cambiaron hoy. Solo demo.

## 2026-11-02 (autónoma)

Tema del lunes: literatura y microestructura. Pregunta concreta, ligada a la idea 0 de docs/10: ¿qué bolsa marca
primero el precio de BTC, y eso deja anticipar un promedio de bolsas como el de IQ Option?

**Comprobaciones:** sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y lo hecho ya está documentado.
Registro diario: hay archivos hasta el 2026-10-31 (BTC, ETH y nocturna; el 31 fue sábado, sin divisas). El del
1 de noviembre entrará con la ejecución de hoy (GitHub la lanza tarde, ítem 46). Conteos (sin aciertos, sellado):
nocturna 927 señales en 6 días registrados; ETH 2 señales, ninguna con p ≥ 0,60. Vigilancia de canales: última
captura 2026-11-02 10:54 UTC.

**Búsquedas** (solo vi los resúmenes del buscador; alphaxiv.org, research-api.cbs.dk y coinapi.io no abren desde este
entorno, así que las cifras no están comprobadas en el original):
- Artículo de SSRN (2024), Binance frente a Coinbase: Binance lidera la formación del precio, y la integración entre
  las dos se rompe a frecuencias muy altas (resumen del buscador).
- Resumen de arXiv 2506.08718 (alphaxiv.org/overview/2506.08718v1): la «participación informativa» de Binance se
  acercaría a 0,9996 entre 2023-09 y 2024-09. Sin verificar en el original.
- Tesis de la CBS, «High Frequency Lead Lag Relationships in The Bitcoin Market»
  (research-api.cbs.dk/ws/portalfiles/portal/59795067/…): con datos tick a tick, algunas bolsas siguen a otras con
  hasta 15 s de retraso.
- Tutorial de CoinAPI (coinapi.io/tutorials/analyzing-lead-lag-effects-between-exchanges-flat-files): entre Binance y
  OKX no hay líder claro a 1 s. Es un tutorial, no un estudio revisado.
- Tesis del MIT (dspace.mit.edu/handle/1721.1/121626): había oportunidades de arbitraje en el 0,03–40 % de los
  intervalos de 5 s, según la moneda y la pareja de bolsas.

**Lectura:**
- Encaja con los Estudios 37, 38 y 41. Las bolsas en USDT copian a Binance en segundos, y por eso la ventaja
  sobrevive en ellas; las bolsas en dólares tienen su propio ruido.
- Pero el retraso entre bolsas es de **segundos**. El modelo decide en el segundo 50 con cierres de 1 min hasta t − 1,
  así que ese retraso ya se agotó. El modelo del blitz ya tiene `c_disp` (Binance − compuesto).
- Un estudio con más variables de «qué bolsa va adelantada» en velas de 1 min sería relleno con expectativa casi nula.
  Con velas de 1 s de otras bolsas sería otro asunto, pero exige descargas grandes que la nube no alcanza.
- La pieza útil es otra: si **el precio de IQ Option va atrasado** unos segundos frente a Binance (el Estudio 47 lo
  sospechó), lo que Binance hizo en esos segundos anticiparía el precio del blitz. Eso solo se mide con la hora al
  segundo y el precio de IQ Option. Queda como idea 1b en docs/10 (sesión local, junto con `tbot blitz comparar`).

**Estudio nuevo:** ninguno. No lo forcé: la literatura no da una hipótesis que se pueda probar con datos de 1 min, y
la versión al segundo necesita datos de IQ Option que solo el usuario puede capturar.

**Pendientes con fecha**
- 2026-11-03: confirmar que el registro del 1 y del 2 de noviembre quedó guardado.
- Sesión local con Fredy: anotar, al segundo, la hora y el precio de entrada de algunas operaciones blitz en la demo
  (ideas 1 y 1b).
- Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44 y 46: evaluación única después del 2027-01-18; canales: 2027-01-31.

**Para Fredy**
- Hoy leí resúmenes de estudios sobre qué bolsa de bitcoin «marca» el precio: casi siempre es Binance, y las demás la
  siguen con unos segundos de atraso.
- Eso explica por qué nuestras señales funcionan con bolsas parecidas a Binance y no con otras.
- Idea para cuando tengas un rato en la demo: anota la hora exacta (con segundos) y el precio de entrada de algunas
  operaciones blitz. Si IQ Option va atrasado frente a Binance, eso podría ser una ventaja extra.
- Hoy no hice ninguna prueba nueva: no había ninguna que valiera la pena. El bot y las señales no cambiaron. Solo demo.

## 2026-11-03 (autónoma)

Tema del martes: estrategias de otras personas con historial verificado (idea 2 de docs/10). Meta: cuentas concretas
con historial largo y desarmar su estilo.

**Comprobaciones:** sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y todo lo hecho ya documentado.
Registro diario: archivos hasta el 2026-11-01 (BTC, ETH y nocturna); el del 2 de noviembre entrará con la ejecución de
hoy (GitHub la lanza tarde, ítem 46). Conteos (sin aciertos, sellado): nocturna 927 señales en 7 días registrados
(fuerte 377; 22 UTC 314). Vigilancia de canales: última captura 2026-11-03 10:45 UTC.

**Búsquedas** (solo resúmenes del buscador; darwinex.com, mql5.com, ideas.repec.org y thegodfunded.com no abren desde
este entorno, así que no pude leer ninguna cuenta concreta ni los textos completos):
- Apesteguia, Oechssler y Weidenholzer, *Copy Trading* (Management Science, 2020;
  https://bse.eu/research/publications/copy-trading): ver y poder copiar a los que ganan **aumenta la toma de riesgo**;
  quienes copian heredan el riesgo (o la suerte) del copiado.
- Estudio de 2018 sobre social trading (QREF 70, https://ideas.repec.org/a/eee/quaeco/v70y2018icp160-171.html): sin
  rentabilidad anormal tras costos para ninguna estrategia de copia.
- Asesores de futuros (J. Futures Markets 2010): persistencia a 3 meses que desaparece en el mejor y el peor cuartil.
- ZuluTrade (https://forexop.com/signals/zulutrade): avisos para proveedores con 100 % de ganadoras y tope de 700 pips de
  pérdida flotante: el acierto «perfecto» suele ser martingala u operar sin stop.
- Empresas de fondeo (https://www.tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances): en más de
  100 000 cuentas de 10 empresas, ~7 % cobra algo. FTMO no publica qué parte de sus clientes cobra.

**Lectura:** nada nuevo que probar. Refuerza la sección 3b de docs/06 (añadida la 3c): los historiales «verificados» se
eligen por supervivencia y el acierto alto suele esconder riesgo. Para desarmar una cuenta real hace falta su CSV
completo de operaciones, que solo se puede bajar en una sesión local.

**Estudio nuevo:** ninguno. No lo forcé: sin datos de operaciones de una cuenta concreta no hay regla que pre-registrar.

**Pendientes con fecha**
- 2026-11-04: confirmar que el registro del 2 y del 3 de noviembre quedó guardado.
- Sesión local con Fredy: anotar precios de entrada del blitz en la demo (ideas 1 y 1b); si quiere, bajar el CSV de
  2–3 cuentas verificadas de Myfxbook/Darwinex con ≥ 3 años para desarmarlas (idea 2).
- Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44 y 46: evaluación única después del 2027-01-18; canales: 2027-01-31.

**Para Fredy**
- Hoy busqué traders con historial verificado que acierten mucho. Los estudios dicen lo mismo de siempre: son muy pocos.
- Copiar a quien va ganando hace que corras más riesgo, no que aciertes más; tras costos, nadie gana copiando en promedio.
- En las empresas de fondeo (FTMO y parecidas) solo ~7 de cada 100 cobran algo.
- No pude abrir cuentas concretas desde la nube. Si un día quieres, bajamos juntos el historial completo de alguna.
- Hoy no hice ninguna prueba nueva. El bot y las señales no cambiaron. Solo demo.

## 2026-11-04 (autónoma)

Tema del miércoles: mejorar el modelo de BTC 1 min (o el de ETH).

**Comprobaciones:** sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y todo lo hecho ya documentado.
Registro diario con archivos hasta el 2026-11-03 en BTC, ETH, nocturna y blitz (el del 2 y el 3 de noviembre quedaron
guardados). Conteos (sin aciertos, sellado): blitz 73 señales en 9 días (p ≥ 0,57: 47; horario del usuario: 8).
Vigilancia de canales: última captura 2026-11-04 06:06 UTC. Desde este entorno, Binance (data.binance.vision y la API)
sigue bloqueado (403 del proxy), así que el estudio se ejecuta en GitHub Actions.

**Idea del día:** las dos palancas que han movido el acierto son filtrar por confianza y usar el precio exacto de
liquidación (docs/10). Del precio ya hay mucho; de la confianza solo se ha probado la probabilidad del modelo
(p ≥ 0,60). Pero la ventaja va por épocas: se concentra en algunos meses (Estudios 20 y 41). Si el acierto del modelo
persiste de una semana a otra, su **acierto reciente ya conocido** sería otra forma de confianza. En la literatura es
el «meta-etiquetado» (López de Prado, *Advances in Financial Machine Learning*, 2018, cap. 3; no leí el texto, solo lo
cito como origen) o «operar la curva de capital», con resultados mixtos en foros. No estaba probado aquí (busqué en
docs/).

**Estudio 48** (pre-registro 10677d7, código en otro commit, en la cola de GitHub): con el GBM de BTC 1 min del Estudio
33, se opera solo si el acierto de las últimas 500 operaciones ya resueltas (H48a) o el de los últimos 7 días (H48b)
llega al equilibrio (54,05 %). Debe ganar en desarrollo (2022-01 → 2025-08, con intervalo por semanas) y repetirse en
verificación (2025-09 → 2026-09). Datos hasta 2026-09: nada reservado. Expectativa: dudosa.

**Pendientes con fecha**
- 2026-11-05: documentar el resultado del Estudio 48 (results/estudio48/) según su pre-registro.
- Sesión local con Fredy: anotar precios de entrada del blitz en la demo (ideas 1 y 1b de docs/10).
- Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44 y 46: evaluación única después del 2027-01-18; canales: 2027-01-31.

**Para Fredy**
- Hoy probé una idea nueva para el modelo de bitcoin: «si el bot viene acertando, seguir; si viene fallando, parar».
- Es lo que hace mucha gente con su racha. Lo dejé escrito antes de mirar datos, para no engañarnos.
- La prueba corre sola en GitHub; mañana sabremos si sirve o no.
- El bot y las señales no cambiaron. Solo demo.

## 2026-11-05 (autónoma)

Tema del jueves: mejorar la reversión nocturna en divisas. Antes, la tarea obligatoria: documentar el Estudio 48.

**Comprobaciones:**
- Sin ramas `claude/rutina-*` pendientes.
- Cola: `study48` hecha el 2026-11-04 12:24 UTC, sin documentar → documentada hoy.
- Registro diario: archivos hasta el 2026-11-03. La corrida programada de hoy aún no había arrancado a las 12:15 UTC.
  En los días anteriores arrancó entre las 14:00 y las 16:30 UTC (horarios de GitHub poco fiables, ítem 46): normal.
- Conteos sellados (sin aciertos): BTC 583 señales en 9 días, nocturna 1 375, blitz 73, ETH 13.
- Vigilancia de canales: última captura 2026-11-05 10:45 UTC.

**Estudio 48 (resultado, aplicado mecánicamente): H48a y H48b PASAN.**
- Con el filtro, las operaciones tomadas aciertan 57,2–57,5 % y las saltadas 52,9–54,7 % (desarrollo y verificación).
- La diferencia es de +2,3 a +4,5 puntos, con el intervalo por semanas lejos de 0.
- El acierto de una semana se parece al de la siguiente (correlación 0,36–0,40).
- Sin fuga de futuro: la racha solo usa operaciones resueltas antes de la apertura de la vela.
- La trampa que encontré: la «ganancia por día» del informe compara días distintos (ítem 53 del registro de errores).
  Con totales, la ganancia casi no cambia (desarrollo −6 %, verificación +5 %). El filtro sirve para operar menos con
  la misma ganancia; no es una ventaja nueva.

**Estudio 49 (nuevo, el único del día):**
- Confirmación del filtro con las señales que la nube ya registra del modelo congelado H16b (2026-10-26 → 2027-01-18).
- Pasos: pre-registro (commit propio), código y pruebas en otro commit (`tbot research study49`).
- El código se niega a correr antes del 2027-01-19 (sello del registro). No va a la cola.
- Potencia declarada ~45 %. El blitz queda fuera: tiene muy pocas señales.

**Tema del jueves (búsqueda breve):**
- No encontré un estudio riguroso nuevo sobre la reversión a las 17:00 de Nueva York.
- Lo más cercano: Krohn, Mueller y Whelan, borrador de la conferencia AEA 2020
  (https://benny.aeaweb.org/conference/2020/preliminary/paper/2dedYfDH). Según el resumen del buscador:
  - a esa hora el diferencial es máximo y el volumen mínimo;
  - los vaivenes intradía son reales, pero cuesta ganar con ellos tras costos.
  - No leí el texto completo.
- Encaja con el Estudio 34: la reversión vive en los minutos de diferencial abierto. Nada nuevo que probar hoy.
- Las páginas de brókeres con cifras («4–12 veces el diferencial») no dicen su método; no las uso.

**Pendientes con fecha**
- Sesión local con Fredy: anotar precios de entrada del blitz en la demo (ideas 1 y 1b de docs/10).
- Después del 2027-01-18: evaluar una sola vez los Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44, 46 y 49.
- Canales: veredicto el 2027-01-31.

**Para Fredy**
- La idea de ayer funcionó en los datos viejos: cuando el bot de bitcoin viene fallando, conviene parar un rato.
- Así se aciertan más operaciones (cerca de 57 de cada 100), pero se gana casi lo mismo en total: se opera menos.
- No es una ventaja nueva; sirve para cansarse menos y arriesgar menos en las malas semanas.
- Dejé escrita la prueba de verdad con datos nuevos; se hace en enero, una sola vez.
- El bot y las señales no cambiaron. Solo demo.

## 2026-11-06 (autónoma)

Tema del viernes: canales de señales.

**Comprobaciones:**
- Sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y todo lo hecho ya documentado.
- Vigilancia de canales: corre (última captura 2026-11-06 06:34 UTC, 12 canales).
- Auditoría con precios (Estudio 32): días juzgados del 2026-10-29 al 2026-11-04.
- Registro diario: archivos hasta el 2026-11-04 (el del 5 aún no llega a las 12:15 UTC; horarios de GitHub, ítem 46).
  Conteos sellados (sin aciertos): BTC 632 señales en 10 días (p ≥ 0,60: 46), ETH 14, nocturna 1 575 (fuerte 600).

**Tabla descriptiva `tbot canales tabla` (sin veredicto antes del 2027-01-31):**

| Canal | Señales | Verificadas | Acierto 1.ª entrada | Límite inf. 95 % | p frente al azar |
|---|---|---|---|---|---|
| QuotexSignalfreee | 141 | 94 | 56,4 % | 46,3 % | 0,13 |
| gotraderssinaisfree | 63 | 58 | 48,3 % | 35,9 % | 0,65 |

Lectura: ninguno se distingue del azar todavía (los dos intervalos incluyen 50 %); con 94 señales eso es lo esperable
aunque hubiera ventaja. Lo nuevo: **gotraderssinaisfree no publica señales desde el 2026-10-31**; lo capturado del 3 y
el 5 de noviembre es solo publicidad (tarjetas y registro en Quotex). En la práctica queda un solo canal verificable,
así que el veredicto del 2027-01-31 tendrá poca potencia.

**Búsqueda de canales nuevos:** sin resultado útil. t.me sigue sin abrir desde este entorno (curl sin respuesta). Dos
búsquedas web: apareció el canal vfxAlert_binarysignals (https://t.me/s/vfxAlert_binarysignals/1029), pero según el
resumen del buscador sus estrategias son de «Pocket Option OTC» (no pude abrir la página): no sirve. El resto fueron
listas de advertencia de estafas (https://brokerlistings.com/scams/signals-telegram) y foros de denuncias
(https://www.forexpeacearmy.com/community/tags/telegram-scam/). No se añadió ningún canal.

**Estudio nuevo:** ninguno (no había material que lo justificara; no fuerzo uno).

**Pendientes con fecha**
- Sesión local con Fredy: buscar 3–5 canales con listas NO OTC fechadas (t.me sí abre desde su PC) y anotar precios de
  entrada del blitz en la demo.
- Después del 2027-01-18: evaluar una sola vez los Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44, 46 y 49.
- Canales: veredicto único el 2027-01-31.

**Para Fredy**
- Revisé los canales de señales que el bot vigila. De los dos que se pueden comprobar, uno acierta 56 de cada 100 y el
  otro 48, pero con tan pocas señales eso todavía no se distingue de lanzar una moneda.
- Uno de los dos dejó de publicar señales el 31 de octubre: ahora solo pone publicidad.
- No encontré canales nuevos que sirvan (desde la nube no abre Telegram). Si ves canales con listas de divisas
  normales (no OTC) y con la hora antes de entrar, pásame el nombre.
- El bot y las señales no cambiaron. Solo demo.

## 2026-11-07 (autónoma)

Tema del sábado: robustez y calidad.

**Comprobaciones:**
- Sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y lo hecho ya documentado.
- `git fetch` avisó de una «actualización forzada» de la rama principal: era solo el clon superficial de este
  entorno (la referencia vieja 14ff9e7, del 2026-10-31, sí está en la historia actual). Nada se reescribió.
- Registro diario: 11 días seguidos (2026-10-26 → 11-05), sin huecos. Conteos sellados (sin aciertos): BTC 651
  señales, nocturna 1 809 (fuerte 687), blitz 84 (p ≥ 0,57: 52).
- Vigilancia de canales: captura de hoy (07:02 UTC). Unidos no publica desde el 2026-11-01 y gotraderssinaisfree
  desde el 11-05 (solo publicidad, ver el 11-06). Auditoría con precios hasta el 2026-11-05.
- Pruebas: todas en verde.

**Revisión de código (Estudio 49, la confirmación del filtro de racha):** coincide con su pre-registro (racha solo con
señales resueltas 3 min antes, bootstrap por semanas ISO con semilla 12345, criterios y ampliación). Fallo hallado:
no comprobaba que el registro tuviera todos los días antes de su evaluación única. Si se lanzaba el 19 de enero antes
de que llegara el archivo del 18, se gastaba con datos incompletos. Arreglado: se niega a correr si falta algún día
(ítem 54 del registro de errores; nota de procedimiento en docs/01, sin tocar criterios). Prueba nueva.

**Estudio nuevo:** ninguno (sábado de revisión; no fuerzo uno).

**Pendientes con fecha**
- Sesión local con Fredy: precios de entrada del blitz en la demo (ideas 1 y 1b de docs/10) y canales no OTC.
- Después del 2027-01-18: evaluar una sola vez los Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44, 46 y 49,
  comprobando antes que no falte ningún día de datos.
- Canales: veredicto único el 2027-01-31.
- Mañana (domingo): resumen semanal.

**Para Fredy**
- Hoy revisé que todo lo automático siga funcionando: el registro diario y la vigilancia de canales van bien.
- Encontré y arreglé un descuido: la prueba de enero del «filtro de racha» podía correr con un día de datos faltante.
  Ahora espera a tener todos los días.
- No hubo estudio nuevo. El bot y las señales no cambiaron. Solo demo.

## 2026-11-08 (autónoma)

Tema del domingo: resumen semanal y repriorizar docs/10.

**Comprobaciones:**
- Sin ramas `claude/rutina-*` pendientes; cola de estudios vacía y todo lo hecho ya documentado (33 y 48).
- GitHub Actions: las últimas 25 ejecuciones en verde (pruebas, registro diario, cola, vigilancia de canales y la
  primera grabación del libro de OKX, 2026-11-08 05:29 UTC → `results/okx_libro/2026-11-08_0529.jsonl`).
- Registro diario (conteos sellados, sin aciertos): BTC 672 señales en 12 días (p ≥ 0,60: 47), ETH 15 (p ≥ 0,60: 0),
  nocturna 1 809 en 13 días (fuerte 687), blitz BTC 84 (p ≥ 0,57: 52), blitz ETH 470 (p ≥ 0,57: 176),
  OKX ETH 98 y OKX BTC 218. El blitz llega hasta el 11-05 (Gate publica con retraso, normal).
- Nocturna con 0 señales el viernes 6 (y el 30 de octubre, el 31 y el 1 de noviembre): no es un fallo. Deriv no
  entrega velas de divisas tras el cierre del viernes ni en el fin de semana.
- **Conteos de OKX distintos al desarrollo:** ETH 8,2 señales por día (en el Estudio 54, 25,5) y BTC 18,2 (en el 54,
  11,5). Revisé el código del registro sin mirar aciertos: la regla de compra es la misma del Estudio 54 (comprar si
  p ≥ ~0,551) y cada moneda usa sus propios precios. Parece efecto del mercado de estas dos semanas (en el blitz ya se
  vio que los meses tranquilos dan muchas menos señales de ETH). Se anota para enero; no cambia nada ahora.
- Canales (tabla descriptiva, sin veredicto antes del 2027-01-31): QuotexSignalfreee 182 señales verificadas, 50,5 %
  en la primera entrada (límite inferior 43,3 %); gotraderssinaisfree 58, 48,3 %. Ninguno se distingue del azar.

### Resumen de la semana (2026-11-02 → 2026-11-08)

**Qué se aprendió**
1. **OKX es la mejor vía encontrada hasta ahora (Estudio 54).** Sus contratos «sube o baja en 5 min» de ETH y BTC se
   liquidan con un índice de precios reales y cuestan ~0,52 (equilibrio 53,1 %). Con el aviso anticipado, en el
   pasado: ETH 55,9 % y BTC 56,5 %, 13 de 14 meses con ganancia. Se vio en la cuenta de Fredy (sin operar).
2. **El riesgo nuevo es el precio de compra, no el acierto.** 10 s antes de la ventana solo hay ~13 contratos a 0,52
   y, en BTC, a veces el libro ya está inclinado hacia el lado del modelo (0,55). Si quien vende sabe lo mismo que el
   bot, las señales baratas serían las peores. GitHub graba el libro cada 6 h para medirlo (Estudio 56).
3. **Más monedas dan más señales; revisar más seguido no** (Estudios 50 y 51). El blitz de ETH funciona en el pasado,
   pero IQ Option solo tiene ETH «OTC» (precio propio): no aplica. Solana no pasa (53).
4. **Filtro de racha (48):** parar cuando el modelo viene fallando sube el acierto por operación (~57 %), pero no la
   ganancia total. Sirve para operar menos.
5. **Literatura y traders verificados:** Binance marca el precio de BTC y las demás bolsas lo siguen en segundos;
   copiar a quien va ganando sube el riesgo, no el acierto.
6. **Errores corregidos:** 54 (una evaluación única podía correr con un día faltante) y 56 (el modo OKX en vivo con ETH
   decidía con precios de BTC; el registro no estaba afectado).

**Qué está en marcha (automático)**
- Registro diario sellado: BTC, ETH, nocturna, blitz BTC y ETH, OKX ETH y BTC.
- Grabación del libro de OKX cada 6 h (Estudio 56); vigilancia de canales cada hora; cola de estudios y esta rutina.

**Próximas fechas**
- 2027-01-19: evaluación única de las confirmaciones (Estudios 12, 14, 15, 16, 19, 21, 29, 35, 40, 43, 44, 46, 49,
  52 y 55), primera mirada del Estudio 56 (α 0,01) y apertura del registro. Antes, comprobar que no falte ningún día.
- 2027-01-31: veredicto de los canales (Estudio 32).
- 2027-04-27: mirada principal del Estudio 56 (el libro real de OKX).

**Repriorización de docs/10:** OKX sube arriba (idea 1c: decidir antes de que el libro se vacíe, cuando el libro
grabado diga cuánto se inclina; con cuidado de no usar para elegir el momento el mismo libro del Estudio 56). Las ideas
de IQ Option (0, 1, 1b) siguen, pero dependen de anotaciones de Fredy. Traders verificados y canales, después.

**Estudio nuevo:** ninguno (domingo de resumen).

**Pendientes con fecha**
- 2026-11-09: comprobar que la grabación del libro de OKX corre sola cada 6 h (hoy solo hay la primera, lanzada a mano).
- Sesión local con Fredy: anotar precios de entrada del blitz en la demo de IQ (ideas 1 y 1b) y canales no OTC.

**Para Fredy**
- Esta semana encontramos la mejor opción hasta ahora: los contratos de 5 minutos de OKX (ETH y BTC), con precio real.
- En el pasado el bot habría acertado unas 56 de cada 100; hacen falta 53 para no perder.
- Lo que falta saber es si se puede comprar barato justo cuando el bot avisa. GitHub lo está midiendo solo.
- Nada se confirma hasta enero. No operes con dinero real: OKX no tiene demo útil, así que por ahora solo mirar.
- Todo lo automático funciona. El bot y las señales no cambiaron hoy.
