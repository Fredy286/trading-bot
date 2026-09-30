# Resultados empíricos — etapa `dev`

- Commit del código: `fa918a50dc04d7be3de25c8fac54bff0b3c021ba` — hash de configuración: `2bcecccbf2f9` — versión 0.1.0
- Hipótesis evaluadas (corrección de Holm sobre todas): **624**
- Contrato binario: pago 85%, empate = refund; contado: spread observado + comisión.

## 1. Veredicto mecánico

Configuraciones candidatas (deben superar además el periodo bloqueado y la observación en vivo):

| Instrumento | h | Contrato | Modelo | Política | n | Acierto [IC95] | EV [IC95] | p Holm |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1 | binaria | gbm | B | 217663 | 56.6 % [56.4 %, 56.8 %] | 0.044 [0.039, 0.049] | 0.0000 |
| BTCUSDT | 1 | binaria | gbm | BN | 206174 | 56.7 % [56.5 %, 56.9 %] | 0.045 [0.040, 0.050] | 0.0000 |
| BTCUSDT | 5 | binaria | gbm | B | 30704 | 55.2 % [54.6 %, 55.8 %] | 0.021 [0.009, 0.032] | 0.0186 |
| BTCUSDT | 5 | binaria | gbm | BN | 28265 | 55.4 % [54.8 %, 56.0 %] | 0.025 [0.014, 0.036] | 0.0014 |
| BTCUSDT | 15 | binaria | rsi14_extremes | A | 10294 | 57.9 % [56.9 %, 58.8 %] | 0.070 [0.054, 0.089] | 0.0000 |
| BTCUSDT | 15 | binaria | logit | B | 30856 | 56.0 % [55.4 %, 56.6 %] | 0.036 [0.026, 0.047] | 0.0000 |
| BTCUSDT | 15 | binaria | logit | BN | 27111 | 56.3 % [55.7 %, 56.9 %] | 0.041 [0.030, 0.052] | 0.0000 |
| BTCUSDT | 15 | binaria | gbm | BN | 14129 | 55.7 % [54.9 %, 56.5 %] | 0.030 [0.015, 0.046] | 0.0324 |
| BTCUSDT | 60 | binaria | logit | B | 5914 | 56.6 % [55.4 %, 57.9 %] | 0.048 [0.026, 0.070] | 0.0200 |
| BTCUSDT | 60 | binaria | logit | BN | 4147 | 57.5 % [55.9 %, 59.0 %] | 0.063 [0.039, 0.090] | 0.0036 |

Cuántas configuraciones (no de referencia) cumplen cada criterio por separado:

| Criterio | Cumplen | De |
|---|---|---|
| c1_min_trades | 431 | 528 |
| c2_above_breakeven | 28 | 528 |
| c3_holm | 10 | 528 |
| c4_stable | 29 | 528 |
| c5_beats_reference | 307 | 528 |

## 2. Calidad de datos

| Instrumento | Fuente | Precio | Minutos en sesión | Minutos cerrados | Min. sin ticks | Rellenados (sin ticks) | Spread mediano | Desde | Hasta |
|---|---|---|---|---|---|---|---|---|---|
| AUDUSD | histdata | BID (spread supuesto) | 2,065,630 | 909,530 | 14,495 | 14,495 | 0.000040 | 2021-01-03 | 2026-08-31 |
| BTCUSDT | binance | negociado (sin bid/ask) | 2,978,134 | 1,226 | 8 | 0 | 0.000000 | 2021-01-01 | 2026-08-31 |
| EURUSD | histdata | BID (spread supuesto) | 2,067,006 | 908,154 | 11,621 | 11,621 | 0.000020 | 2021-01-03 | 2026-08-31 |
| GBPUSD | histdata | BID (spread supuesto) | 2,065,448 | 909,712 | 11,324 | 11,324 | 0.000050 | 2021-01-03 | 2026-08-31 |
| USDJPY | histdata | BID (spread supuesto) | 2,065,530 | 909,630 | 10,688 | 10,688 | 0.003000 | 2021-01-03 | 2026-08-31 |
| XAUUSD | histdata | BID (spread supuesto) | 1,961,712 | 1,013,388 | 518 | 518 | 0.250000 | 2021-01-03 | 2026-08-31 |

## 3. Movimiento típico frente a costos (periodo de prueba)

Umbral de contado `p* ≈ 0,5 + costo/(2·movimiento)`; si supera 100 % es inalcanzable.

| Instrumento | h (min) | Mov. medio abs. (pb) | Costo medio ida y vuelta (pb) | p* contado | Empates |
|---|---|---|---|---|---|
| AUDUSD | 1 | 1.22 | 1.65 | 117.7 % (inalcanzable) | 7.4 % |
| AUDUSD | 5 | 2.81 | 1.65 | 79.5 % | 2.6 % |
| AUDUSD | 15 | 4.88 | 1.65 | 66.9 % | 1.3 % |
| AUDUSD | 60 | 9.74 | 1.65 | 58.5 % | 0.7 % |
| BTCUSDT | 1 | 4.42 | 20.00 | 276.3 % (inalcanzable) | 2.6 % |
| BTCUSDT | 5 | 9.95 | 20.00 | 150.5 % (inalcanzable) | 0.3 % |
| BTCUSDT | 15 | 17.45 | 20.00 | 107.3 % (inalcanzable) | 0.0 % |
| BTCUSDT | 60 | 34.64 | 20.00 | 78.9 % | 0.0 % |
| EURUSD | 1 | 0.87 | 0.84 | 97.8 % | 7.7 % |
| EURUSD | 5 | 2.00 | 0.84 | 70.8 % | 2.8 % |
| EURUSD | 15 | 3.49 | 0.84 | 62.0 % | 1.4 % |
| EURUSD | 60 | 6.95 | 0.84 | 56.0 % | 0.7 % |
| GBPUSD | 1 | 0.95 | 0.95 | 99.9 % | 6.5 % |
| GBPUSD | 5 | 2.18 | 0.95 | 71.8 % | 2.3 % |
| GBPUSD | 15 | 3.81 | 0.95 | 62.5 % | 1.1 % |
| GBPUSD | 60 | 7.59 | 0.95 | 56.3 % | 0.5 % |
| USDJPY | 1 | 1.04 | 0.70 | 83.9 % | 5.5 % |
| USDJPY | 5 | 2.40 | 0.70 | 64.7 % | 1.8 % |
| USDJPY | 15 | 4.21 | 0.70 | 58.4 % | 0.9 % |
| USDJPY | 60 | 8.43 | 0.70 | 54.2 % | 0.4 % |
| XAUUSD | 1 | 1.66 | 1.48 | 94.4 % | 1.4 % |
| XAUUSD | 5 | 3.73 | 1.48 | 69.8 % | 0.4 % |
| XAUUSD | 15 | 6.48 | 1.48 | 61.4 % | 0.2 % |
| XAUUSD | 60 | 13.29 | 1.48 | 55.6 % | 0.1 % |

### Sensibilidad del umbral de contado al costo total ida y vuelta

Calculado con el movimiento medio medido; no depende del spread supuesto. Referencia: 1 pip de EUR/USD ≈ 0,9 pb.

| Instrumento | h | costo 0.5 pb | costo 1 pb | costo 2 pb | costo 5 pb | costo 10 pb |
|---|---|---|---|---|---|---|
| AUDUSD | 1 | 70.5 % | 91.0 % | inalcanzable | inalcanzable | inalcanzable |
| AUDUSD | 5 | 58.9 % | 67.8 % | 85.6 % | inalcanzable | inalcanzable |
| AUDUSD | 15 | 55.1 % | 60.2 % | 70.5 % | inalcanzable | inalcanzable |
| AUDUSD | 60 | 52.6 % | 55.1 % | 60.3 % | 75.7 % | inalcanzable |
| BTCUSDT | 1 | 55.7 % | 61.3 % | 72.6 % | inalcanzable | inalcanzable |
| BTCUSDT | 5 | 52.5 % | 55.0 % | 60.0 % | 75.1 % | inalcanzable |
| BTCUSDT | 15 | 51.4 % | 52.9 % | 55.7 % | 64.3 % | 78.7 % |
| BTCUSDT | 60 | 50.7 % | 51.4 % | 52.9 % | 57.2 % | 64.4 % |
| EURUSD | 1 | 78.6 % | inalcanzable | inalcanzable | inalcanzable | inalcanzable |
| EURUSD | 5 | 62.5 % | 75.0 % | 99.9 % | inalcanzable | inalcanzable |
| EURUSD | 15 | 57.2 % | 64.3 % | 78.6 % | inalcanzable | inalcanzable |
| EURUSD | 60 | 53.6 % | 57.2 % | 64.4 % | 86.0 % | inalcanzable |
| GBPUSD | 1 | 76.2 % | inalcanzable | inalcanzable | inalcanzable | inalcanzable |
| GBPUSD | 5 | 61.5 % | 72.9 % | 95.9 % | inalcanzable | inalcanzable |
| GBPUSD | 15 | 56.6 % | 63.1 % | 76.3 % | inalcanzable | inalcanzable |
| GBPUSD | 60 | 53.3 % | 56.6 % | 63.2 % | 82.9 % | inalcanzable |
| USDJPY | 1 | 74.0 % | 98.1 % | inalcanzable | inalcanzable | inalcanzable |
| USDJPY | 5 | 60.4 % | 70.8 % | 91.6 % | inalcanzable | inalcanzable |
| USDJPY | 15 | 55.9 % | 61.9 % | 73.8 % | inalcanzable | inalcanzable |
| USDJPY | 60 | 53.0 % | 55.9 % | 61.9 % | 79.7 % | inalcanzable |
| XAUUSD | 1 | 65.0 % | 80.0 % | inalcanzable | inalcanzable | inalcanzable |
| XAUUSD | 5 | 56.7 % | 63.4 % | 76.8 % | inalcanzable | inalcanzable |
| XAUUSD | 15 | 53.9 % | 57.7 % | 65.4 % | 88.6 % | inalcanzable |
| XAUUSD | 60 | 51.9 % | 53.8 % | 57.5 % | 68.8 % | 87.6 % |

