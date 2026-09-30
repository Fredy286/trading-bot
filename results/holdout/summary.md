## 0. Veredicto del periodo bloqueado (candidatas congeladas en desarrollo)

**CANDIDATAS VALIDADAS EN PERIODO BLOQUEADO (pendiente observación en vivo sin dinero)** — candidatas evaluadas: 10; pasan criterio estricto: 2; pasan criterio mínimo: 5.

| Instrumento | h | Contrato | Modelo | Política | n | Acierto [LI95] | Umbral | EV [IC95] | EV en desarrollo | p Holm (familia) | Mínimo | Estricto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1 | binaria | gbm | B | 58386 | 56.4 % [56.0 %] | 54.05 % | 0.039 [0.028, 0.050] | 0.044 | 0.0000 | sí | sí |
| BTCUSDT | 1 | binaria | gbm | BN | 55955 | 56.5 % [56.1 %] | 54.05 % | 0.041 [0.030, 0.052] | 0.045 | 0.0000 | sí | sí |
| BTCUSDT | 5 | binaria | gbm | B | 4678 | 53.8 % [52.3 %] | 54.05 % | -0.005 [-0.032, 0.021] | 0.021 | 1.0000 | no | no |
| BTCUSDT | 5 | binaria | gbm | BN | 4313 | 53.7 % [52.2 %] | 54.05 % | -0.006 [-0.035, 0.023] | 0.025 | 1.0000 | no | no |
| BTCUSDT | 15 | binaria | rsi14_extremes | A | 3081 | 56.0 % [54.3 %] | 54.05 % | 0.036 [0.006, 0.067] | 0.070 | 0.1214 | sí | no |
| BTCUSDT | 15 | binaria | logit | B | 4187 | 54.4 % [52.9 %] | 54.05 % | 0.006 [-0.021, 0.031] | 0.036 | 1.0000 | sí | no |
| BTCUSDT | 15 | binaria | logit | BN | 3681 | 54.7 % [53.0 %] | 54.05 % | 0.011 [-0.018, 0.039] | 0.041 | 1.0000 | sí | no |
| BTCUSDT | 15 | binaria | gbm | BN | 1988 | 54.0 % [51.8 %] | 54.05 % | -0.001 [-0.038, 0.039] | 0.030 | 1.0000 | no | no |
| BTCUSDT | 60 | binaria | logit | B | 0 | — [—] | 54.05 % | — [—, —] | 0.048 | 1.0000 | no | no |
| BTCUSDT | 60 | binaria | logit | BN | 0 | — [—] | 54.05 % | — [—, —] | 0.063 | 1.0000 | no | no |

# Resultados empíricos — etapa `holdout`

- Commit del código: `fa2b853e1dc62508593d92bb671ccca81e5b2035` — hash de configuración: `2bcecccbf2f9` — versión 0.1.0
- Hipótesis evaluadas (corrección de Holm sobre todas): **624**
- Contrato binario: pago 85%, empate = refund; contado: spread observado + comisión.

## 1. Veredicto mecánico

Configuraciones candidatas (deben superar además el periodo bloqueado y la observación en vivo):

| Instrumento | h | Contrato | Modelo | Política | n | Acierto [IC95] | EV [IC95] | p Holm |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1 | binaria | gbm | B | 58386 | 56.4 % [56.0 %, 56.8 %] | 0.039 [0.028, 0.050] | 0.0000 |
| BTCUSDT | 1 | binaria | gbm | BN | 55955 | 56.5 % [56.1 %, 56.9 %] | 0.041 [0.030, 0.052] | 0.0000 |
| USDJPY | 1 | binaria | gbm | B | 5414 | 57.0 % [55.5 %, 58.5 %] | 0.043 [0.021, 0.064] | 0.0396 |
| USDJPY | 1 | binaria | gbm | BN | 4926 | 57.3 % [55.7 %, 58.8 %] | 0.046 [0.023, 0.069] | 0.0219 |

Cuántas configuraciones (no de referencia) cumplen cada criterio por separado:

| Criterio | Cumplen | De |
|---|---|---|
| c1_min_trades | 429 | 528 |
| c2_above_breakeven | 22 | 528 |
| c3_holm | 6 | 528 |
| c4_stable | 13 | 528 |
| c5_beats_reference | 305 | 528 |

## 2. Calidad de datos

| Instrumento | Fuente | Precio | Minutos en sesión | Minutos cerrados | Min. sin ticks | Rellenados (sin ticks) | Huecos inesperados (≥2 h, días hábiles) | Spread mediano | Desde | Hasta |
|---|---|---|---|---|---|---|---|---|---|---|
| AUDUSD | histdata | BID (spread supuesto) | 2,065,630 | 909,530 | 14,495 | 14,495 | 116 (24,791 min) | 0.000040 | 2021-01-03 | 2026-08-31 |
| BTCUSDT | binance | negociado (sin bid/ask) | 2,978,134 | 1,226 | 8 | 0 | 5 (852 min) | 0.000000 | 2021-01-01 | 2026-08-31 |
| EURUSD | histdata | BID (spread supuesto) | 2,067,006 | 908,154 | 11,621 | 11,621 | 97 (24,750 min) | 0.000020 | 2021-01-03 | 2026-08-31 |
| GBPUSD | histdata | BID (spread supuesto) | 2,065,448 | 909,712 | 11,324 | 11,324 | 109 (23,348 min) | 0.000050 | 2021-01-03 | 2026-08-31 |
| USDJPY | histdata | BID (spread supuesto) | 2,065,530 | 909,630 | 10,688 | 10,688 | 93 (22,161 min) | 0.003000 | 2021-01-03 | 2026-08-31 |
| XAUUSD | histdata | BID (spread supuesto) | 1,961,712 | 1,013,388 | 518 | 518 | 175 (97,851 min) | 0.250000 | 2021-01-03 | 2026-08-31 |

## 3. Movimiento típico frente a costos (periodo de prueba)

Umbral de contado `p* ≈ 0,5 + costo/(2·movimiento)`; si supera 100 % es inalcanzable.

| Instrumento | h (min) | Mov. medio abs. (pb) | Costo medio ida y vuelta (pb) | p* contado | Empates |
|---|---|---|---|---|---|
| AUDUSD | 1 | 0.96 | 1.60 | 133.9 % (inalcanzable) | 8.6 % |
| AUDUSD | 5 | 2.20 | 1.60 | 86.5 % | 3.1 % |
| AUDUSD | 15 | 3.80 | 1.60 | 71.1 % | 1.6 % |
| AUDUSD | 60 | 7.51 | 1.60 | 60.7 % | 0.8 % |
| BTCUSDT | 1 | 3.84 | 20.00 | 310.5 % (inalcanzable) | 3.5 % |
| BTCUSDT | 5 | 8.74 | 20.00 | 164.4 % (inalcanzable) | 0.4 % |
| BTCUSDT | 15 | 15.23 | 20.00 | 115.6 % (inalcanzable) | 0.1 % |
| BTCUSDT | 60 | 30.02 | 20.00 | 83.3 % | 0.0 % |
| EURUSD | 1 | 0.63 | 0.77 | 111.3 % (inalcanzable) | 7.9 % |
| EURUSD | 5 | 1.46 | 0.77 | 76.6 % | 2.8 % |
| EURUSD | 15 | 2.51 | 0.77 | 65.4 % | 1.5 % |
| EURUSD | 60 | 4.96 | 0.77 | 57.8 % | 0.8 % |
| GBPUSD | 1 | 0.72 | 0.89 | 112.4 % (inalcanzable) | 7.0 % |
| GBPUSD | 5 | 1.66 | 0.89 | 76.9 % | 2.4 % |
| GBPUSD | 15 | 2.86 | 0.89 | 65.6 % | 1.2 % |
| GBPUSD | 60 | 5.74 | 0.89 | 57.8 % | 0.6 % |
| USDJPY | 1 | 0.72 | 0.64 | 94.4 % | 6.9 % |
| USDJPY | 5 | 1.66 | 0.64 | 69.2 % | 2.4 % |
| USDJPY | 15 | 2.91 | 0.64 | 61.0 % | 1.1 % |
| USDJPY | 60 | 5.88 | 0.64 | 55.4 % | 0.5 % |
| XAUUSD | 1 | 2.91 | 0.74 | 62.6 % | 0.4 % |
| XAUUSD | 5 | 6.53 | 0.74 | 55.6 % | 0.2 % |
| XAUUSD | 15 | 11.20 | 0.74 | 53.3 % | 0.1 % |
| XAUUSD | 60 | 22.66 | 0.74 | 51.6 % | 0.0 % |

