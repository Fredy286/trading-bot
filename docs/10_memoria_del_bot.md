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
- **Trampas ya vistas:**
  - el precio bid crea reversiones falsas en el cierre de Nueva York (usar precio medio);
  - con martingala, el «85–90 %» sale del azar;
  - el OTC no se puede verificar;
  - el acierto al cierre exacto de la vela desaparece con el clic humano;
  - unidades de tiempo de pandas (microsegundos).
- **El usuario:** opera solo en demo; tiene libres las noches desde las 21:00 de Bogotá; su plataforma (IQ Option)
  no tiene BTC a 1 min (sí binaria de 15 min con pago del 87 %).

## Ideas pendientes (prioridad de arriba abajo)

| # | Idea | Por qué | Estado |
|---|---|---|---|
| 1 | Variables de «reloj» (minuto en el cuarto de hora, hora de financiación 00/08/16 UTC) en el GBM de BTC | Preprint de Kim y Hansen (2026): ráfagas de volumen y dependencia serial en los cuartos de hora | **Estudio 33** (pre-registro aea2c8b, código a1598a3), en la cola de GitHub Actions desde el 2026-10-29. Documentar el resultado |
| 2 | Confirmación de ETH con umbral: modelo congelado de ETH (12 meses hasta el 2026-10-25) y evaluación única con datos nuevos | Estudio 26 pasó (58,8 %) | Por pre-registrar (confirmación) |
| 3 | Selector BTC + ETH con p ≥ 0,60 en el horario del usuario (21:00–01:00 Bogotá) | Más señales de alta confianza en sus horas | Idea |
| 4 | Traders con historial **verificado** (Myfxbook, Darwinex, eToro, ranking de TradingView): ¿quién acierta ≥ 60 % de verdad y cómo? | El usuario cree que hay algo detrás de quien acierta a diario | Primera revisión hecha (docs/06, sección 3b): menos del 1 % gana de forma repetida; el acierto alto suele esconder pérdidas grandes. Siguiente: buscar cuentas concretas con historial largo y desarmar su estilo (martes) |
| 5 | Reversión nocturna: **réplica en un año no usado (2024-09 → 2025-08, ticks de HistData con bid y ask)** + filtro de «diferencial normal» (diferencial en la señal ≤ 1,5 × mediana de las medianas nocturnas de los 20 días previos) + la variante 30/2,5/5 min | Nunca se miró ese año con precio medio en los 24 pares; tras el cierre de NY el diferencial se abre y puede fabricar reversiones del precio medio que ninguna plataforma paga (CME 2026; BidFX vía financefeeds) | **Estudio 34 hecho:** H34a y H34c pasan (réplica); H34b (diferencial normal) no pasa → la ventaja es de microestructura. Siguiente: Estudio 36 (precio de Deriv) |
| 6 | Auditoría prospectiva de canales (Estudio 32): tabla descriptiva mensual, y buscar más canales con señales **no OTC** publicadas antes de la entrada | Comprobar con datos frescos si alguien acierta | En marcha (captura cada hora) |
| 7 | Comparar precios de Deriv con HistData en los mismos minutos (calidad del registro diario) | Validar la fuente de la demo | Idea |