## 4. Acierto fuera de muestra — contrato binario, política A (operar todo)

Umbral con pago 85%: **54.05 %**. Celdas: acierto (n en miles).

| Instrumento | h | random | majority | momentum1 | reversal1 | sma20_trend | rsi14_extremes | boll_reversal | logit | gbm |
|---|---|---|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | 50.0 % (1196k) | 50.2 % (1196k) | 49.6 % (1114k) | 50.4 % (1114k) | 49.4 % (1195k) | 51.5 % (106k) | 51.4 % (124k) | 50.6 % (1196k) | 50.6 % (1196k) |
| AUDUSD | 5 | 49.9 % (239k) | 50.3 % (239k) | 49.5 % (224k) | 50.5 % (224k) | 49.1 % (239k) | 52.6 % (21k) | 52.2 % (26k) | 50.8 % (239k) | 50.6 % (234k) |
| AUDUSD | 15 | 50.1 % (79k) | 50.2 % (79k) | 49.5 % (75k) | 50.5 % (75k) | 49.2 % (79k) | 53.1 % (7k) | 53.0 % (9k) | 50.5 % (79k) | 50.7 % (79k) |
| AUDUSD | 60 | 50.3 % (20k) | 49.2 % (20k) | 49.2 % (19k) | 50.8 % (19k) | 48.9 % (20k) | 55.9 % (2k) | 55.1 % (3k) | 51.3 % (20k) | 51.5 % (19k) |
| BTCUSDT | 1 | 50.0 % (1909k) | 50.0 % (1909k) | 50.6 % (1856k) | 49.4 % (1856k) | 49.7 % (1908k) | 52.8 % (163k) | 52.7 % (196k) | 51.3 % (1904k) | 52.0 % (1908k) |
| BTCUSDT | 5 | 50.0 % (382k) | 50.0 % (382k) | 49.7 % (373k) | 50.3 % (373k) | 48.8 % (382k) | 54.9 % (32k) | 53.3 % (38k) | 51.6 % (382k) | 51.6 % (380k) |
| BTCUSDT | 15 | 50.1 % (127k) | 50.2 % (127k) | 49.3 % (125k) | 50.7 % (125k) | 47.2 % (127k) | 57.9 % (10k) | 55.6 % (12k) | 52.9 % (127k) | 52.3 % (127k) |
| BTCUSDT | 60 | 50.4 % (32k) | 51.1 % (32k) | 50.0 % (31k) | 50.0 % (31k) | 47.6 % (32k) | 56.6 % (3k) | 53.4 % (3k) | 53.0 % (32k) | 51.7 % (32k) |
| EURUSD | 1 | 50.0 % (1198k) | 50.5 % (1198k) | 49.6 % (1106k) | 50.4 % (1106k) | 49.6 % (1197k) | 51.6 % (108k) | 51.2 % (124k) | 50.6 % (1196k) | 50.6 % (1197k) |
| EURUSD | 5 | 49.9 % (239k) | 50.0 % (239k) | 49.5 % (223k) | 50.5 % (223k) | 49.2 % (239k) | 52.7 % (22k) | 52.5 % (26k) | 50.8 % (239k) | 50.6 % (239k) |
| EURUSD | 15 | 50.0 % (79k) | 50.2 % (79k) | 49.7 % (75k) | 50.3 % (75k) | 48.8 % (79k) | 53.4 % (7k) | 52.5 % (9k) | 51.2 % (79k) | 51.1 % (79k) |
| EURUSD | 60 | 50.6 % (20k) | 50.4 % (20k) | 49.4 % (19k) | 50.6 % (19k) | 48.2 % (20k) | 50.9 % (2k) | 52.3 % (3k) | 50.4 % (18k) | 50.7 % (20k) |
| GBPUSD | 1 | 50.0 % (1196k) | 50.3 % (1196k) | 49.5 % (1122k) | 50.5 % (1122k) | 49.4 % (1195k) | 51.7 % (110k) | 51.6 % (125k) | 50.6 % (1196k) | 50.5 % (1196k) |
| GBPUSD | 5 | 50.0 % (239k) | 50.0 % (239k) | 49.4 % (225k) | 50.6 % (225k) | 48.9 % (239k) | 52.3 % (22k) | 52.4 % (26k) | 50.8 % (237k) | 50.7 % (239k) |
| GBPUSD | 15 | 49.5 % (79k) | 49.8 % (79k) | 49.4 % (75k) | 50.6 % (75k) | 48.7 % (79k) | 54.7 % (8k) | 53.3 % (10k) | 51.3 % (79k) | 50.7 % (79k) |
| GBPUSD | 60 | 50.4 % (20k) | 50.1 % (20k) | 49.5 % (19k) | 50.5 % (19k) | 48.5 % (20k) | 52.8 % (2k) | 54.5 % (3k) | 50.2 % (20k) | 50.4 % (20k) |
| USDJPY | 1 | 50.0 % (1195k) | 50.0 % (1195k) | 49.4 % (1131k) | 50.6 % (1131k) | 49.0 % (1194k) | 53.0 % (108k) | 52.7 % (125k) | 51.1 % (1195k) | 51.0 % (1195k) |
| USDJPY | 5 | 49.9 % (239k) | 50.9 % (239k) | 49.5 % (227k) | 50.5 % (227k) | 48.9 % (239k) | 54.3 % (22k) | 52.6 % (26k) | 51.1 % (239k) | 51.1 % (239k) |
| USDJPY | 15 | 50.1 % (79k) | 51.2 % (79k) | 49.4 % (76k) | 50.6 % (76k) | 48.7 % (79k) | 54.5 % (8k) | 53.2 % (10k) | 51.2 % (79k) | 51.1 % (79k) |
| USDJPY | 60 | 50.4 % (20k) | 52.0 % (20k) | 49.8 % (19k) | 50.2 % (19k) | 48.8 % (20k) | 53.6 % (2k) | 52.4 % (3k) | 51.4 % (20k) | 51.1 % (20k) |
| XAUUSD | 1 | 50.0 % (978k) | 50.2 % (978k) | 49.5 % (963k) | 50.5 % (963k) | 49.5 % (978k) | 51.8 % (81k) | 52.1 % (101k) | 50.5 % (978k) | 50.6 % (977k) |
| XAUUSD | 5 | 49.9 % (195k) | 50.3 % (195k) | 49.2 % (192k) | 50.8 % (192k) | 49.1 % (195k) | 52.3 % (16k) | 52.4 % (21k) | 50.6 % (195k) | 50.2 % (195k) |
| XAUUSD | 15 | 50.1 % (64k) | 50.1 % (64k) | 49.5 % (64k) | 50.5 % (64k) | 48.7 % (64k) | 51.3 % (5k) | 52.1 % (7k) | 50.8 % (64k) | 50.0 % (63k) |
| XAUUSD | 60 | 49.8 % (15k) | 50.1 % (15k) | 50.3 % (15k) | 49.7 % (15k) | 49.3 % (15k) | 51.2 % (1k) | 50.8 % (2k) | 51.4 % (15k) | 51.4 % (15k) |

## 5. Políticas selectivas (B = EV estimado ≥ margen; BN = B sin ventanas de noticias)

