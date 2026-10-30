# Memoria del bot (aprendizaje continuo)

Archivo de trabajo de la investigación diaria autónoma. Aquí vive la **lista de ideas** con su estado, para no
repetir trabajo y para aprender de lo ya probado. La rutina la lee al empezar y la actualiza al terminar.
Lo detallado está en docs/01 (pre-registros y resultados), docs/06 (ideas de terceros), docs/08 (mejoras) y docs/09
(bitácora diaria).

## Lo aprendido (resumen que no debe olvidarse)

- **Lo que funciona en desarrollo (sin confirmar con datos nuevos):**
  1. BTC 1 min con aviso en el segundo 50 y clic a +10 s: 57–58 %. Con p ≥ 0,60, ~60–62 % (Estudios 16, 20, 21).
  2. Reversión nocturna de Bollinger (20, 2) en divisas, 21–24 UTC, 3 min: 57 % con precio medio y clic a +10 s.
     Hora fuerte 22 UTC (~62 %). Sólida ante cambios de parámetros (Estudios 25, 27, 28, 31).
  3. ETH con aviso anticipado y p ≥ 0,60: 58,8 % (653 ops; Estudio 26).
- **Lo que NO funciona (no repetir sin una idea realmente distinta):** indicadores clásicos (RSI, MACD, medias,
  Fibonacci, ICT, zonas), patrones de velas por color y posición del reloj (MHI, Milhão, Torres…), «catalogación»
  de horarios, Kronos, análogos, Kalman, ETH/USDC como variables extra para BTC, la reversión en otras horas u otros
  mercados (oro, S&P, BTC), y los canales de señales auditados (49–51 % en la primera entrada).
- **La reversión nocturna vive en el diferencial abierto (Estudio 34):** se replica en 2024–25 (56,2 %; 5 min 59,6 %),
  pero el acierto sale de los minutos con diferencial 3–60 veces lo normal (60–66 %); con diferencial normal, 53–54 %.
  Antes de mejorarla, comprobar que una plataforma real pague ese movimiento.
- **Las ventajas viven en el precio de cada fuente (Estudios 34, 36 y 37):**
  - BTC: las señales calificadas con Coinbase aciertan 52,2 % (Binance 57,6 %);
  - divisas de noche: la reversión existe en Deriv (56,4 %; 5 min 60,7 %) y en HistData, pero con señales distintas
    (dirección coincidente 46 %).

  - BTC con el precio del bróker Deriv: 52,4 % (Estudio 38). El modelo de BTC predice el precio de BINANCE, no
    el de BTC en general.
  - **Pero en las bolsas en USDT la ventaja sobrevive en buena parte (Estudio 41):**

    | Precio de juicio | Todas | p ≥ 0,60 |
    |---|---|---|
    | OKX | 54,9 % | 57,4 % |
    | Bybit | 54,3 % | 57,0 % |
    | Promedio de Binance, Bybit y OKX (el de IQ Option) | 55,5 % | **58,6 %** (pasa) |

    Se pierde en las bolsas en dólares (Coinbase, Deriv). Confirmación: Estudio 43 (después del 2027-01-18).

  Regla: una señal solo sirve si se calcula con el MISMO precio con el que liquida la plataforma.
- **Trampas ya vistas:**
  - el precio bid crea reversiones falsas en el cierre de Nueva York (usar precio medio);
  - con martingala, el «85–90 %» sale del azar;
  - el OTC no se puede verificar;
  - el acierto al cierre exacto de la vela desaparece con el clic humano;
  - unidades de tiempo de pandas (microsegundos).
- **Deriv, desarmado (2026-10-30, consultas `proposal` y `contracts_for` a las 03:55 UTC):**
  - el pago de «sube/baja» a 15 min en divisas **depende del movimiento reciente**: tras una caída, «sube» paga
    menos (NZDJPY −3,7 pb en 15 min: CALL 51,4 %, PUT 100,1 %; AUDCAD −3,4 pb: CALL 75,1 %, PUT 81,8 %). Su modelo de
    precios ya cobra la reversión de corto plazo;
  - el lado favorable casi siempre queda en 81,8 % (equilibrio 55,0 %);
  - oro: sube/baja desde 5 min; índices (OTC_NDX, OTC_SPC, OTC_DJI): desde 15 min; BTC y ETH: solo multiplicadores;
  - más el bloqueo de 21:00 a 23:59 UTC (ítem 49). **Conclusión: Deriv no sirve para nuestras ventajas.** No
    proponer estudios de reversión ni de BTC en Deriv. Datos: `results/estudio39/ofertas_deriv_2026-10-30T0355Z.json`.
- **IQ Option, pista sobre su precio de BTC (2026-10-30, página pública iqoption.com/en, sin cuenta):**
  - «Bitcoin» aparece con compra/venta a 1 centavo (78 258,98 / 78 258,99), el formato del libro de Binance al
    contado (Bybit y OKX cotizan de 0,1 en 0,1);
  - «Bitcoin-PerpFuture» (paso de 0,1) va 53 USD por debajo, como el perpetuo de Binance (−44 ± 5 USD esa noche);
  - las bolsas en dólares (Coinbase, Kraken, Bitstamp) estaban unos 205 USD más abajo.

  Primera hipótesis: IQ Option toma el precio de BTC de Binance.