### Sensibilidad del umbral de contado al costo total ida y vuelta

Calculado con el movimiento medio medido; no depende del spread supuesto. Referencia: 1 pip de EUR/USD ≈ 0,9 pb.

| Instrumento | h | costo 0.5 pb | costo 1 pb | costo 2 pb | costo 5 pb | costo 10 pb |
|---|---|---|---|---|---|---|
| AUDUSD | 1 | 76.2 % | inalcanzable | inalcanzable | inalcanzable | inalcanzable |
| AUDUSD | 5 | 61.4 % | 72.7 % | 95.5 % | inalcanzable | inalcanzable |
| AUDUSD | 15 | 56.6 % | 63.2 % | 76.3 % | inalcanzable | inalcanzable |
| AUDUSD | 60 | 53.3 % | 56.7 % | 63.3 % | 83.3 % | inalcanzable |
| BTCUSDT | 1 | 56.5 % | 63.0 % | 76.1 % | inalcanzable | inalcanzable |
| BTCUSDT | 5 | 52.9 % | 55.7 % | 61.4 % | 78.6 % | inalcanzable |
| BTCUSDT | 15 | 51.6 % | 53.3 % | 56.6 % | 66.4 % | 82.8 % |
| BTCUSDT | 60 | 50.8 % | 51.7 % | 53.3 % | 58.3 % | 66.7 % |
| EURUSD | 1 | 89.7 % | inalcanzable | inalcanzable | inalcanzable | inalcanzable |
| EURUSD | 5 | 67.2 % | 84.3 % | inalcanzable | inalcanzable | inalcanzable |
| EURUSD | 15 | 60.0 % | 69.9 % | 89.9 % | inalcanzable | inalcanzable |
| EURUSD | 60 | 55.0 % | 60.1 % | 70.2 % | inalcanzable | inalcanzable |
| GBPUSD | 1 | 84.9 % | inalcanzable | inalcanzable | inalcanzable | inalcanzable |
| GBPUSD | 5 | 65.1 % | 80.1 % | inalcanzable | inalcanzable | inalcanzable |
| GBPUSD | 15 | 58.7 % | 67.5 % | 84.9 % | inalcanzable | inalcanzable |
| GBPUSD | 60 | 54.4 % | 58.7 % | 67.4 % | 93.5 % | inalcanzable |
| USDJPY | 1 | 84.7 % | inalcanzable | inalcanzable | inalcanzable | inalcanzable |
| USDJPY | 5 | 65.0 % | 80.1 % | inalcanzable | inalcanzable | inalcanzable |
| USDJPY | 15 | 58.6 % | 67.2 % | 84.3 % | inalcanzable | inalcanzable |
| USDJPY | 60 | 54.2 % | 58.5 % | 67.0 % | 92.5 % | inalcanzable |
| XAUUSD | 1 | 58.6 % | 67.2 % | 84.3 % | inalcanzable | inalcanzable |
| XAUUSD | 5 | 53.8 % | 57.7 % | 65.3 % | 88.3 % | inalcanzable |
| XAUUSD | 15 | 52.2 % | 54.5 % | 58.9 % | 72.3 % | 94.6 % |
| XAUUSD | 60 | 51.1 % | 52.2 % | 54.4 % | 61.0 % | 72.1 % |

## 4. Acierto fuera de muestra — contrato binario, política A (operar todo)

Umbral con pago 85%: **54.05 %**. Celdas: acierto (n en miles).

| Instrumento | h | random | majority | momentum1 | reversal1 | sma20_trend | rsi14_extremes | boll_reversal | logit | gbm |
|---|---|---|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | 50.0 % (355k) | 50.3 % (355k) | 49.5 % (327k) | 50.5 % (327k) | 49.4 % (355k) | 51.7 % (31k) | 51.7 % (37k) | 50.7 % (355k) | 50.5 % (355k) |
| AUDUSD | 5 | 49.7 % (71k) | 50.0 % (71k) | 49.5 % (66k) | 50.5 % (66k) | 48.6 % (71k) | 53.3 % (6k) | 52.8 % (8k) | 51.0 % (71k) | 51.0 % (71k) |
| AUDUSD | 15 | 50.1 % (24k) | 50.4 % (24k) | 48.5 % (22k) | 51.5 % (22k) | 48.0 % (24k) | 54.6 % (2k) | 54.9 % (3k) | 50.8 % (24k) | 50.9 % (24k) |
| AUDUSD | 60 | 50.5 % (6k) | 50.5 % (6k) | 48.6 % (6k) | 51.4 % (6k) | 46.8 % (6k) | 61.0 % (1k) | 56.7 % (1k) | 51.2 % (6k) | 51.5 % (6k) |
| BTCUSDT | 1 | 50.0 % (520k) | 50.0 % (520k) | 50.4 % (502k) | 49.6 % (502k) | 49.3 % (520k) | 52.4 % (49k) | 52.4 % (55k) | 51.3 % (518k) | 52.0 % (520k) |
| BTCUSDT | 5 | 50.0 % (104k) | 50.4 % (104k) | 49.5 % (101k) | 50.5 % (101k) | 48.4 % (104k) | 54.9 % (10k) | 53.4 % (11k) | 51.4 % (104k) | 51.3 % (104k) |
| BTCUSDT | 15 | 49.6 % (35k) | 50.3 % (35k) | 50.3 % (34k) | 49.7 % (34k) | 48.2 % (35k) | 56.0 % (3k) | 52.4 % (3k) | 52.0 % (35k) | 51.5 % (34k) |
| BTCUSDT | 60 | 50.0 % (9k) | 50.1 % (9k) | 50.8 % (8k) | 49.2 % (8k) | 48.5 % (9k) | 51.2 % (1k) | 48.1 % (1k) | 52.1 % (9k) | 49.9 % (9k) |
| EURUSD | 1 | 49.8 % (355k) | 50.5 % (355k) | 49.5 % (329k) | 50.5 % (329k) | 49.6 % (355k) | 51.9 % (31k) | 51.1 % (37k) | 50.8 % (355k) | 50.6 % (355k) |
| EURUSD | 5 | 50.0 % (71k) | 49.6 % (71k) | 49.6 % (66k) | 50.4 % (66k) | 48.8 % (71k) | 53.4 % (6k) | 52.1 % (8k) | 51.0 % (70k) | 50.7 % (71k) |
| EURUSD | 15 | 50.0 % (24k) | 49.6 % (24k) | 49.5 % (22k) | 50.5 % (22k) | 48.6 % (24k) | 54.4 % (2k) | 53.4 % (3k) | 51.7 % (24k) | 50.7 % (24k) |
| EURUSD | 60 | 51.2 % (6k) | 49.7 % (6k) | 48.6 % (6k) | 51.4 % (6k) | 47.3 % (6k) | 53.0 % (1k) | 52.5 % (1k) | 50.3 % (6k) | 50.7 % (6k) |
| GBPUSD | 1 | 49.9 % (355k) | 50.4 % (355k) | 49.4 % (331k) | 50.6 % (331k) | 49.5 % (354k) | 51.2 % (33k) | 51.8 % (37k) | 50.8 % (355k) | 50.5 % (355k) |
| GBPUSD | 5 | 49.9 % (71k) | 49.7 % (71k) | 49.6 % (67k) | 50.4 % (67k) | 48.9 % (71k) | 52.8 % (7k) | 53.7 % (8k) | 51.2 % (71k) | 50.7 % (71k) |
| GBPUSD | 15 | 50.1 % (24k) | 49.3 % (24k) | 50.3 % (22k) | 49.7 % (22k) | 49.1 % (24k) | 52.6 % (2k) | 52.3 % (3k) | 51.3 % (24k) | 51.3 % (24k) |
| GBPUSD | 60 | 49.6 % (6k) | 49.7 % (6k) | 49.4 % (6k) | 50.6 % (6k) | 48.0 % (6k) | 59.9 % (1k) | 57.3 % (1k) | 52.1 % (6k) | 52.0 % (6k) |
| USDJPY | 1 | 50.0 % (356k) | 50.3 % (356k) | 49.1 % (333k) | 50.9 % (333k) | 48.9 % (356k) | 52.2 % (32k) | 52.4 % (37k) | 51.2 % (356k) | 51.2 % (356k) |
| USDJPY | 5 | 50.3 % (71k) | 51.7 % (71k) | 49.0 % (67k) | 51.0 % (67k) | 48.7 % (71k) | 53.2 % (7k) | 52.6 % (8k) | 51.6 % (71k) | 52.0 % (71k) |
| USDJPY | 15 | 49.6 % (24k) | 52.0 % (24k) | 50.2 % (22k) | 49.8 % (22k) | 48.9 % (24k) | 54.1 % (2k) | 52.7 % (3k) | 51.6 % (24k) | 52.0 % (24k) |
| USDJPY | 60 | 48.9 % (6k) | 53.7 % (6k) | 49.0 % (6k) | 51.0 % (6k) | 48.0 % (6k) | 56.0 % (1k) | 56.2 % (1k) | 53.8 % (6k) | 53.9 % (6k) |
| XAUUSD | 1 | 50.0 % (289k) | 50.2 % (289k) | 48.9 % (288k) | 51.1 % (288k) | 48.9 % (289k) | 52.8 % (22k) | 52.9 % (30k) | 51.1 % (287k) | 51.0 % (289k) |
| XAUUSD | 5 | 50.1 % (58k) | 50.1 % (58k) | 49.2 % (57k) | 50.8 % (57k) | 47.9 % (58k) | 53.1 % (4k) | 53.6 % (6k) | 51.0 % (58k) | 50.6 % (58k) |
| XAUUSD | 15 | 50.3 % (19k) | 50.7 % (19k) | 49.1 % (19k) | 50.9 % (19k) | 48.1 % (19k) | 55.0 % (2k) | 54.8 % (2k) | 51.3 % (19k) | 50.7 % (19k) |
| XAUUSD | 60 | 50.1 % (5k) | 50.6 % (5k) | 49.5 % (5k) | 50.5 % (5k) | 50.0 % (5k) | 50.7 % (0k) | 52.7 % (1k) | 51.5 % (5k) | 51.5 % (5k) |

