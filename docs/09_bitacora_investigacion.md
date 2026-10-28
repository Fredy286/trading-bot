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