- **IQ Option, captura del usuario con hora (2026-10-29 23:06:57 Bogotá; detalle en el Estudio 41 de docs/01):**
  - marcaba 77 925,99 (compra/venta con 4 decimales: precio calculado). En ese segundo Binance marcaba 77 934, OKX
    77 925, Bybit 77 918,9 y Coinbase 77 725;
  - promedio de Binance, Bybit y OKX: 77 925,97. **IQ Option usa un PROMEDIO de bolsas en USDT**, no Binance solo;
  - su binaria de BTC vence en horas fijas (cada 15 min), cierra la compra 5 min antes y paga 87 %. Es el caso R = 5
    del Estudio 19: 53,2 % con el precio de Binance, por debajo del equilibrio (53,5 %). **Esa binaria no tiene
    ventaja con nuestro modelo.** Falta conocer duraciones y pago del «blitz» de BTC;
  - en la captura el saldo era de 0,24 USD (posible cuenta real): recordar al usuario que practique en la cuenta de
    práctica.
- **El usuario:** opera solo en demo; tiene libres las noches desde las 21:00 de Bogotá; su plataforma (IQ Option)
  no tiene BTC a 1 min (sí binaria de 15 min con pago del 87 %).

## Ideas pendientes (prioridad de arriba abajo)

| # | Idea | Por qué | Estado |
|---|---|---|---|
| 0 | **Aprender con el precio de la plataforma**: entrenar y juzgar los modelos con el precio de la plataforma del usuario. IQ Option liquida BTC con un promedio de bolsas en USDT, que SÍ se puede reconstruir con datos públicos (Binance, Bybit, OKX). Deriv quedó descartado | Estudios 34, 36–38 y 41 | **Estudio 42** (blitz de BTC de 3 min al 86 %, modelo entrenado con el promedio) pre-registrado y en ejecución. Si pasa: confirmación con datos nuevos y modo de práctica del blitz |
| 0b | Reversión en Deriv: Deriv no deja operar divisas de 20:50 a 22:00 UTC, exige ≥ 15 min y (consulta del 2026-10-29 a las 22:05 UTC) **no permite contratos de divisas de menos de 5 h de 21:00 a 23:59 UTC**. Estudio 39 (22–24 UTC, 15 min) no pasa (53,8 %); a las 22 UTC 56,7 % (post hoc) | Estudios 36, 39 y 40 | **DESCARTADA para operar** (Deriv cierra toda la ventana útil). El Estudio 40 sigue solo como medida científica (evaluación única tras el 2027-01-18). No buscar más horarios de reversión en Deriv. La reversión solo tendría uso en una plataforma que permita 3–5 min de 21 a 24 UTC en pares NO OTC y liquide con un precio cuyos datos podamos descargar |
| 1 | Variables de «reloj» (minuto en el cuarto de hora, hora de financiación 00/08/16 UTC) en el GBM de BTC | Preprint de Kim y Hansen (2026): ráfagas de volumen y dependencia serial en los cuartos de hora | **Estudio 33** (pre-registro aea2c8b, código a1598a3), en la cola de GitHub Actions desde el 2026-10-29. Documentar el resultado |
| 2 | Confirmación de ETH con umbral: modelo congelado de ETH (12 meses hasta el 2026-10-25) y evaluación única con datos nuevos | Estudio 26 pasó (58,8 %) | Por pre-registrar (confirmación) |
| 3 | Selector BTC + ETH con p ≥ 0,60 en el horario del usuario (21:00–01:00 Bogotá) | Más señales de alta confianza en sus horas | Idea |
| 4 | Traders con historial **verificado** (Myfxbook, Darwinex, eToro, ranking de TradingView): ¿quién acierta ≥ 60 % de verdad y cómo? | El usuario cree que hay algo detrás de quien acierta a diario | Primera revisión hecha (docs/06, sección 3b): menos del 1 % gana de forma repetida; el acierto alto suele esconder pérdidas grandes. Siguiente: buscar cuentas concretas con historial largo y desarmar su estilo (martes) |
| 5 | Reversión nocturna: **réplica en un año no usado (2024-09 → 2025-08, ticks de HistData con bid y ask)** + filtro de «diferencial normal» (diferencial en la señal ≤ 1,5 × mediana de las medianas nocturnas de los 20 días previos) + la variante 30/2,5/5 min | Nunca se miró ese año con precio medio en los 24 pares; tras el cierre de NY el diferencial se abre y puede fabricar reversiones del precio medio que ninguna plataforma paga (CME 2026; BidFX vía financefeeds) | **Estudio 34 hecho:** H34a y H34c pasan (réplica); H34b (diferencial normal) no pasa → la ventaja es de microestructura. Siguiente: Estudio 36 (precio de Deriv) |
| 6 | Auditoría prospectiva de canales (Estudio 32): tabla descriptiva mensual, y buscar más canales con señales **no OTC** publicadas antes de la entrada | Comprobar con datos frescos si alguien acierta | En marcha (captura cada hora) |
| 7 | Comparar precios de Deriv con HistData en los mismos minutos (calidad del registro diario) | Validar la fuente de la demo | Idea |