| Instrumento | h | Contrato | Modelo | Política | n | Acierto [IC95] | EV [IC95] | Máx. caída | p Holm |
|---|---|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | binaria | gbm | B | 9317 | 55.0 % [53.9 %, 56.1 %] | 0.014 [-0.004, 0.031] | 66.1 | 1.000 |
| AUDUSD | 1 | binaria | gbm | BN | 8558 | 55.3 % [54.1 %, 56.5 %] | 0.019 [0.001, 0.036] | 73.3 | 1.000 |
| AUDUSD | 1 | binaria | logit | B | 5581 | 53.9 % [52.5 %, 55.4 %] | -0.002 [-0.023, 0.019] | 46.8 | 1.000 |
| AUDUSD | 1 | binaria | logit | BN | 4791 | 54.5 % [52.9 %, 56.0 %] | 0.006 [-0.017, 0.029] | 52.6 | 1.000 |
| AUDUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | binaria | gbm | B | 4210 | 55.1 % [53.6 %, 56.6 %] | 0.018 [-0.008, 0.047] | 55.9 | 1.000 |
| AUDUSD | 5 | binaria | gbm | BN | 3826 | 55.6 % [54.0 %, 57.2 %] | 0.027 [-0.001, 0.056] | 58.7 | 1.000 |
| AUDUSD | 5 | binaria | logit | B | 4760 | 55.1 % [53.6 %, 56.5 %] | 0.018 [-0.010, 0.045] | 71.7 | 1.000 |
| AUDUSD | 5 | binaria | logit | BN | 4030 | 55.9 % [54.3 %, 57.5 %] | 0.033 [0.002, 0.061] | 43.4 | 1.000 |
| AUDUSD | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | binaria | gbm | B | 2261 | 57.2 % [55.2 %, 59.3 %] | 0.058 [0.023, 0.093] | 42.9 | 0.842 |
| AUDUSD | 15 | binaria | gbm | BN | 1922 | 57.6 % [55.4 %, 59.9 %] | 0.065 [0.024, 0.105] | 36.1 | 0.570 |
| AUDUSD | 15 | binaria | logit | B | 1614 | 53.0 % [50.5 %, 55.4 %] | -0.019 [-0.057, 0.023] | 46.5 | 1.000 |
| AUDUSD | 15 | binaria | logit | BN | 1315 | 53.5 % [50.7 %, 56.2 %] | -0.011 [-0.059, 0.037] | 38.0 | 1.000 |
| AUDUSD | 15 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 15 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | binaria | gbm | B | 1499 | 51.5 % [48.9 %, 54.0 %] | -0.047 [-0.085, -0.008] | 105.9 | 1.000 |
| AUDUSD | 60 | binaria | gbm | BN | 867 | 51.4 % [48.1 %, 54.7 %] | -0.049 [-0.116, 0.016] | 76.9 | 1.000 |
| AUDUSD | 60 | binaria | logit | B | 1489 | 50.3 % [47.7 %, 52.8 %] | -0.069 [-0.108, -0.036] | 114.3 | 1.000 |
| AUDUSD | 60 | binaria | logit | BN | 903 | 50.1 % [46.8 %, 53.3 %] | -0.073 [-0.133, -0.021] | 76.7 | 1.000 |
| AUDUSD | 60 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| AUDUSD | 60 | contado | logit | B | 2 | 50.0 % [9.5 %, 90.5 %] | 8.685 [8.685, 8.685] | 4.5 | 0.607 |
| AUDUSD | 60 | contado | logit | BN | 1 | 0.0 % [0.0 %, 79.3 %] | -4.510 [-4.510, -4.510] | 4.5 | 1.000 |
| BTCUSDT | 1 | binaria | gbm | B | 217663 | 56.6 % [56.4 %, 56.8 %] | 0.044 [0.039, 0.049] | 171.9 | 0.000 |
| BTCUSDT | 1 | binaria | gbm | BN | 206174 | 56.7 % [56.5 %, 56.9 %] | 0.045 [0.040, 0.050] | 163.2 | 0.000 |
| BTCUSDT | 1 | binaria | logit | B | 77946 | 53.8 % [53.4 %, 54.1 %] | -0.005 [-0.012, 0.002] | 1117.9 | 1.000 |
| BTCUSDT | 1 | binaria | logit | BN | 72085 | 53.8 % [53.4 %, 54.2 %] | -0.005 [-0.012, 0.003] | 1037.2 | 1.000 |
| BTCUSDT | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | binaria | gbm | B | 30704 | 55.2 % [54.6 %, 55.8 %] | 0.021 [0.009, 0.032] | 126.3 | 0.019 |
| BTCUSDT | 5 | binaria | gbm | BN | 28265 | 55.4 % [54.8 %, 56.0 %] | 0.025 [0.014, 0.036] | 107.6 | 0.001 |
| BTCUSDT | 5 | binaria | logit | B | 30581 | 54.5 % [53.9 %, 55.0 %] | 0.008 [-0.002, 0.018] | 157.3 | 1.000 |
| BTCUSDT | 5 | binaria | logit | BN | 28343 | 54.6 % [54.0 %, 55.2 %] | 0.009 [-0.002, 0.021] | 156.2 | 1.000 |
| BTCUSDT | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | binaria | gbm | B | 15923 | 55.5 % [54.7 %, 56.3 %] | 0.026 [0.012, 0.040] | 58.4 | 0.094 |
| BTCUSDT | 15 | binaria | gbm | BN | 14129 | 55.7 % [54.9 %, 56.5 %] | 0.030 [0.015, 0.046] | 55.6 | 0.032 |
| BTCUSDT | 15 | binaria | logit | B | 30856 | 56.0 % [55.4 %, 56.6 %] | 0.036 [0.026, 0.047] | 62.4 | 0.000 |
| BTCUSDT | 15 | binaria | logit | BN | 27111 | 56.3 % [55.7 %, 56.9 %] | 0.041 [0.030, 0.052] | 60.2 | 0.000 |
| BTCUSDT | 15 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 15 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | binaria | gbm | B | 3665 | 53.2 % [51.6 %, 54.8 %] | -0.016 [-0.044, 0.011] | 84.6 | 1.000 |
| BTCUSDT | 60 | binaria | gbm | BN | 2578 | 53.7 % [51.8 %, 55.6 %] | -0.007 [-0.044, 0.027] | 65.1 | 1.000 |
| BTCUSDT | 60 | binaria | logit | B | 5914 | 56.6 % [55.4 %, 57.9 %] | 0.048 [0.026, 0.070] | 36.5 | 0.020 |
| BTCUSDT | 60 | binaria | logit | BN | 4147 | 57.5 % [55.9 %, 59.0 %] | 0.063 [0.039, 0.090] | 21.2 | 0.004 |
| BTCUSDT | 60 | contado | gbm | B | 16 | 25.0 % [10.2 %, 49.5 %] | -43.311 [-86.864, 48.779] | 1284.5 | 1.000 |
| BTCUSDT | 60 | contado | gbm | BN | 8 | 25.0 % [7.1 %, 59.1 %] | 0.135 [-51.964, 64.354] | 200.3 | 1.000 |
| BTCUSDT | 60 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| BTCUSDT | 60 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | binaria | gbm | B | 5384 | 53.3 % [51.8 %, 54.8 %] | -0.012 [-0.032, 0.011] | 143.5 | 1.000 |
| EURUSD | 1 | binaria | gbm | BN | 4857 | 53.8 % [52.2 %, 55.3 %] | -0.004 [-0.027, 0.019] | 107.5 | 1.000 |
| EURUSD | 1 | binaria | logit | B | 2009 | 53.6 % [51.3 %, 55.9 %] | -0.007 [-0.051, 0.033] | 47.1 | 1.000 |
| EURUSD | 1 | binaria | logit | BN | 1871 | 53.1 % [50.7 %, 55.5 %] | -0.015 [-0.056, 0.032] | 47.9 | 1.000 |
| EURUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | binaria | gbm | B | 1142 | 52.5 % [49.4 %, 55.4 %] | -0.027 [-0.073, 0.016] | 41.2 | 1.000 |
| EURUSD | 5 | binaria | gbm | BN | 1027 | 52.2 % [49.0 %, 55.4 %] | -0.031 [-0.078, 0.014] | 37.6 | 1.000 |
| EURUSD | 5 | binaria | logit | B | 4859 | 51.5 % [50.1 %, 52.9 %] | -0.045 [-0.074, -0.016] | 249.9 | 1.000 |
| EURUSD | 5 | binaria | logit | BN | 4428 | 51.9 % [50.4 %, 53.4 %] | -0.038 [-0.066, -0.012] | 201.9 | 1.000 |
| EURUSD | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 15 | binaria | gbm | B | 1841 | 53.6 % [51.3 %, 55.9 %] | -0.008 [-0.049, 0.030] | 52.8 | 1.000 |
| EURUSD | 15 | binaria | gbm | BN | 1583 | 53.3 % [50.9 %, 55.8 %] | -0.013 [-0.057, 0.028] | 57.0 | 1.000 |
| EURUSD | 15 | binaria | logit | B | 2273 | 52.5 % [50.4 %, 54.5 %] | -0.029 [-0.070, 0.010] | 75.6 | 1.000 |
| EURUSD | 15 | binaria | logit | BN | 1910 | 53.7 % [51.5 %, 56.0 %] | -0.006 [-0.044, 0.033] | 49.8 | 1.000 |
| EURUSD | 15 | contado | gbm | B | 3 | 66.7 % [20.8 %, 93.9 %] | 3.947 [3.947, 3.947] | 3.6 | 0.607 |
| EURUSD | 15 | contado | gbm | BN | 3 | 66.7 % [20.8 %, 93.9 %] | 3.947 [3.947, 3.947] | 3.6 | 0.607 |
| EURUSD | 15 | contado | logit | B | 6 | 16.7 % [3.0 %, 56.4 %] | -2.731 [-6.725, -1.295] | 16.4 | 1.000 |
| EURUSD | 15 | contado | logit | BN | 4 | 25.0 % [4.6 %, 69.9 %] | 0.179 [-3.358, 2.763] | 3.4 | 1.000 |
| EURUSD | 60 | binaria | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | binaria | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| EURUSD | 60 | contado | gbm | B | 118 | 45.8 % [37.0 %, 54.7 %] | -0.089 [-2.751, 2.591] | 166.3 | 1.000 |
| EURUSD | 60 | contado | gbm | BN | 64 | 45.3 % [33.7 %, 57.4 %] | 0.764 [-3.215, 4.057] | 149.1 | 1.000 |
| EURUSD | 60 | contado | logit | B | 115 | 43.5 % [34.8 %, 52.6 %] | -1.512 [-4.354, 1.151] | 297.0 | 1.000 |
| EURUSD | 60 | contado | logit | BN | 61 | 49.2 % [37.1 %, 61.4 %] | -0.578 [-4.334, 3.252] | 79.7 | 1.000 |
| GBPUSD | 1 | binaria | gbm | B | 4717 | 52.6 % [51.0 %, 54.1 %] | -0.023 [-0.049, 0.004] | 148.0 | 1.000 |
| GBPUSD | 1 | binaria | gbm | BN | 4334 | 52.5 % [50.9 %, 54.2 %] | -0.023 [-0.051, 0.007] | 137.9 | 1.000 |
| GBPUSD | 1 | binaria | logit | B | 5383 | 55.0 % [53.6 %, 56.4 %] | 0.016 [-0.006, 0.037] | 46.2 | 1.000 |
| GBPUSD | 1 | binaria | logit | BN | 4539 | 55.3 % [53.8 %, 56.8 %] | 0.021 [-0.003, 0.048] | 38.1 | 1.000 |
| GBPUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 5 | binaria | gbm | B | 6269 | 55.2 % [54.0 %, 56.5 %] | 0.021 [-0.002, 0.044] | 67.4 | 1.000 |
| GBPUSD | 5 | binaria | gbm | BN | 5663 | 55.5 % [54.2 %, 56.8 %] | 0.025 [0.002, 0.049] | 49.2 | 1.000 |
| GBPUSD | 5 | binaria | logit | B | 1476 | 54.7 % [52.1 %, 57.2 %] | 0.011 [-0.039, 0.058] | 36.8 | 1.000 |
| GBPUSD | 5 | binaria | logit | BN | 1323 | 55.8 % [53.1 %, 58.5 %] | 0.031 [-0.019, 0.077] | 33.3 | 1.000 |
| GBPUSD | 5 | contado | gbm | B | 13 | 76.9 % [49.7 %, 91.8 %] | 7.174 [7.174, 7.174] | 10.6 | 0.607 |
| GBPUSD | 5 | contado | gbm | BN | 11 | 72.7 % [43.4 %, 90.3 %] | 4.915 [4.915, 4.915] | 10.6 | 0.607 |
| GBPUSD | 5 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 5 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 15 | binaria | gbm | B | 2356 | 54.5 % [52.5 %, 56.5 %] | 0.008 [-0.025, 0.043] | 44.1 | 1.000 |
| GBPUSD | 15 | binaria | gbm | BN | 2017 | 54.4 % [52.2 %, 56.5 %] | 0.006 [-0.030, 0.043] | 35.0 | 1.000 |
| GBPUSD | 15 | binaria | logit | B | 1633 | 53.5 % [51.0 %, 55.9 %] | -0.010 [-0.055, 0.039] | 83.5 | 1.000 |
| GBPUSD | 15 | binaria | logit | BN | 1418 | 54.5 % [51.9 %, 57.1 %] | 0.008 [-0.039, 0.058] | 69.7 | 1.000 |
| GBPUSD | 15 | contado | gbm | B | 49 | 53.1 % [39.4 %, 66.3 %] | -1.115 [-1.400, 12.600] | 245.8 | 1.000 |
| GBPUSD | 15 | contado | gbm | BN | 37 | 54.1 % [38.4 %, 69.0 %] | 0.318 [-0.023, 12.600] | 180.5 | 1.000 |
| GBPUSD | 15 | contado | logit | B | 24 | 58.3 % [38.8 %, 75.5 %] | 0.863 [-12.749, 7.464] | 83.4 | 1.000 |
| GBPUSD | 15 | contado | logit | BN | 21 | 52.4 % [32.4 %, 71.7 %] | -1.256 [-17.669, 5.414] | 83.4 | 1.000 |
| GBPUSD | 60 | binaria | gbm | B | 334 | 50.0 % [44.7 %, 55.3 %] | -0.075 [-0.172, 0.024] | 36.5 | 1.000 |
| GBPUSD | 60 | binaria | gbm | BN | 196 | 52.0 % [45.1 %, 58.9 %] | -0.037 [-0.172, 0.097] | 25.6 | 1.000 |
| GBPUSD | 60 | binaria | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | binaria | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| GBPUSD | 60 | contado | gbm | B | 74 | 44.6 % [33.8 %, 55.9 %] | -5.216 [-11.658, 1.595] | 426.6 | 1.000 |
| GBPUSD | 60 | contado | gbm | BN | 40 | 45.0 % [30.7 %, 60.2 %] | -2.679 [-7.074, 1.479] | 170.7 | 1.000 |
| GBPUSD | 60 | contado | logit | B | 24 | 37.5 % [21.2 %, 57.3 %] | -9.742 [-10.456, 6.681] | 323.6 | 1.000 |
| GBPUSD | 60 | contado | logit | BN | 14 | 35.7 % [16.3 %, 61.2 %] | -6.204 [-6.204, -6.204] | 163.3 | 1.000 |
| USDJPY | 1 | binaria | gbm | B | 17981 | 55.4 % [54.6 %, 56.2 %] | 0.022 [0.010, 0.035] | 90.0 | 0.218 |
| USDJPY | 1 | binaria | gbm | BN | 16377 | 55.4 % [54.6 %, 56.3 %] | 0.022 [0.009, 0.036] | 76.0 | 0.266 |
| USDJPY | 1 | binaria | logit | B | 10193 | 55.6 % [54.6 %, 56.6 %] | 0.027 [0.009, 0.044] | 60.7 | 0.779 |
| USDJPY | 1 | binaria | logit | BN | 9215 | 55.3 % [54.2 %, 56.3 %] | 0.022 [0.003, 0.040] | 58.9 | 1.000 |
| USDJPY | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| USDJPY | 5 | binaria | gbm | B | 10106 | 54.6 % [53.6 %, 55.6 %] | 0.010 [-0.008, 0.027] | 90.0 | 1.000 |
| USDJPY | 5 | binaria | gbm | BN | 9114 | 54.7 % [53.7 %, 55.7 %] | 0.012 [-0.007, 0.031] | 76.0 | 1.000 |
| USDJPY | 5 | binaria | logit | B | 10840 | 54.3 % [53.4 %, 55.2 %] | 0.005 [-0.013, 0.022] | 179.6 | 1.000 |
| USDJPY | 5 | binaria | logit | BN | 9574 | 54.6 % [53.6 %, 55.6 %] | 0.009 [-0.009, 0.029] | 124.9 | 1.000 |
| USDJPY | 5 | contado | gbm | B | 258 | 50.0 % [43.9 %, 56.1 %] | 0.015 [-1.381, 1.260] | 183.7 | 1.000 |
| USDJPY | 5 | contado | gbm | BN | 235 | 50.2 % [43.9 %, 56.6 %] | -0.078 [-1.435, 1.233] | 178.6 | 1.000 |
| USDJPY | 5 | contado | logit | B | 51 | 52.9 % [39.5 %, 65.9 %] | 0.580 [-0.839, 2.677] | 46.5 | 1.000 |
| USDJPY | 5 | contado | logit | BN | 50 | 54.0 % [40.4 %, 67.0 %] | 0.756 [-0.641, 2.828] | 46.5 | 1.000 |
| USDJPY | 15 | binaria | gbm | B | 5001 | 53.9 % [52.5 %, 55.3 %] | -0.003 [-0.027, 0.022] | 106.9 | 1.000 |
| USDJPY | 15 | binaria | gbm | BN | 4307 | 53.2 % [51.7 %, 54.7 %] | -0.015 [-0.041, 0.012] | 146.9 | 1.000 |
| USDJPY | 15 | binaria | logit | B | 11648 | 53.1 % [52.2 %, 54.1 %] | -0.017 [-0.034, -0.001] | 352.6 | 1.000 |
| USDJPY | 15 | binaria | logit | BN | 10076 | 53.1 % [52.1 %, 54.0 %] | -0.018 [-0.037, -0.000] | 319.0 | 1.000 |
| USDJPY | 15 | contado | gbm | B | 579 | 46.3 % [42.3 %, 50.4 %] | -1.127 [-1.806, -0.341] | 661.3 | 1.000 |
| USDJPY | 15 | contado | gbm | BN | 497 | 45.9 % [41.5 %, 50.3 %] | -1.065 [-1.945, -0.277] | 538.5 | 1.000 |
| USDJPY | 15 | contado | logit | B | 1227 | 47.9 % [45.1 %, 50.7 %] | -0.885 [-1.413, -0.388] | 1134.2 | 1.000 |
| USDJPY | 15 | contado | logit | BN | 1075 | 47.1 % [44.1 %, 50.1 %] | -1.010 [-1.604, -0.443] | 1130.4 | 1.000 |
| USDJPY | 60 | binaria | gbm | B | 1729 | 52.2 % [49.8 %, 54.6 %] | -0.034 [-0.076, 0.006] | 97.3 | 1.000 |
| USDJPY | 60 | binaria | gbm | BN | 998 | 52.7 % [49.6 %, 55.8 %] | -0.025 [-0.085, 0.029] | 52.0 | 1.000 |
| USDJPY | 60 | binaria | logit | B | 2511 | 52.2 % [50.3 %, 54.2 %] | -0.034 [-0.065, -0.002] | 116.2 | 1.000 |
| USDJPY | 60 | binaria | logit | BN | 1375 | 52.9 % [50.2 %, 55.5 %] | -0.021 [-0.069, 0.025] | 68.6 | 1.000 |
| USDJPY | 60 | contado | gbm | B | 2480 | 48.1 % [46.2 %, 50.1 %] | -0.946 [-1.619, -0.293] | 2510.3 | 1.000 |
| USDJPY | 60 | contado | gbm | BN | 1409 | 48.3 % [45.7 %, 50.9 %] | -1.174 [-2.000, -0.287] | 1722.4 | 1.000 |
| USDJPY | 60 | contado | logit | B | 2637 | 48.7 % [46.8 %, 50.6 %] | -0.810 [-1.421, -0.173] | 2424.5 | 1.000 |
| USDJPY | 60 | contado | logit | BN | 1484 | 49.3 % [46.7 %, 51.8 %] | -0.904 [-1.669, -0.114] | 1659.7 | 1.000 |
| XAUUSD | 1 | binaria | gbm | B | 6567 | 54.2 % [53.0 %, 55.5 %] | 0.003 [-0.016, 0.026] | 76.9 | 1.000 |
| XAUUSD | 1 | binaria | gbm | BN | 5842 | 54.1 % [52.9 %, 55.4 %] | 0.002 [-0.019, 0.025] | 80.1 | 1.000 |
| XAUUSD | 1 | binaria | logit | B | 7895 | 54.2 % [53.1 %, 55.3 %] | 0.003 [-0.018, 0.024] | 154.3 | 1.000 |
| XAUUSD | 1 | binaria | logit | BN | 7020 | 54.4 % [53.2 %, 55.5 %] | 0.006 [-0.017, 0.029] | 137.7 | 1.000 |
| XAUUSD | 1 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 1 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 1 | contado | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 1 | contado | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 5 | binaria | gbm | B | 189 | 53.4 % [46.3 %, 60.4 %] | -0.011 [-0.129, 0.098] | 13.8 | 1.000 |
| XAUUSD | 5 | binaria | gbm | BN | 171 | 53.2 % [45.7 %, 60.5 %] | -0.015 [-0.146, 0.125] | 14.6 | 1.000 |
| XAUUSD | 5 | binaria | logit | B | 3312 | 51.9 % [50.2 %, 53.6 %] | -0.039 [-0.068, -0.009] | 148.0 | 1.000 |
| XAUUSD | 5 | binaria | logit | BN | 2856 | 52.7 % [50.8 %, 54.5 %] | -0.026 [-0.057, 0.007] | 109.9 | 1.000 |
| XAUUSD | 5 | contado | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 5 | contado | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 5 | contado | logit | B | 1 | 0.0 % [0.0 %, 79.3 %] | -2.928 [-2.928, -2.928] | 2.9 | 1.000 |
| XAUUSD | 5 | contado | logit | BN | 1 | 0.0 % [0.0 %, 79.3 %] | -2.928 [-2.928, -2.928] | 2.9 | 1.000 |
| XAUUSD | 15 | binaria | gbm | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 15 | binaria | gbm | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 15 | binaria | logit | B | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 15 | binaria | logit | BN | 0 | — [—, —] | — [—, —] | 0.0 | 1.000 |
| XAUUSD | 15 | contado | gbm | B | 1 | 0.0 % [0.0 %, 79.3 %] | -14.530 [-14.530, -14.530] | 14.5 | 1.000 |
| XAUUSD | 15 | contado | gbm | BN | 1 | 0.0 % [0.0 %, 79.3 %] | -14.530 [-14.530, -14.530] | 14.5 | 1.000 |
| XAUUSD | 15 | contado | logit | B | 31 | 45.2 % [29.2 %, 62.2 %] | 0.645 [-3.786, 5.085] | 84.3 | 1.000 |
| XAUUSD | 15 | contado | logit | BN | 24 | 41.7 % [24.5 %, 61.2 %] | -0.920 [-7.693, 5.273] | 101.5 | 1.000 |
| XAUUSD | 60 | binaria | gbm | B | 1144 | 51.1 % [48.2 %, 54.0 %] | -0.054 [-0.099, -0.009] | 71.0 | 1.000 |
| XAUUSD | 60 | binaria | gbm | BN | 633 | 50.2 % [46.4 %, 54.1 %] | -0.071 [-0.139, -0.005] | 49.9 | 1.000 |
| XAUUSD | 60 | binaria | logit | B | 1144 | 51.1 % [48.2 %, 54.0 %] | -0.054 [-0.099, -0.009] | 71.0 | 1.000 |
| XAUUSD | 60 | binaria | logit | BN | 633 | 50.2 % [46.4 %, 54.1 %] | -0.071 [-0.139, -0.005] | 49.9 | 1.000 |
| XAUUSD | 60 | contado | gbm | B | 1066 | 49.9 % [46.9 %, 52.9 %] | -0.755 [-2.791, 1.175] | 1547.0 | 1.000 |
| XAUUSD | 60 | contado | gbm | BN | 588 | 50.2 % [46.1 %, 54.2 %] | 0.203 [-2.241, 2.559] | 482.5 | 1.000 |
| XAUUSD | 60 | contado | logit | B | 1066 | 49.9 % [46.9 %, 52.9 %] | -0.755 [-2.791, 1.175] | 1547.0 | 1.000 |
| XAUUSD | 60 | contado | logit | BN | 588 | 50.2 % [46.1 %, 54.2 %] | 0.203 [-2.241, 2.559] | 482.5 | 1.000 |