## 5. Políticas selectivas (B = EV estimado ≥ margen; BN = B sin ventanas de noticias)

| Instrumento | h | Contrato | Modelo | Política | n | Acierto [IC95] | EV [IC95] | Máx. caída | p Holm |
|---|---|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | binaria | gbm | B | 2678 | 55.8 % [53.6 %, 57.9 %] | 0.025 [-0.001, 0.055] | 32.4 | 1.000 |
| AUDUSD | 1 | binaria | gbm | BN | 2526 | 56.0 % [53.9 %, 58.2 %] | 0.029 [0.002, 0.060] | 33.3 | 1.000 |
| AUDUSD | 1 | binaria | logit | B | 807 | 55.5 % [51.6 %, 59.3 %] | 0.021 [-0.046, 0.091] | 23.5 | 1.000 |
| AUDUSD | 1 | binaria | logit | BN | 788 | 55.6 % [51.6 %, 59.5 %] | 0.022 [-0.043, 0.089] | 21.5 | 1.000 |
| AUDUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | binaria | gbm | B | 3168 | 54.5 % [52.7 %, 56.3 %] | 0.008 [-0.018, 0.037] | 28.9 | 1.000 |
| AUDUSD | 5 | binaria | gbm | BN | 2834 | 54.6 % [52.8 %, 56.5 %] | 0.010 [-0.021, 0.041] | 37.6 | 1.000 |
| AUDUSD | 5 | binaria | logit | B | 2513 | 52.7 % [50.7 %, 54.7 %] | -0.024 [-0.059, 0.009] | 80.4 | 1.000 |
| AUDUSD | 5 | binaria | logit | BN | 2249 | 52.7 % [50.5 %, 54.8 %] | -0.024 [-0.060, 0.018] | 75.0 | 1.000 |
| AUDUSD | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | binaria | gbm | B | 1132 | 54.4 % [51.5 %, 57.3 %] | 0.007 [-0.040, 0.046] | 26.8 | 1.000 |
| AUDUSD | 15 | binaria | gbm | BN | 945 | 54.5 % [51.3 %, 57.7 %] | 0.008 [-0.043, 0.059] | 26.9 | 1.000 |
| AUDUSD | 15 | binaria | logit | B | 6 | 50.0 % [18.8 %, 81.2 %] | -0.075 [-0.383, 0.850] | 1.3 | 1.000 |
| AUDUSD | 15 | binaria | logit | BN | 6 | 50.0 % [18.8 %, 81.2 %] | -0.075 [-0.383, 0.850] | 1.3 | 1.000 |
| AUDUSD | 15 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | binaria | gbm | B | 308 | 55.4 % [49.8 %, 60.9 %] | 0.025 [-0.078, 0.124] | 16.0 | 1.000 |
| AUDUSD | 60 | binaria | gbm | BN | 189 | 62.8 % [55.7 %, 69.4 %] | 0.160 [0.050, 0.276] | 7.2 | 1.000 |
| AUDUSD | 60 | binaria | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | binaria | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | contado | gbm | B | 14 | 28.6 % [11.7 %, 54.6 %] | -5.726 [-14.942, 5.838] | 124.1 | 1.000 |
| AUDUSD | 60 | contado | gbm | BN | 8 | 12.5 % [2.2 %, 47.1 %] | -11.356 [-21.935, -6.692] | 90.8 | 1.000 |
| AUDUSD | 60 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | binaria | gbm | B | 58386 | 56.4 % [56.0 %, 56.8 %] | 0.039 [0.028, 0.050] | 280.4 | 0.000 |
| BTCUSDT | 1 | binaria | gbm | BN | 55955 | 56.5 % [56.1 %, 56.9 %] | 0.041 [0.030, 0.052] | 264.7 | 0.000 |
| BTCUSDT | 1 | binaria | logit | B | 14133 | 53.0 % [52.2 %, 53.9 %] | -0.017 [-0.031, -0.002] | 352.8 | 1.000 |
| BTCUSDT | 1 | binaria | logit | BN | 13283 | 53.0 % [52.1 %, 53.9 %] | -0.018 [-0.032, -0.002] | 326.1 | 1.000 |
| BTCUSDT | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | binaria | gbm | B | 4678 | 53.8 % [52.3 %, 55.2 %] | -0.005 [-0.032, 0.021] | 125.8 | 1.000 |
| BTCUSDT | 5 | binaria | gbm | BN | 4313 | 53.7 % [52.2 %, 55.2 %] | -0.006 [-0.035, 0.023] | 114.5 | 1.000 |
| BTCUSDT | 5 | binaria | logit | B | 6939 | 54.5 % [53.3 %, 55.7 %] | 0.008 [-0.016, 0.030] | 71.7 | 1.000 |
| BTCUSDT | 5 | binaria | logit | BN | 6240 | 54.5 % [53.2 %, 55.7 %] | 0.008 [-0.014, 0.030] | 81.3 | 1.000 |
| BTCUSDT | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | binaria | gbm | B | 2252 | 54.4 % [52.3 %, 56.4 %] | 0.006 [-0.030, 0.039] | 36.8 | 1.000 |
| BTCUSDT | 15 | binaria | gbm | BN | 1988 | 54.0 % [51.8 %, 56.2 %] | -0.001 [-0.038, 0.039] | 39.9 | 1.000 |
| BTCUSDT | 15 | binaria | logit | B | 4187 | 54.4 % [52.9 %, 55.9 %] | 0.006 [-0.021, 0.031] | 73.3 | 1.000 |
| BTCUSDT | 15 | binaria | logit | BN | 3681 | 54.7 % [53.0 %, 56.3 %] | 0.011 [-0.018, 0.039] | 80.7 | 1.000 |
| BTCUSDT | 15 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | binaria | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | binaria | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | binaria | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | binaria | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | binaria | gbm | B | 1523 | 51.9 % [49.2 %, 54.5 %] | -0.035 [-0.075, 0.004] | 71.2 | 1.000 |
| EURUSD | 1 | binaria | gbm | BN | 1386 | 52.3 % [49.5 %, 55.1 %] | -0.028 [-0.067, 0.011] | 55.3 | 1.000 |
| EURUSD | 1 | binaria | logit | B | 969 | 51.2 % [47.8 %, 54.6 %] | -0.046 [-0.103, 0.021] | 56.7 | 1.000 |
| EURUSD | 1 | binaria | logit | BN | 786 | 49.1 % [45.3 %, 52.9 %] | -0.078 [-0.150, -0.004] | 67.1 | 1.000 |
| EURUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | binaria | gbm | B | 2081 | 55.7 % [53.6 %, 57.9 %] | 0.030 [-0.011, 0.070] | 34.8 | 1.000 |
| EURUSD | 5 | binaria | gbm | BN | 1892 | 56.0 % [53.7 %, 58.2 %] | 0.034 [-0.011, 0.076] | 37.4 | 1.000 |
| EURUSD | 5 | binaria | logit | B | 900 | 52.3 % [49.0 %, 55.6 %] | -0.032 [-0.084, 0.022] | 35.7 | 1.000 |
| EURUSD | 5 | binaria | logit | BN | 802 | 52.4 % [48.9 %, 55.9 %] | -0.030 [-0.088, 0.028] | 33.7 | 1.000 |
| EURUSD | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 15 | binaria | gbm | B | 518 | 58.3 % [53.9 %, 62.5 %] | 0.076 [-0.001, 0.155] | 16.1 | 1.000 |
| EURUSD | 15 | binaria | gbm | BN | 447 | 60.7 % [56.1 %, 65.2 %] | 0.121 [0.035, 0.199] | 12.8 | 1.000 |
| EURUSD | 15 | binaria | logit | B | 1004 | 52.6 % [49.5 %, 55.7 %] | -0.026 [-0.085, 0.037] | 59.9 | 1.000 |
| EURUSD | 15 | binaria | logit | BN | 823 | 52.0 % [48.6 %, 55.5 %] | -0.036 [-0.099, 0.030] | 49.3 | 1.000 |
| EURUSD | 15 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 15 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 15 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 15 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | binaria | gbm | B | 5110 | 56.2 % [54.7 %, 57.6 %] | 0.034 [0.008, 0.059] | 36.2 | 1.000 |
| GBPUSD | 1 | binaria | gbm | BN | 4791 | 56.8 % [55.3 %, 58.3 %] | 0.044 [0.021, 0.069] | 37.1 | 0.113 |
| GBPUSD | 1 | binaria | logit | B | 2288 | 53.9 % [51.7 %, 56.1 %] | -0.002 [-0.037, 0.030] | 49.2 | 1.000 |
| GBPUSD | 1 | binaria | logit | BN | 2111 | 54.5 % [52.2 %, 56.8 %] | 0.007 [-0.031, 0.044] | 37.4 | 1.000 |
| GBPUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 5 | binaria | gbm | B | 1418 | 60.3 % [57.7 %, 62.9 %] | 0.110 [0.073, 0.152] | 10.2 | 0.001 |
| GBPUSD | 5 | binaria | gbm | BN | 1314 | 61.4 % [58.7 %, 64.1 %] | 0.130 [0.085, 0.176] | 9.9 | 0.000 |
| GBPUSD | 5 | binaria | logit | B | 431 | 58.6 % [53.8 %, 63.3 %] | 0.080 [-0.006, 0.169] | 12.6 | 1.000 |
| GBPUSD | 5 | binaria | logit | BN | 383 | 59.1 % [53.9 %, 64.0 %] | 0.087 [-0.003, 0.175] | 11.6 | 1.000 |
| GBPUSD | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 15 | binaria | gbm | B | 979 | 54.1 % [50.9 %, 57.2 %] | 0.001 [-0.059, 0.062] | 41.2 | 1.000 |
| GBPUSD | 15 | binaria | gbm | BN | 860 | 53.8 % [50.5 %, 57.2 %] | -0.004 [-0.062, 0.055] | 36.0 | 1.000 |
| GBPUSD | 15 | binaria | logit | B | 749 | 53.6 % [50.0 %, 57.1 %] | -0.009 [-0.080, 0.059] | 32.0 | 1.000 |
| GBPUSD | 15 | binaria | logit | BN | 596 | 54.6 % [50.5 %, 58.6 %] | 0.010 [-0.061, 0.082] | 26.3 | 1.000 |
| GBPUSD | 15 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 15 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 15 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 15 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | binaria | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | binaria | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | binaria | logit | B | 310 | 56.7 % [51.1 %, 62.1 %] | 0.048 [-0.038, 0.135] | 16.3 | 1.000 |
| GBPUSD | 60 | binaria | logit | BN | 187 | 54.3 % [47.1 %, 61.4 %] | 0.005 [-0.108, 0.138] | 8.2 | 1.000 |
| GBPUSD | 60 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | contado | logit | B | 4 | 0.0 % [0.0 %, 49.0 %] | -3.065 [-3.985, -2.681] | 12.3 | 1.000 |
| GBPUSD | 60 | contado | logit | BN | 4 | 0.0 % [0.0 %, 49.0 %] | -3.065 [-3.985, -2.681] | 12.3 | 1.000 |
| USDJPY | 1 | binaria | gbm | B | 5414 | 57.0 % [55.5 %, 58.5 %] | 0.043 [0.021, 0.064] | 22.4 | 0.040 |
| USDJPY | 1 | binaria | gbm | BN | 4926 | 57.3 % [55.7 %, 58.8 %] | 0.046 [0.023, 0.069] | 24.9 | 0.022 |
| USDJPY | 1 | binaria | logit | B | 4217 | 54.1 % [52.5 %, 55.7 %] | 0.001 [-0.026, 0.031] | 68.6 | 1.000 |
| USDJPY | 1 | binaria | logit | BN | 3849 | 54.9 % [53.2 %, 56.6 %] | 0.014 [-0.013, 0.043] | 48.7 | 1.000 |
| USDJPY | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 5 | binaria | gbm | B | 3888 | 54.9 % [53.3 %, 56.5 %] | 0.015 [-0.017, 0.045] | 58.1 | 1.000 |
| USDJPY | 5 | binaria | gbm | BN | 3481 | 54.9 % [53.2 %, 56.6 %] | 0.015 [-0.019, 0.048] | 52.1 | 1.000 |
| USDJPY | 5 | binaria | logit | B | 6055 | 55.6 % [54.3 %, 56.8 %] | 0.027 [0.005, 0.050] | 45.0 | 1.000 |
| USDJPY | 5 | binaria | logit | BN | 5533 | 55.8 % [54.5 %, 57.2 %] | 0.032 [0.010, 0.056] | 42.0 | 1.000 |
| USDJPY | 5 | contado | gbm | B | 10 | 40.0 % [16.8 %, 68.7 %] | -1.368 [-2.128, 0.406] | 34.5 | 1.000 |
| USDJPY | 5 | contado | gbm | BN | 9 | 44.4 % [18.9 %, 73.3 %] | -1.471 [-2.410, 0.406] | 34.5 | 1.000 |
| USDJPY | 5 | contado | logit | B | 7 | 57.1 % [25.0 %, 84.2 %] | 0.712 [0.703, 0.716] | 3.7 | 0.615 |
| USDJPY | 5 | contado | logit | BN | 6 | 66.7 % [30.0 %, 90.3 %] | 1.449 [0.703, 1.822] | 2.4 | 0.615 |
| USDJPY | 15 | binaria | gbm | B | 1122 | 56.2 % [53.3 %, 59.1 %] | 0.039 [-0.005, 0.085] | 16.8 | 1.000 |
| USDJPY | 15 | binaria | gbm | BN | 955 | 55.9 % [52.7 %, 59.1 %] | 0.034 [-0.011, 0.080] | 11.7 | 1.000 |
| USDJPY | 15 | binaria | logit | B | 752 | 58.8 % [55.2 %, 62.3 %] | 0.087 [0.028, 0.150] | 12.4 | 1.000 |
| USDJPY | 15 | binaria | logit | BN | 672 | 59.5 % [55.8 %, 63.2 %] | 0.101 [0.037, 0.169] | 14.9 | 1.000 |
| USDJPY | 15 | contado | gbm | B | 38 | 52.6 % [37.3 %, 67.5 %] | 0.350 [-0.062, 0.647] | 20.6 | 0.615 |
| USDJPY | 15 | contado | gbm | BN | 31 | 48.4 % [32.0 %, 65.2 %] | -0.587 [-1.392, -0.044] | 38.4 | 1.000 |
| USDJPY | 15 | contado | logit | B | 43 | 44.2 % [30.4 %, 58.9 %] | -2.618 [-9.043, 0.003] | 145.7 | 1.000 |
| USDJPY | 15 | contado | logit | BN | 39 | 38.5 % [24.9 %, 54.1 %] | -3.512 [-10.687, -0.519] | 165.8 | 1.000 |
| USDJPY | 60 | binaria | gbm | B | 815 | 56.4 % [52.9 %, 59.7 %] | 0.042 [-0.019, 0.107] | 16.0 | 1.000 |
| USDJPY | 60 | binaria | gbm | BN | 470 | 57.8 % [53.3 %, 62.3 %] | 0.069 [-0.019, 0.153] | 10.6 | 1.000 |
| USDJPY | 60 | binaria | logit | B | 670 | 59.9 % [56.2 %, 63.6 %] | 0.108 [0.047, 0.168] | 8.0 | 0.784 |
| USDJPY | 60 | binaria | logit | BN | 410 | 61.2 % [56.4 %, 65.9 %] | 0.131 [0.048, 0.214] | 6.7 | 1.000 |
| USDJPY | 60 | contado | gbm | B | 254 | 56.7 % [50.5 %, 62.6 %] | -0.880 [-2.701, 0.699] | 405.4 | 1.000 |
| USDJPY | 60 | contado | gbm | BN | 154 | 57.8 % [49.9 %, 65.3 %] | -0.240 [-2.383, 1.872] | 262.3 | 1.000 |
| USDJPY | 60 | contado | logit | B | 310 | 54.5 % [49.0 %, 60.0 %] | -0.617 [-2.013, 0.504] | 318.1 | 1.000 |
| USDJPY | 60 | contado | logit | BN | 182 | 54.9 % [47.7 %, 62.0 %] | 0.261 [-1.358, 1.633] | 155.4 | 1.000 |
| XAUUSD | 1 | binaria | gbm | B | 5644 | 54.1 % [52.8 %, 55.4 %] | 0.001 [-0.023, 0.027] | 75.3 | 1.000 |
| XAUUSD | 1 | binaria | gbm | BN | 5210 | 53.8 % [52.5 %, 55.2 %] | -0.004 [-0.029, 0.023] | 85.5 | 1.000 |
| XAUUSD | 1 | binaria | logit | B | 3835 | 55.2 % [53.6 %, 56.8 %] | 0.021 [-0.006, 0.045] | 34.0 | 1.000 |
| XAUUSD | 1 | binaria | logit | BN | 3523 | 55.2 % [53.5 %, 56.8 %] | 0.020 [-0.007, 0.047] | 32.8 | 1.000 |
| XAUUSD | 1 | contado | gbm | B | 524 | 51.3 % [47.1 %, 55.6 %] | 0.704 [-0.937, 2.601] | 425.5 | 1.000 |
| XAUUSD | 1 | contado | gbm | BN | 487 | 51.3 % [46.9 %, 55.7 %] | 0.886 [-0.618, 2.749] | 412.6 | 1.000 |
| XAUUSD | 1 | contado | logit | B | 161 | 52.2 % [44.5 %, 59.7 %] | 0.509 [-1.308, 6.258] | 189.7 | 1.000 |
| XAUUSD | 1 | contado | logit | BN | 154 | 51.3 % [43.5 %, 59.1 %] | 0.318 [-1.467, 5.967] | 189.2 | 1.000 |
| XAUUSD | 5 | binaria | gbm | B | 515 | 53.1 % [48.8 %, 57.4 %] | -0.017 [-0.084, 0.054] | 25.4 | 1.000 |
| XAUUSD | 5 | binaria | gbm | BN | 471 | 51.9 % [47.4 %, 56.4 %] | -0.039 [-0.112, 0.034] | 29.9 | 1.000 |
| XAUUSD | 5 | binaria | logit | B | 262 | 56.3 % [50.3 %, 62.2 %] | 0.042 [-0.067, 0.153] | 10.9 | 1.000 |
| XAUUSD | 5 | binaria | logit | BN | 240 | 57.3 % [51.0 %, 63.4 %] | 0.060 [-0.041, 0.168] | 8.1 | 1.000 |
| XAUUSD | 5 | contado | gbm | B | 1112 | 48.5 % [45.5 %, 51.4 %] | -0.552 [-1.216, 0.163] | 899.6 | 1.000 |
| XAUUSD | 5 | contado | gbm | BN | 1024 | 48.6 % [45.6 %, 51.7 %] | -0.506 [-1.229, 0.183] | 802.0 | 1.000 |
| XAUUSD | 5 | contado | logit | B | 647 | 51.5 % [47.6 %, 55.3 %] | 0.091 [-1.656, 2.071] | 875.3 | 1.000 |
| XAUUSD | 5 | contado | logit | BN | 604 | 51.7 % [47.7 %, 55.6 %] | -0.099 [-2.190, 1.922] | 835.8 | 1.000 |
| XAUUSD | 15 | binaria | gbm | B | 592 | 52.4 % [48.3 %, 56.4 %] | -0.031 [-0.106, 0.039] | 22.5 | 1.000 |
| XAUUSD | 15 | binaria | gbm | BN | 514 | 51.8 % [47.4 %, 56.0 %] | -0.043 [-0.121, 0.032] | 28.0 | 1.000 |
| XAUUSD | 15 | binaria | logit | B | 2305 | 50.8 % [48.8 %, 52.9 %] | -0.059 [-0.089, -0.030] | 151.3 | 1.000 |
| XAUUSD | 15 | binaria | logit | BN | 1939 | 50.6 % [48.4 %, 52.8 %] | -0.064 [-0.097, -0.030] | 139.8 | 1.000 |
| XAUUSD | 15 | contado | gbm | B | 2172 | 51.8 % [49.7 %, 53.9 %] | 0.023 [-1.156, 1.130] | 1696.8 | 1.000 |
| XAUUSD | 15 | contado | gbm | BN | 1858 | 51.8 % [49.5 %, 54.0 %] | 0.211 [-0.916, 1.213] | 1099.9 | 1.000 |
| XAUUSD | 15 | contado | logit | B | 3896 | 50.5 % [48.9 %, 52.0 %] | -0.570 [-1.281, 0.199] | 3373.0 | 1.000 |
| XAUUSD | 15 | contado | logit | BN | 3250 | 50.6 % [48.8 %, 52.3 %] | -0.644 [-1.458, 0.155] | 3406.0 | 1.000 |
| XAUUSD | 60 | binaria | gbm | B | 1109 | 54.0 % [51.0 %, 56.9 %] | -0.002 [-0.048, 0.047] | 26.9 | 1.000 |
| XAUUSD | 60 | binaria | gbm | BN | 617 | 55.0 % [51.1 %, 58.9 %] | 0.018 [-0.048, 0.081] | 16.6 | 1.000 |
| XAUUSD | 60 | binaria | logit | B | 1109 | 54.0 % [51.0 %, 56.9 %] | -0.002 [-0.048, 0.047] | 26.9 | 1.000 |
| XAUUSD | 60 | binaria | logit | BN | 617 | 55.0 % [51.1 %, 58.9 %] | 0.018 [-0.048, 0.081] | 16.6 | 1.000 |
| XAUUSD | 60 | contado | gbm | B | 3221 | 49.0 % [47.3 %, 50.7 %] | -1.099 [-2.436, 0.068] | 4573.9 | 1.000 |
| XAUUSD | 60 | contado | gbm | BN | 1762 | 47.4 % [45.1 %, 49.8 %] | -0.817 [-2.521, 0.914] | 3124.6 | 1.000 |
| XAUUSD | 60 | contado | logit | B | 3221 | 49.0 % [47.3 %, 50.7 %] | -1.099 [-2.436, 0.068] | 4573.9 | 1.000 |
| XAUUSD | 60 | contado | logit | BN | 1762 | 47.4 % [45.1 %, 49.8 %] | -0.817 [-2.521, 0.914] | 3124.6 | 1.000 |

