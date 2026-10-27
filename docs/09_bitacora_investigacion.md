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