Unidades: binaria en unidades de apuesta; contado en puntos básicos (pb).

## 6. ¿Se alcanza un acierto ≥ 80%?

Mejor acierto en cualquier nivel de cobertura (umbral fijado con el tramo de calibración, n ≥ 100), sin costos.

| Instrumento | h | Modelo | Mejor acierto | IC95 | n | Cobertura | ¿≥ objetivo? |
|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | gbm | 54.0 % | [53.3 %, 54.7 %] | 19364 | 1.73 % | no |
| AUDUSD | 1 | logit | 52.3 % | [51.5 %, 53.1 %] | 15875 | 1.42 % | no |
| AUDUSD | 5 | gbm | 53.3 % | [51.5 %, 55.0 %] | 3084 | 1.31 % | no |
| AUDUSD | 5 | logit | 53.3 % | [52.5 %, 54.1 %] | 14352 | 6.10 % | no |
| AUDUSD | 15 | gbm | 54.8 % | [53.0 %, 56.6 %] | 2972 | 3.75 % | no |
| AUDUSD | 15 | logit | 52.3 % | [50.9 %, 53.6 %] | 5395 | 6.81 % | no |
| AUDUSD | 60 | gbm | 51.6 % | [50.3 %, 52.9 %] | 5485 | 27.93 % | no |
| AUDUSD | 60 | logit | 51.8 % | [50.4 %, 53.3 %] | 4445 | 22.63 % | no |
| BTCUSDT | 1 | gbm | 59.3 % | [58.2 %, 60.4 %] | 7752 | 0.41 % | no |
| BTCUSDT | 1 | logit | 57.8 % | [56.6 %, 58.9 %] | 7367 | 0.39 % | no |
| BTCUSDT | 5 | gbm | 56.8 % | [55.5 %, 58.0 %] | 6371 | 1.66 % | no |
| BTCUSDT | 5 | logit | 55.2 % | [54.2 %, 56.1 %] | 10100 | 2.63 % | no |
| BTCUSDT | 15 | gbm | 57.1 % | [55.0 %, 59.2 %] | 2118 | 1.65 % | no |
| BTCUSDT | 15 | logit | 57.5 % | [56.2 %, 58.7 %] | 6217 | 4.84 % | no |
| BTCUSDT | 60 | gbm | 53.6 % | [52.5 %, 54.6 %] | 8515 | 26.52 % | no |
| BTCUSDT | 60 | logit | 54.8 % | [53.6 %, 55.9 %] | 7221 | 22.49 % | no |
| EURUSD | 1 | gbm | 54.4 % | [52.0 %, 56.7 %] | 1670 | 0.15 % | no |
| EURUSD | 1 | logit | 53.2 % | [51.6 %, 54.9 %] | 3534 | 0.32 % | no |
| EURUSD | 5 | gbm | 52.2 % | [51.6 %, 52.8 %] | 23850 | 10.15 % | no |
| EURUSD | 5 | logit | 51.7 % | [51.3 %, 52.2 %] | 47129 | 20.06 % | no |
| EURUSD | 15 | gbm | 55.3 % | [53.8 %, 56.7 %] | 4444 | 5.61 % | no |
| EURUSD | 15 | logit | 51.8 % | [51.1 %, 52.5 %] | 19009 | 24.00 % | no |
| EURUSD | 60 | gbm | 51.9 % | [50.9 %, 52.9 %] | 9921 | 50.33 % | no |
| EURUSD | 60 | logit | 51.5 % | [50.4 %, 52.6 %] | 8051 | 40.84 % | no |
| GBPUSD | 1 | gbm | 52.8 % | [51.6 %, 54.0 %] | 6874 | 0.61 % | no |
| GBPUSD | 1 | logit | 53.8 % | [52.8 %, 54.7 %] | 10588 | 0.94 % | no |
| GBPUSD | 5 | gbm | 54.6 % | [52.1 %, 57.0 %] | 1552 | 0.66 % | no |
| GBPUSD | 5 | logit | 52.9 % | [51.9 %, 53.9 %] | 10065 | 4.27 % | no |
| GBPUSD | 15 | gbm | 52.5 % | [51.2 %, 53.8 %] | 5517 | 6.96 % | no |
| GBPUSD | 15 | logit | 53.5 % | [52.3 %, 54.7 %] | 6687 | 8.43 % | no |
| GBPUSD | 60 | gbm | 50.6 % | [49.5 %, 51.8 %] | 7114 | 36.14 % | no |
| GBPUSD | 60 | logit | 51.6 % | [49.9 %, 53.2 %] | 3709 | 18.84 % | no |
| USDJPY | 1 | gbm | 55.7 % | [54.8 %, 56.6 %] | 11279 | 0.99 % | no |
| USDJPY | 1 | logit | 55.9 % | [53.9 %, 58.0 %] | 2240 | 0.20 % | no |
| USDJPY | 5 | gbm | 52.9 % | [52.4 %, 53.4 %] | 39675 | 16.76 % | no |
| USDJPY | 5 | logit | 56.5 % | [55.0 %, 58.0 %] | 4206 | 1.78 % | no |
| USDJPY | 15 | gbm | 53.6 % | [52.2 %, 55.0 %] | 5077 | 6.39 % | no |
| USDJPY | 15 | logit | 54.7 % | [52.9 %, 56.5 %] | 3091 | 3.89 % | no |
| USDJPY | 60 | gbm | 52.4 % | [51.1 %, 53.7 %] | 5941 | 30.18 % | no |
| USDJPY | 60 | logit | 53.4 % | [52.0 %, 54.7 %] | 5485 | 27.87 % | no |
| XAUUSD | 1 | gbm | 54.5 % | [53.1 %, 55.9 %] | 4869 | 0.50 % | no |
| XAUUSD | 1 | logit | 53.9 % | [53.0 %, 54.8 %] | 12962 | 1.33 % | no |
| XAUUSD | 5 | gbm | 52.4 % | [51.1 %, 53.6 %] | 6231 | 3.18 % | no |
| XAUUSD | 5 | logit | 52.6 % | [51.6 %, 53.6 %] | 9328 | 4.76 % | no |
| XAUUSD | 15 | gbm | 50.5 % | [49.1 %, 51.9 %] | 5119 | 7.90 % | no |
| XAUUSD | 15 | logit | 51.7 % | [50.6 %, 52.8 %] | 7776 | 12.00 % | no |
| XAUUSD | 60 | gbm | 50.8 % | [49.6 %, 52.0 %] | 6856 | 44.18 % | no |
| XAUUSD | 60 | logit | 50.8 % | [49.6 %, 52.0 %] | 6856 | 44.18 % | no |