Unidades: binaria en unidades de apuesta; contado en puntos básicos (pb).

## 6. ¿Se alcanza un acierto ≥ 80%?

Mejor acierto en cualquier nivel de cobertura (umbral fijado con el tramo de calibración, n ≥ 100), sin costos.

| Instrumento | h | Modelo | Mejor acierto | IC95 | n | Cobertura | ¿≥ objetivo? |
|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | gbm | 56.3 % | [54.0 %, 58.5 %] | 1809 | 0.55 % | no |
| AUDUSD | 1 | logit | 55.3 % | [51.3 %, 59.2 %] | 604 | 0.18 % | no |
| AUDUSD | 5 | gbm | 60.9 % | [56.0 %, 65.6 %] | 389 | 0.56 % | no |
| AUDUSD | 5 | logit | 52.8 % | [51.3 %, 54.3 %] | 4195 | 6.04 % | no |
| AUDUSD | 15 | gbm | 58.2 % | [54.7 %, 61.7 %] | 747 | 3.18 % | no |
| AUDUSD | 15 | logit | 65.5 % | [57.2 %, 72.9 %] | 139 | 0.59 % | no |
| AUDUSD | 60 | gbm | 54.8 % | [50.6 %, 59.0 %] | 538 | 9.20 % | no |
| AUDUSD | 60 | logit | 54.3 % | [51.1 %, 57.5 %] | 948 | 16.21 % | no |
| BTCUSDT | 1 | gbm | 62.4 % | [57.9 %, 66.8 %] | 450 | 0.09 % | no |
| BTCUSDT | 1 | logit | 54.8 % | [54.2 %, 55.4 %] | 25351 | 5.00 % | no |
| BTCUSDT | 5 | gbm | 53.9 % | [52.5 %, 55.2 %] | 5229 | 4.99 % | no |
| BTCUSDT | 5 | logit | 55.2 % | [52.3 %, 58.0 %] | 1161 | 1.11 % | no |
| BTCUSDT | 15 | gbm | 54.9 % | [53.2 %, 56.6 %] | 3364 | 9.61 % | no |
| BTCUSDT | 15 | logit | 59.6 % | [54.3 %, 64.7 %] | 337 | 0.96 % | no |
| BTCUSDT | 60 | gbm | 50.8 % | [47.9 %, 53.8 %] | 1106 | 12.63 % | no |
| BTCUSDT | 60 | logit | 52.6 % | [50.4 %, 54.9 %] | 1869 | 21.35 % | no |
| EURUSD | 1 | gbm | 51.6 % | [51.1 %, 52.0 %] | 41783 | 12.66 % | no |
| EURUSD | 1 | logit | 51.4 % | [50.7 %, 52.1 %] | 22417 | 6.79 % | no |
| EURUSD | 5 | gbm | 57.4 % | [53.1 %, 61.6 %] | 526 | 0.75 % | no |
| EURUSD | 5 | logit | 54.1 % | [51.5 %, 56.7 %] | 1419 | 2.04 % | no |
| EURUSD | 15 | gbm | 60.2 % | [53.7 %, 66.3 %] | 231 | 0.98 % | no |
| EURUSD | 15 | logit | 53.8 % | [52.4 %, 55.2 %] | 4741 | 20.19 % | no |
| EURUSD | 60 | gbm | 55.3 % | [51.5 %, 59.2 %] | 636 | 10.84 % | no |
| EURUSD | 60 | logit | 54.1 % | [50.9 %, 57.3 %] | 929 | 15.83 % | no |
| GBPUSD | 1 | gbm | 61.4 % | [57.8 %, 64.8 %] | 733 | 0.22 % | no |
| GBPUSD | 1 | logit | 57.8 % | [54.1 %, 61.5 %] | 688 | 0.21 % | no |
| GBPUSD | 5 | gbm | 53.5 % | [52.2 %, 54.7 %] | 6001 | 8.59 % | no |
| GBPUSD | 5 | logit | 59.2 % | [50.2 %, 67.5 %] | 120 | 0.17 % | no |
| GBPUSD | 15 | gbm | 54.8 % | [52.1 %, 57.6 %] | 1255 | 5.34 % | no |
| GBPUSD | 15 | logit | 55.0 % | [52.2 %, 57.8 %] | 1214 | 5.16 % | no |
| GBPUSD | 60 | gbm | 53.1 % | [51.3 %, 54.9 %] | 2987 | 51.01 % | no |
| GBPUSD | 60 | logit | 52.5 % | [50.9 %, 54.1 %] | 3708 | 63.32 % | no |
| USDJPY | 1 | gbm | 57.7 % | [52.5 %, 62.7 %] | 357 | 0.11 % | no |
| USDJPY | 1 | logit | 54.5 % | [53.4 %, 55.5 %] | 8801 | 2.63 % | no |
| USDJPY | 5 | gbm | 56.8 % | [55.0 %, 58.5 %] | 3029 | 4.31 % | no |
| USDJPY | 5 | logit | 55.3 % | [52.2 %, 58.4 %] | 1000 | 1.42 % | no |
| USDJPY | 15 | gbm | 52.1 % | [51.1 %, 53.0 %] | 10782 | 45.59 % | no |
| USDJPY | 15 | logit | 59.3 % | [51.8 %, 66.4 %] | 172 | 0.73 % | no |
| USDJPY | 60 | gbm | 54.9 % | [52.8 %, 57.0 %] | 2143 | 36.38 % | no |
| USDJPY | 60 | logit | 57.9 % | [55.0 %, 60.8 %] | 1129 | 19.16 % | no |
| XAUUSD | 1 | gbm | 54.8 % | [52.2 %, 57.4 %] | 1389 | 0.48 % | no |
| XAUUSD | 1 | logit | 56.7 % | [52.8 %, 60.6 %] | 624 | 0.21 % | no |
| XAUUSD | 5 | gbm | 53.8 % | [51.5 %, 56.1 %] | 1754 | 3.02 % | no |
| XAUUSD | 5 | logit | 53.8 % | [52.6 %, 55.0 %] | 6288 | 10.84 % | no |
| XAUUSD | 15 | gbm | 52.7 % | [50.5 %, 54.9 %] | 1949 | 10.16 % | no |
| XAUUSD | 15 | logit | 54.0 % | [51.4 %, 56.6 %] | 1408 | 7.34 % | no |
| XAUUSD | 60 | gbm | 50.5 % | [48.9 %, 52.2 %] | 3442 | 74.74 % | no |
| XAUUSD | 60 | logit | 50.5 % | [48.9 %, 52.2 %] | 3442 | 74.74 % | no |

