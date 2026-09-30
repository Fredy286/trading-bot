# Resultados empíricos — etapa `dev`

- Commit del código: `4f9c5675805a1367878288ba43dfc2abc53d039a` — hash de configuración: `2bcecccbf2f9` — versión 0.1.0
- Hipótesis evaluadas (corrección de Holm sobre todas): **0**
- Contrato binario: pago 85%, empate = refund; contado: spread observado + comisión.

## 1. Veredicto mecánico

**SIN SEÑAL.** Ninguna combinación de instrumento, horizonte, contrato, modelo y política cumple los cinco criterios pre-registrados. El sistema debe operar en modo «sin señal».

## 2. Calidad de datos

| Instrumento | Minutos en sesión | Minutos cerrados | Min. sin ticks aislados | Spread mediano | Desde | Hasta |
|---|---|---|---|---|---|---|
| BTCUSDT | 2,978,134 | 1,226 | 8 | 0.000000 | 2021-01-01 | 2026-08-31 |

## 3. Movimiento típico frente a costos (periodo de prueba)

Umbral de contado `p* ≈ 0,5 + costo/(2·movimiento)`; si supera 100 % es inalcanzable.

| Instrumento | h (min) | Mov. medio abs. (pb) | Costo medio ida y vuelta (pb) | p* contado | Empates |
|---|---|---|---|---|---|

## 6. ¿Se alcanza un acierto ≥ 80%?

Mejor acierto en cualquier nivel de cobertura (umbral fijado con el tramo de calibración, n ≥ 100), sin costos.

Sin datos.

## 7. Calibración fuera de muestra (P(sube))

| Instrumento | h | Modelo | ECE | Brier | Brier ref. (0,5) | n |
|---|---|---|---|---|---|---|

## 9. Acierto alto ≠ rentabilidad (demostración)

Entradas al azar con objetivo de ganancia de 1σ y límite de pérdida de 10σ (σ = volatilidad a 15 min).

| Instrumento | n | Objetivo alcanzado («acierto») | Ganadoras netas de costos | EV neto (pb) | Ganancia media (pb) | Pérdida media (pb) |
|---|---|---|---|---|---|---|
| BTCUSDT | 19,998 | 78.2 % | 42.9 % | -20.80 | 17.26 | -49.39 |