## 7. Calibración fuera de muestra (P(sube))

| Instrumento | h | Modelo | ECE | Brier | Brier ref. (0,5) | n |
|---|---|---|---|---|---|---|
| AUDUSD | 1 | logit | 0.42 % | 0.24997 | 0,25000 | 1,118,833 |
| AUDUSD | 1 | gbm | 0.33 % | 0.24995 | 0,25000 | 1,118,833 |
| AUDUSD | 5 | logit | 0.78 % | 0.24995 | 0,25000 | 235,102 |
| AUDUSD | 5 | gbm | 0.57 % | 0.24997 | 0,25000 | 235,102 |
| AUDUSD | 15 | logit | 1.15 % | 0.25009 | 0,25000 | 79,177 |
| AUDUSD | 15 | gbm | 1.22 % | 0.25003 | 0,25000 | 79,177 |
| AUDUSD | 60 | logit | 1.64 % | 0.25019 | 0,25000 | 19,640 |
| AUDUSD | 60 | gbm | 1.39 % | 0.25012 | 0,25000 | 19,640 |
| BTCUSDT | 1 | logit | 0.54 % | 0.24980 | 0,25000 | 1,877,303 |
| BTCUSDT | 1 | gbm | 0.44 % | 0.24923 | 0,25000 | 1,877,303 |
| BTCUSDT | 5 | logit | 0.55 % | 0.24964 | 0,25000 | 384,559 |
| BTCUSDT | 5 | gbm | 0.62 % | 0.24961 | 0,25000 | 384,559 |
| BTCUSDT | 15 | logit | 0.70 % | 0.24879 | 0,25000 | 128,465 |
| BTCUSDT | 15 | gbm | 0.73 % | 0.24930 | 0,25000 | 128,465 |
| BTCUSDT | 60 | logit | 0.77 % | 0.24877 | 0,25000 | 32,107 |
| BTCUSDT | 60 | gbm | 0.98 % | 0.24957 | 0,25000 | 32,107 |
| EURUSD | 1 | logit | 0.35 % | 0.24994 | 0,25000 | 1,116,809 |
| EURUSD | 1 | gbm | 0.26 % | 0.24995 | 0,25000 | 1,116,809 |
| EURUSD | 5 | logit | 0.51 % | 0.24996 | 0,25000 | 234,926 |
| EURUSD | 5 | gbm | 0.44 % | 0.24995 | 0,25000 | 234,926 |
| EURUSD | 15 | logit | 0.99 % | 0.24998 | 0,25000 | 79,190 |
| EURUSD | 15 | gbm | 0.60 % | 0.24980 | 0,25000 | 79,190 |
| EURUSD | 60 | logit | 1.87 % | 0.25019 | 0,25000 | 19,713 |
| EURUSD | 60 | gbm | 1.87 % | 0.25016 | 0,25000 | 19,713 |
| GBPUSD | 1 | logit | 0.29 % | 0.24993 | 0,25000 | 1,129,574 |
| GBPUSD | 1 | gbm | 0.41 % | 0.24997 | 0,25000 | 1,129,574 |
| GBPUSD | 5 | logit | 0.52 % | 0.24991 | 0,25000 | 235,912 |
| GBPUSD | 5 | gbm | 0.63 % | 0.24991 | 0,25000 | 235,912 |
| GBPUSD | 15 | logit | 0.61 % | 0.24985 | 0,25000 | 79,311 |
| GBPUSD | 15 | gbm | 0.83 % | 0.25000 | 0,25000 | 79,311 |
| GBPUSD | 60 | logit | 1.73 % | 0.25020 | 0,25000 | 19,685 |
| GBPUSD | 60 | gbm | 1.77 % | 0.25016 | 0,25000 | 19,685 |
| USDJPY | 1 | logit | 0.41 % | 0.24981 | 0,25000 | 1,140,139 |
| USDJPY | 1 | gbm | 0.34 % | 0.24981 | 0,25000 | 1,140,139 |
| USDJPY | 5 | logit | 0.69 % | 0.24976 | 0,25000 | 236,721 |
| USDJPY | 5 | gbm | 0.71 % | 0.24984 | 0,25000 | 236,721 |
| USDJPY | 15 | logit | 1.14 % | 0.24992 | 0,25000 | 79,414 |
| USDJPY | 15 | gbm | 1.23 % | 0.24988 | 0,25000 | 79,414 |
| USDJPY | 60 | logit | 2.05 % | 0.25006 | 0,25000 | 19,684 |
| USDJPY | 60 | gbm | 1.97 % | 0.25001 | 0,25000 | 19,684 |
| XAUUSD | 1 | logit | 0.52 % | 0.24995 | 0,25000 | 973,809 |
| XAUUSD | 1 | gbm | 0.39 % | 0.24997 | 0,25000 | 973,809 |
| XAUUSD | 5 | logit | 0.82 % | 0.25001 | 0,25000 | 195,890 |
| XAUUSD | 5 | gbm | 0.91 % | 0.25005 | 0,25000 | 195,890 |
| XAUUSD | 15 | logit | 1.22 % | 0.25012 | 0,25000 | 64,802 |
| XAUUSD | 15 | gbm | 1.49 % | 0.25018 | 0,25000 | 64,802 |
| XAUUSD | 60 | logit | 2.10 % | 0.25021 | 0,25000 | 15,517 |
| XAUUSD | 60 | gbm | 2.10 % | 0.25021 | 0,25000 | 15,517 |