## 7. Calibración fuera de muestra (P(sube))

| Instrumento | h | Modelo | ECE | Brier | Brier ref. (0,5) | n |
|---|---|---|---|---|---|---|
| AUDUSD | 1 | logit | 0.39 % | 0.24993 | 0,25000 | 327,887 |
| AUDUSD | 1 | gbm | 0.42 % | 0.24994 | 0,25000 | 327,887 |
| AUDUSD | 5 | logit | 0.99 % | 0.24989 | 0,25000 | 69,469 |
| AUDUSD | 5 | gbm | 0.70 % | 0.24990 | 0,25000 | 69,469 |
| AUDUSD | 15 | logit | 1.27 % | 0.24985 | 0,25000 | 23,462 |
| AUDUSD | 15 | gbm | 1.50 % | 0.24990 | 0,25000 | 23,462 |
| AUDUSD | 60 | logit | 1.79 % | 0.25000 | 0,25000 | 5,850 |
| AUDUSD | 60 | gbm | 1.57 % | 0.24974 | 0,25000 | 5,850 |
| BTCUSDT | 1 | logit | 0.53 % | 0.24975 | 0,25000 | 507,304 |
| BTCUSDT | 1 | gbm | 0.44 % | 0.24929 | 0,25000 | 507,304 |
| BTCUSDT | 5 | logit | 0.45 % | 0.24970 | 0,25000 | 104,735 |
| BTCUSDT | 5 | gbm | 0.56 % | 0.24979 | 0,25000 | 104,735 |
| BTCUSDT | 15 | logit | 0.91 % | 0.24938 | 0,25000 | 35,012 |
| BTCUSDT | 15 | gbm | 0.64 % | 0.24969 | 0,25000 | 35,012 |
| BTCUSDT | 60 | logit | 1.58 % | 0.24972 | 0,25000 | 8,754 |
| BTCUSDT | 60 | gbm | 1.25 % | 0.25010 | 0,25000 | 8,754 |
| EURUSD | 1 | logit | 0.46 % | 0.24997 | 0,25000 | 330,096 |
| EURUSD | 1 | gbm | 0.26 % | 0.24995 | 0,25000 | 330,096 |
| EURUSD | 5 | logit | 0.88 % | 0.24990 | 0,25000 | 69,691 |
| EURUSD | 5 | gbm | 1.07 % | 0.25000 | 0,25000 | 69,691 |
| EURUSD | 15 | logit | 0.74 % | 0.24973 | 0,25000 | 23,483 |
| EURUSD | 15 | gbm | 1.05 % | 0.24983 | 0,25000 | 23,483 |
| EURUSD | 60 | logit | 1.63 % | 0.24995 | 0,25000 | 5,867 |
| EURUSD | 60 | gbm | 1.94 % | 0.24973 | 0,25000 | 5,867 |
| GBPUSD | 1 | logit | 0.47 % | 0.24993 | 0,25000 | 333,135 |
| GBPUSD | 1 | gbm | 0.60 % | 0.24994 | 0,25000 | 333,135 |
| GBPUSD | 5 | logit | 0.61 % | 0.24991 | 0,25000 | 69,861 |
| GBPUSD | 5 | gbm | 0.78 % | 0.24979 | 0,25000 | 69,861 |
| GBPUSD | 15 | logit | 1.07 % | 0.24969 | 0,25000 | 23,519 |
| GBPUSD | 15 | gbm | 1.14 % | 0.24979 | 0,25000 | 23,519 |
| GBPUSD | 60 | logit | 1.62 % | 0.24953 | 0,25000 | 5,856 |
| GBPUSD | 60 | gbm | 1.20 % | 0.24941 | 0,25000 | 5,856 |
| USDJPY | 1 | logit | 0.38 % | 0.24976 | 0,25000 | 335,005 |
| USDJPY | 1 | gbm | 0.31 % | 0.24974 | 0,25000 | 335,005 |
| USDJPY | 5 | logit | 0.76 % | 0.24952 | 0,25000 | 70,223 |
| USDJPY | 5 | gbm | 0.54 % | 0.24947 | 0,25000 | 70,223 |
| USDJPY | 15 | logit | 0.78 % | 0.24940 | 0,25000 | 23,649 |
| USDJPY | 15 | gbm | 0.84 % | 0.24946 | 0,25000 | 23,649 |
| USDJPY | 60 | logit | 1.38 % | 0.24806 | 0,25000 | 5,891 |
| USDJPY | 60 | gbm | 1.73 % | 0.24826 | 0,25000 | 5,891 |
| XAUUSD | 1 | logit | 0.61 % | 0.24981 | 0,25000 | 290,354 |
| XAUUSD | 1 | gbm | 0.68 % | 0.24992 | 0,25000 | 290,354 |
| XAUUSD | 5 | logit | 0.91 % | 0.24990 | 0,25000 | 58,021 |
| XAUUSD | 5 | gbm | 1.28 % | 0.25000 | 0,25000 | 58,021 |
| XAUUSD | 15 | logit | 1.61 % | 0.24994 | 0,25000 | 19,179 |
| XAUUSD | 15 | gbm | 1.81 % | 0.25008 | 0,25000 | 19,179 |
| XAUUSD | 60 | logit | 3.64 % | 0.25055 | 0,25000 | 4,605 |
| XAUUSD | 60 | gbm | 3.64 % | 0.25055 | 0,25000 | 4,605 |