## 8. Sensibilidad (no son hipótesis nuevas)

| Instrumento | h | Contrato | Modelo | Variante | n | Acierto | EV |
|---|---|---|---|---|---|---|---|
| AUDUSD | 1 | binaria | gbm | B_lat60 | 9303 | 53.0 % | -0.016 |
| AUDUSD | 1 | binaria | gbm | B_tieloss | 901 | 60.3 % | -0.220 |
| AUDUSD | 1 | binaria | logit | B_lat60 | 5578 | 52.9 % | -0.017 |
| AUDUSD | 1 | binaria | logit | B_tieloss | 228 | 52.1 % | -0.107 |
| AUDUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| AUDUSD | 5 | binaria | gbm | B_lat60 | 4210 | 56.1 % | 0.036 |
| AUDUSD | 5 | binaria | gbm | B_tieloss | 1709 | 57.8 % | 0.033 |
| AUDUSD | 5 | binaria | logit | B_lat60 | 4760 | 54.7 % | 0.012 |
| AUDUSD | 5 | binaria | logit | B_tieloss | 1464 | 57.7 % | 0.032 |
| AUDUSD | 5 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 5 | contado | logit | B_lat60 | 0 | — | — |
| AUDUSD | 15 | binaria | gbm | B_lat60 | 2261 | 56.9 % | 0.053 |
| AUDUSD | 15 | binaria | gbm | B_tieloss | 978 | 58.4 % | 0.061 |
| AUDUSD | 15 | binaria | logit | B_lat60 | 1614 | 52.6 % | -0.026 |
| AUDUSD | 15 | binaria | logit | B_tieloss | 1019 | 53.0 % | -0.036 |
| AUDUSD | 15 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 15 | contado | logit | B_lat60 | 0 | — | — |
| AUDUSD | 60 | binaria | gbm | B_lat60 | 1499 | 52.1 % | -0.036 |
| AUDUSD | 60 | binaria | gbm | B_tieloss | 1187 | 51.2 % | -0.062 |
| AUDUSD | 60 | binaria | logit | B_lat60 | 1489 | 50.6 % | -0.064 |
| AUDUSD | 60 | binaria | logit | B_tieloss | 1214 | 50.6 % | -0.072 |
| AUDUSD | 60 | contado | gbm | B_lat60 | 0 | — | — |
| AUDUSD | 60 | contado | logit | B_lat60 | 2 | 50.0 % | 9.345 |
| BTCUSDT | 1 | binaria | gbm | B_lat60 | 217663 | 52.1 % | -0.034 |
| BTCUSDT | 1 | binaria | gbm | B_tieloss | 94011 | 56.4 % | 0.003 |
| BTCUSDT | 1 | binaria | logit | B_lat60 | 77946 | 52.0 % | -0.038 |
| BTCUSDT | 1 | binaria | logit | B_tieloss | 42504 | 54.6 % | 0.006 |
| BTCUSDT | 1 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 1 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 5 | binaria | gbm | B_lat60 | 30704 | 54.2 % | 0.003 |
| BTCUSDT | 5 | binaria | gbm | B_tieloss | 28772 | 55.3 % | 0.021 |
| BTCUSDT | 5 | binaria | logit | B_lat60 | 30581 | 54.4 % | 0.007 |
| BTCUSDT | 5 | binaria | logit | B_tieloss | 28484 | 54.7 % | 0.009 |
| BTCUSDT | 5 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 5 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 15 | binaria | gbm | B_lat60 | 15923 | 54.9 % | 0.016 |
| BTCUSDT | 15 | binaria | gbm | B_tieloss | 15788 | 55.5 % | 0.026 |
| BTCUSDT | 15 | binaria | logit | B_lat60 | 30856 | 55.4 % | 0.024 |
| BTCUSDT | 15 | binaria | logit | B_tieloss | 30591 | 56.1 % | 0.037 |
| BTCUSDT | 15 | contado | gbm | B_lat60 | 0 | — | — |
| BTCUSDT | 15 | contado | logit | B_lat60 | 0 | — | — |
| BTCUSDT | 60 | binaria | gbm | B_lat60 | 3665 | 52.6 % | -0.026 |
| BTCUSDT | 60 | binaria | gbm | B_tieloss | 3660 | 53.2 % | -0.016 |
| BTCUSDT | 60 | binaria | logit | B_lat60 | 5914 | 56.5 % | 0.045 |
| BTCUSDT | 60 | binaria | logit | B_tieloss | 5898 | 56.7 % | 0.048 |
| BTCUSDT | 60 | contado | gbm | B_lat60 | 16 | 31.2 % | -41.205 |
| BTCUSDT | 60 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 1 | binaria | gbm | B_lat60 | 5374 | 52.7 % | -0.021 |
| EURUSD | 1 | binaria | gbm | B_tieloss | 157 | 58.2 % | -0.034 |
| EURUSD | 1 | binaria | logit | B_lat60 | 2006 | 52.1 % | -0.031 |
| EURUSD | 1 | binaria | logit | B_tieloss | 224 | 54.3 % | -0.017 |
| EURUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| EURUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 5 | binaria | gbm | B_lat60 | 1142 | 51.3 % | -0.048 |
| EURUSD | 5 | binaria | gbm | B_tieloss | 413 | 54.3 % | -0.086 |
| EURUSD | 5 | binaria | logit | B_lat60 | 4859 | 50.9 % | -0.055 |
| EURUSD | 5 | binaria | logit | B_tieloss | 1160 | 51.8 % | -0.069 |
| EURUSD | 5 | contado | gbm | B_lat60 | 0 | — | — |
| EURUSD | 5 | contado | logit | B_lat60 | 0 | — | — |
| EURUSD | 15 | binaria | gbm | B_lat60 | 1841 | 53.9 % | -0.002 |
| EURUSD | 15 | binaria | gbm | B_tieloss | 983 | 54.7 % | -0.008 |
| EURUSD | 15 | binaria | logit | B_lat60 | 2273 | 52.1 % | -0.036 |
| EURUSD | 15 | binaria | logit | B_tieloss | 1457 | 52.3 % | -0.044 |
| EURUSD | 15 | contado | gbm | B_lat60 | 3 | 33.3 % | 0.654 |
| EURUSD | 15 | contado | logit | B_lat60 | 6 | 33.3 % | -1.783 |
| EURUSD | 60 | binaria | gbm | B_lat60 | 0 | — | — |
| EURUSD | 60 | binaria | gbm | B_tieloss | 0 | — | — |
| EURUSD | 60 | binaria | logit | B_lat60 | 0 | — | — |
| EURUSD | 60 | binaria | logit | B_tieloss | 0 | — | — |
| EURUSD | 60 | contado | gbm | B_lat60 | 118 | 52.5 % | -0.271 |
| EURUSD | 60 | contado | logit | B_lat60 | 115 | 44.3 % | -1.500 |
| GBPUSD | 1 | binaria | gbm | B_lat60 | 4710 | 51.6 % | -0.037 |
| GBPUSD | 1 | binaria | gbm | B_tieloss | 551 | 57.5 % | -0.268 |
| GBPUSD | 1 | binaria | logit | B_lat60 | 5375 | 51.8 % | -0.039 |
| GBPUSD | 1 | binaria | logit | B_tieloss | 979 | 59.9 % | 0.030 |
| GBPUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| GBPUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| GBPUSD | 5 | binaria | gbm | B_lat60 | 6269 | 53.6 % | -0.009 |
| GBPUSD | 5 | binaria | gbm | B_tieloss | 1682 | 57.0 % | 0.026 |
| GBPUSD | 5 | binaria | logit | B_lat60 | 1476 | 52.5 % | -0.028 |
| GBPUSD | 5 | binaria | logit | B_tieloss | 476 | 57.0 % | -0.013 |
| GBPUSD | 5 | contado | gbm | B_lat60 | 13 | 76.9 % | 5.112 |
| GBPUSD | 5 | contado | logit | B_lat60 | 0 | — | — |
| GBPUSD | 15 | binaria | gbm | B_lat60 | 2356 | 54.7 % | 0.011 |
| GBPUSD | 15 | binaria | gbm | B_tieloss | 1155 | 54.1 % | -0.007 |
| GBPUSD | 15 | binaria | logit | B_lat60 | 1633 | 54.6 % | 0.009 |
| GBPUSD | 15 | binaria | logit | B_tieloss | 992 | 55.8 % | 0.018 |
| GBPUSD | 15 | contado | gbm | B_lat60 | 49 | 49.0 % | -0.167 |
| GBPUSD | 15 | contado | logit | B_lat60 | 24 | 66.7 % | 1.242 |
| GBPUSD | 60 | binaria | gbm | B_lat60 | 334 | 49.1 % | -0.091 |
| GBPUSD | 60 | binaria | gbm | B_tieloss | 21 | 52.4 % | -0.031 |
| GBPUSD | 60 | binaria | logit | B_lat60 | 0 | — | — |
| GBPUSD | 60 | binaria | logit | B_tieloss | 0 | — | — |
| GBPUSD | 60 | contado | gbm | B_lat60 | 74 | 44.6 % | -5.826 |
| GBPUSD | 60 | contado | logit | B_lat60 | 24 | 33.3 % | -11.085 |
| USDJPY | 1 | binaria | gbm | B_lat60 | 17958 | 53.8 % | -0.004 |
| USDJPY | 1 | binaria | gbm | B_tieloss | 3787 | 55.2 % | -0.145 |
| USDJPY | 1 | binaria | logit | B_lat60 | 10184 | 54.4 % | 0.006 |
| USDJPY | 1 | binaria | logit | B_tieloss | 1685 | 55.9 % | 0.002 |
| USDJPY | 1 | contado | gbm | B_lat60 | 0 | — | — |
| USDJPY | 1 | contado | logit | B_lat60 | 0 | — | — |
| USDJPY | 5 | binaria | gbm | B_lat60 | 10106 | 54.6 % | 0.010 |
| USDJPY | 5 | binaria | gbm | B_tieloss | 5838 | 55.7 % | 0.009 |
| USDJPY | 5 | binaria | logit | B_lat60 | 10840 | 54.1 % | 0.001 |
| USDJPY | 5 | binaria | logit | B_tieloss | 4895 | 53.8 % | -0.021 |
| USDJPY | 5 | contado | gbm | B_lat60 | 258 | 49.6 % | -0.280 |
| USDJPY | 5 | contado | logit | B_lat60 | 51 | 51.0 % | 0.455 |
| USDJPY | 15 | binaria | gbm | B_lat60 | 5001 | 54.1 % | 0.002 |
| USDJPY | 15 | binaria | gbm | B_tieloss | 3233 | 54.3 % | -0.003 |
| USDJPY | 15 | binaria | logit | B_lat60 | 11648 | 53.4 % | -0.012 |
| USDJPY | 15 | binaria | logit | B_tieloss | 5758 | 53.0 % | -0.029 |
| USDJPY | 15 | contado | gbm | B_lat60 | 579 | 46.3 % | -0.806 |
| USDJPY | 15 | contado | logit | B_lat60 | 1227 | 48.3 % | -0.926 |
| USDJPY | 60 | binaria | gbm | B_lat60 | 1729 | 53.3 % | -0.014 |
| USDJPY | 60 | binaria | gbm | B_tieloss | 475 | 51.4 % | -0.054 |
| USDJPY | 60 | binaria | logit | B_lat60 | 2511 | 52.9 % | -0.022 |
| USDJPY | 60 | binaria | logit | B_tieloss | 1025 | 53.7 % | -0.011 |
| USDJPY | 60 | contado | gbm | B_lat60 | 2480 | 48.4 % | -0.980 |
| USDJPY | 60 | contado | logit | B_lat60 | 2637 | 48.5 % | -0.872 |
| XAUUSD | 1 | binaria | gbm | B_lat60 | 6494 | 52.2 % | -0.033 |
| XAUUSD | 1 | binaria | gbm | B_tieloss | 4275 | 54.3 % | -0.005 |
| XAUUSD | 1 | binaria | logit | B_lat60 | 7890 | 52.5 % | -0.028 |
| XAUUSD | 1 | binaria | logit | B_tieloss | 4752 | 56.0 % | 0.032 |
| XAUUSD | 1 | contado | gbm | B_lat60 | 0 | — | — |
| XAUUSD | 1 | contado | logit | B_lat60 | 0 | — | — |
| XAUUSD | 5 | binaria | gbm | B_lat60 | 189 | 47.3 % | -0.123 |
| XAUUSD | 5 | binaria | gbm | B_tieloss | 172 | 54.1 % | 0.000 |
| XAUUSD | 5 | binaria | logit | B_lat60 | 3312 | 51.8 % | -0.041 |
| XAUUSD | 5 | binaria | logit | B_tieloss | 1875 | 50.9 % | -0.060 |
| XAUUSD | 5 | contado | gbm | B_lat60 | 0 | — | — |
| XAUUSD | 5 | contado | logit | B_lat60 | 1 | 0.0 % | -10.015 |
| XAUUSD | 15 | binaria | gbm | B_lat60 | 0 | — | — |
| XAUUSD | 15 | binaria | gbm | B_tieloss | 0 | — | — |
| XAUUSD | 15 | binaria | logit | B_lat60 | 0 | — | — |
| XAUUSD | 15 | binaria | logit | B_tieloss | 0 | — | — |
| XAUUSD | 15 | contado | gbm | B_lat60 | 1 | 0.0 % | -19.376 |
| XAUUSD | 15 | contado | logit | B_lat60 | 31 | 51.6 % | -1.484 |
| XAUUSD | 60 | binaria | gbm | B_lat60 | 1144 | 51.9 % | -0.040 |
| XAUUSD | 60 | binaria | gbm | B_tieloss | 1144 | 51.1 % | -0.054 |
| XAUUSD | 60 | binaria | logit | B_lat60 | 1144 | 51.9 % | -0.040 |
| XAUUSD | 60 | binaria | logit | B_tieloss | 1144 | 51.1 % | -0.054 |
| XAUUSD | 60 | contado | gbm | B_lat60 | 1066 | 49.6 % | -0.725 |
| XAUUSD | 60 | contado | logit | B_lat60 | 1066 | 49.6 % | -0.725 |

## 9. Acierto alto ≠ rentabilidad (demostración)

Entradas al azar con objetivo de ganancia de 1σ y límite de pérdida de 10σ (σ = volatilidad a 15 min).

| Instrumento | n | Objetivo alcanzado («acierto») | Ganadoras netas de costos | EV neto (pb) | Ganancia media (pb) | Pérdida media (pb) |
|---|---|---|---|---|---|---|
| AUDUSD | 19,711 | 78.7 % | 79.1 % | -1.63 | 4.42 | -24.52 |
| BTCUSDT | 19,998 | 78.2 % | 42.9 % | -20.80 | 17.26 | -49.39 |
| EURUSD | 19,707 | 79.4 % | 80.1 % | -0.66 | 3.24 | -16.41 |
| GBPUSD | 19,747 | 78.4 % | 78.9 % | -0.90 | 3.70 | -18.10 |
| USDJPY | 19,733 | 78.4 % | 79.2 % | -0.89 | 4.07 | -19.75 |
| XAUUSD | 19,415 | 78.8 % | 79.5 % | -1.46 | 6.47 | -32.29 |