## 8. Sensibilidad (no son hipótesis nuevas)

| Instrumento | h | Contrato | Modelo | Variante | n | Acierto | EV |
|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | binaria | gbm | B_lat60 | 2674 | 53.6 % | -0.007 |
| AUDUSD | 1 | binaria | gbm | B_tieloss | 522 | 59.7 % | -0.050 |
| AUDUSD | 1 | binaria | logit | B_lat60 | 806 | 53.4 % | -0.009 |
| AUDUSD | 1 | binaria | logit | B_tieloss | 0 | — | — |
| AUDUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| AUDUSD | 5 | binaria | gbm | B_lat60 | 3167 | 54.0 % | -0.000 |
| AUDUSD | 5 | binaria | gbm | B_tieloss | 1327 | 56.0 % | -0.017 |
| AUDUSD | 5 | binaria | logit | B_lat60 | 2513 | 53.4 % | -0.012 |
| AUDUSD | 5 | binaria | logit | B_tieloss | 502 | 52.1 % | -0.086 |
| AUDUSD | 5 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 5 | contado | logit | B_lat60 | 0 | — | — |
| AUDUSD | 15 | binaria | gbm | B_lat60 | 1132 | 53.9 % | -0.003 |
| AUDUSD | 15 | binaria | gbm | B_tieloss | 861 | 55.6 % | 0.003 |
| AUDUSD | 15 | binaria | logit | B_lat60 | 6 | 50.0 % | -0.075 |
| AUDUSD | 15 | binaria | logit | B_tieloss | 0 | — | — |
| AUDUSD | 15 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 15 | contado | logit | B_lat60 | 0 | — | — |
| AUDUSD | 60 | binaria | gbm | B_lat60 | 308 | 56.2 % | 0.040 |
| AUDUSD | 60 | binaria | gbm | B_tieloss | 14 | 42.9 % | -0.207 |
| AUDUSD | 60 | binaria | logit | B_lat60 | 0 | — | — |
| AUDUSD | 60 | binaria | logit | B_tieloss | 0 | — | — |
| AUDUSD | 60 | contado | gbm | B_lat60 | 14 | 28.6 % | -7.307 |
| AUDUSD | 60 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 1 | binaria | gbm | B_lat60 | 58385 | 51.4 % | -0.044 |
| BTCUSDT | 1 | binaria | gbm | B_tieloss | 19440 | 55.6 % | -0.031 |
| BTCUSDT | 1 | binaria | logit | B_lat60 | 14133 | 51.8 % | -0.037 |
| BTCUSDT | 1 | binaria | logit | B_tieloss | 3763 | 53.4 % | -0.037 |
| BTCUSDT | 1 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 1 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 5 | binaria | gbm | B_lat60 | 4678 | 53.4 % | -0.012 |
| BTCUSDT | 5 | binaria | gbm | B_tieloss | 3945 | 54.0 % | -0.004 |
| BTCUSDT | 5 | binaria | logit | B_lat60 | 6939 | 54.2 % | 0.003 |
| BTCUSDT | 5 | binaria | logit | B_tieloss | 6221 | 54.6 % | 0.008 |
| BTCUSDT | 5 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 5 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 15 | binaria | gbm | B_lat60 | 2252 | 53.5 % | -0.010 |
| BTCUSDT | 15 | binaria | gbm | B_tieloss | 2209 | 54.5 % | 0.008 |
| BTCUSDT | 15 | binaria | logit | B_lat60 | 4187 | 54.1 % | 0.002 |
| BTCUSDT | 15 | binaria | logit | B_tieloss | 4081 | 54.5 % | 0.008 |
| BTCUSDT | 15 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 15 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 60 | binaria | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 60 | binaria | gbm | B_tieloss | 0 | — | — |
| BTCUSDT | 60 | binaria | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 60 | binaria | logit | B_tieloss | 0 | — | — |
| BTCUSDT | 60 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 60 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 1 | binaria | gbm | B_lat60 | 1523 | 50.6 % | -0.055 |
| EURUSD | 1 | binaria | gbm | B_tieloss | 0 | — | — |
| EURUSD | 1 | binaria | logit | B_lat60 | 969 | 49.8 % | -0.069 |
| EURUSD | 1 | binaria | logit | B_tieloss | 203 | 54.2 % | -0.116 |
| EURUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| EURUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 5 | binaria | gbm | B_lat60 | 2081 | 54.7 % | 0.011 |
| EURUSD | 5 | binaria | gbm | B_tieloss | 318 | 56.4 % | 0.006 |
| EURUSD | 5 | binaria | logit | B_lat60 | 900 | 52.8 % | -0.023 |
| EURUSD | 5 | binaria | logit | B_tieloss | 84 | 48.1 % | -0.141 |
| EURUSD | 5 | contado | gbm | B_lat60 | 0 | — | — |
| EURUSD | 5 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 15 | binaria | gbm | B_lat60 | 518 | 56.7 % | 0.047 |
| EURUSD | 15 | binaria | gbm | B_tieloss | 0 | — | — |
| EURUSD | 15 | binaria | logit | B_lat60 | 1004 | 53.0 % | -0.019 |
| EURUSD | 15 | binaria | logit | B_tieloss | 681 | 53.7 % | -0.022 |
| EURUSD | 15 | contado | gbm | B_lat60 | 0 | — | — |
| EURUSD | 15 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 60 | binaria | gbm | B_lat60 | 0 | — | — |
| EURUSD | 60 | binaria | gbm | B_tieloss | 0 | — | — |
| EURUSD | 60 | binaria | logit | B_lat60 | 0 | — | — |
| EURUSD | 60 | binaria | logit | B_tieloss | 0 | — | — |
| EURUSD | 60 | contado | gbm | B_lat60 | 0 | — | — |
| EURUSD | 60 | contado | logit | B_lat60 | 0 | — | — |
| GBPUSD | 1 | binaria | gbm | B_lat60 | 5104 | 54.3 % | 0.003 |
| GBPUSD | 1 | binaria | gbm | B_tieloss | 835 | 58.9 % | -0.140 |
| GBPUSD | 1 | binaria | logit | B_lat60 | 2288 | 52.5 % | -0.024 |
| GBPUSD | 1 | binaria | logit | B_tieloss | 57 | 58.5 % | 0.006 |
| GBPUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| GBPUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| GBPUSD | 5 | binaria | gbm | B_lat60 | 1418 | 58.4 % | 0.078 |
| GBPUSD | 5 | binaria | gbm | B_tieloss | 378 | 62.5 % | 0.111 |
| GBPUSD | 5 | binaria | logit | B_lat60 | 430 | 55.7 % | 0.029 |
| GBPUSD | 5 | binaria | logit | B_tieloss | 67 | 61.5 % | 0.104 |
| GBPUSD | 5 | contado | gbm | B_lat60 | 0 | — | — |
| GBPUSD | 5 | contado | logit | B_lat60 | 0 | — | — |
| GBPUSD | 15 | binaria | gbm | B_lat60 | 978 | 55.6 % | 0.028 |
| GBPUSD | 15 | binaria | gbm | B_tieloss | 592 | 54.2 % | -0.009 |
| GBPUSD | 15 | binaria | logit | B_lat60 | 749 | 53.4 % | -0.013 |
| GBPUSD | 15 | binaria | logit | B_tieloss | 551 | 53.1 % | -0.026 |
| GBPUSD | 15 | contado | gbm | B_lat60 | 0 | — | — |
| GBPUSD | 15 | contado | logit | B_lat60 | 0 | — | — |
| GBPUSD | 60 | binaria | gbm | B_lat60 | 0 | — | — |
| GBPUSD | 60 | binaria | gbm | B_tieloss | 0 | — | — |
| GBPUSD | 60 | binaria | logit | B_lat60 | 310 | 54.9 % | 0.015 |
| GBPUSD | 60 | binaria | logit | B_tieloss | 274 | 58.1 % | 0.067 |
| GBPUSD | 60 | contado | gbm | B_lat60 | 0 | — | — |
| GBPUSD | 60 | contado | logit | B_lat60 | 4 | 0.0 % | -3.210 |
| USDJPY | 1 | binaria | gbm | B_lat60 | 5400 | 54.6 % | 0.008 |
| USDJPY | 1 | binaria | gbm | B_tieloss | 1736 | 58.5 % | -0.156 |
| USDJPY | 1 | binaria | logit | B_lat60 | 4217 | 51.7 % | -0.039 |
| USDJPY | 1 | binaria | logit | B_tieloss | 13 | 46.2 % | -0.146 |
| USDJPY | 1 | contado | gbm | B_lat60 | 0 | — | — |
| USDJPY | 1 | contado | logit | B_lat60 | 0 | — | — |
| USDJPY | 5 | binaria | gbm | B_lat60 | 3888 | 54.5 % | 0.007 |
| USDJPY | 5 | binaria | gbm | B_tieloss | 966 | 58.1 % | 0.049 |
| USDJPY | 5 | binaria | logit | B_lat60 | 6055 | 55.1 % | 0.019 |
| USDJPY | 5 | binaria | logit | B_tieloss | 1904 | 55.6 % | 0.011 |
| USDJPY | 5 | contado | gbm | B_lat60 | 10 | 20.0 % | -6.334 |
| USDJPY | 5 | contado | logit | B_lat60 | 7 | 57.1 % | 0.292 |
| USDJPY | 15 | binaria | gbm | B_lat60 | 1122 | 56.0 % | 0.035 |
| USDJPY | 15 | binaria | gbm | B_tieloss | 779 | 56.2 % | 0.019 |
| USDJPY | 15 | binaria | logit | B_lat60 | 752 | 59.1 % | 0.092 |
| USDJPY | 15 | binaria | logit | B_tieloss | 540 | 60.6 % | 0.110 |
| USDJPY | 15 | contado | gbm | B_lat60 | 38 | 52.6 % | 0.100 |
| USDJPY | 15 | contado | logit | B_lat60 | 43 | 46.5 % | -2.156 |
| USDJPY | 60 | binaria | gbm | B_lat60 | 815 | 58.2 % | 0.075 |
| USDJPY | 60 | binaria | gbm | B_tieloss | 699 | 56.3 % | 0.035 |
| USDJPY | 60 | binaria | logit | B_lat60 | 670 | 60.2 % | 0.112 |
| USDJPY | 60 | binaria | logit | B_tieloss | 622 | 59.6 % | 0.095 |
| USDJPY | 60 | contado | gbm | B_lat60 | 254 | 55.9 % | -0.882 |
| USDJPY | 60 | contado | logit | B_lat60 | 310 | 55.8 % | -0.638 |
| XAUUSD | 1 | binaria | gbm | B_lat60 | 5626 | 52.0 % | -0.037 |
| XAUUSD | 1 | binaria | gbm | B_tieloss | 4949 | 54.1 % | -0.003 |
| XAUUSD | 1 | binaria | logit | B_lat60 | 3829 | 53.2 % | -0.016 |
| XAUUSD | 1 | binaria | logit | B_tieloss | 3421 | 55.3 % | 0.018 |
| XAUUSD | 1 | contado | gbm | B_lat60 | 523 | 48.0 % | -0.558 |
| XAUUSD | 1 | contado | logit | B_lat60 | 161 | 50.9 % | 1.793 |
| XAUUSD | 5 | binaria | gbm | B_lat60 | 515 | 49.5 % | -0.084 |
| XAUUSD | 5 | binaria | gbm | B_tieloss | 507 | 53.0 % | -0.026 |
| XAUUSD | 5 | binaria | logit | B_lat60 | 262 | 54.6 % | 0.010 |
| XAUUSD | 5 | binaria | logit | B_tieloss | 86 | 53.5 % | -0.010 |
| XAUUSD | 5 | contado | gbm | B_lat60 | 1112 | 46.3 % | -0.741 |
| XAUUSD | 5 | contado | logit | B_lat60 | 647 | 53.2 % | 0.961 |
| XAUUSD | 15 | binaria | gbm | B_lat60 | 592 | 51.9 % | -0.041 |
| XAUUSD | 15 | binaria | gbm | B_tieloss | 558 | 52.0 % | -0.039 |
| XAUUSD | 15 | binaria | logit | B_lat60 | 2305 | 50.5 % | -0.067 |
| XAUUSD | 15 | binaria | logit | B_tieloss | 2119 | 50.4 % | -0.068 |
| XAUUSD | 15 | contado | gbm | B_lat60 | 2172 | 51.0 % | 0.029 |
| XAUUSD | 15 | contado | logit | B_lat60 | 3896 | 49.1 % | -0.704 |
| XAUUSD | 60 | binaria | gbm | B_lat60 | 1109 | 53.4 % | -0.012 |
| XAUUSD | 60 | binaria | gbm | B_tieloss | 967 | 53.5 % | -0.011 |
| XAUUSD | 60 | binaria | logit | B_lat60 | 1109 | 53.4 % | -0.012 |
| XAUUSD | 60 | binaria | logit | B_tieloss | 967 | 53.5 % | -0.011 |
| XAUUSD | 60 | contado | gbm | B_lat60 | 3221 | 48.6 % | -1.129 |
| XAUUSD | 60 | contado | logit | B_lat60 | 3221 | 48.6 % | -1.129 |

## 9. Acierto alto ≠ rentabilidad (demostración)

Entradas al azar con objetivo de ganancia de 1σ y límite de pérdida de 10σ (σ = volatilidad a 15 min).

| Instrumento | n | Objetivo alcanzado («acierto») | Ganadoras netas de costos | EV neto (pb) | Ganancia media (pb) | Pérdida media (pb) |
|---|---|---|---|---|---|---|
