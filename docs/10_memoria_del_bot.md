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
  mercados (oro, S&P, BTC), y los canales de señales auditados (49–51 % en la primera entrada). Tampoco las
  «estrategias de ChatGPT» elegidas por su prueba sobre el pasado (Estudio 45: las 2 mejores de 5 no destacan en el
  semestre siguiente; las cifras de +900–1 500 % en 6 meses no salen ni con 50× de apalancamiento).
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
  - **Ojo: la ventaja del blitz depende del promedio exacto** (nota de solidez del Estudio 42, 2026-10-31).
    En octubre: con 3 bolsas 56,8 %; con 5 (+ KuCoin, Bitget) 54,4 %, y 14 de los 16 resultados distintos
    favorecían al de 3. Las capturas apuntan al de 3 bolsas (evidencia débil). El modo blitz graba 6 bolsas
    tras cada aviso y `tbot blitz comparar` lo resuelve con los precios de entrada que anote el usuario.
  - **Resuelto (Estudio 47, 2026-10-31):** se leyeron 275 velas de 6 capturas del usuario. El precio de BTC de
    IQ Option es un promedio con pesos: Binance 0,34, OKX 0,22, Gate 0,37 y Bybit 0,07 (con MEXC, algo de peso
    también); error de 1,5 USD. Con ese precio reconstruido, el blitz acierta 55,3 % en desarrollo (octubre 56,3 %),
    igual que con 3 bolsas. Confirmación: H44c (enmienda del Estudio 44).
  - **Demora del clic en el blitz (2026-11-03):** 10 s → 55,3 %; 20 s → 54,9 %; 30 s → 54,6 %; 40 s → 54,2 %. El panel
    blitz marca «aún vale» entre 15 y 30 s y «TARDE» después (antes eran 15 s, copiados del modelo de 1 min).
  - **El blitz ya está en el registro diario de la nube (2026-11-04):** señales del modelo congelado con su resultado
    sellado (3 bolsas y precio IQ reconstruido). Desde GitHub (EE. UU.) la API de Binance (451) y la de Bybit (403)
    están bloqueadas. Se usan los archivos públicos (data.binance.vision, public.bybit.com), la API de OKX y los
    archivos de Gate. Las variables son idénticas a las del entrenamiento (diferencia 0). Del 26-10 al 03-11: 73
    señales (unas 8 por día).
  - Gate publica su archivo diario de velas con 1–2 días de retraso: el día del blitz queda «pendiente» y se completa
    en la corrida siguiente. Para evaluar el Estudio 44 en enero, esperar a que exista el archivo del 2027-01-18.
  - **Avisos en el celular (2026-11-07):** `scripts/iniciar_blitz.sh --telegram` manda cada aviso al Telegram del
    `.env` (el usuario ya tenía token y chat configurados). `tbot telegram probar` manda un solo mensaje de prueba.

  Regla: una señal solo sirve si se calcula con el MISMO precio con el que liquida la plataforma.
- **Trampas ya vistas:**
  - el precio bid crea reversiones falsas en el cierre de Nueva York (usar precio medio);
  - con martingala, el «85–90 %» sale del azar;
  - el OTC no se puede verificar;
  - el acierto al cierre exacto de la vela desaparece con el clic humano;
  - unidades de tiempo de pandas (microsegundos).
  - estudio y modo en vivo deben usar la MISMA función para juzgar gana/pierde/empate (ítem 51: con precios
    promediados, una regla de redondeo copiada cambiaba el empate).
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
- **Lección de la semana 2026-10-26 → 11-01:** casi todo lo que «mejora» el modelo en log-loss no mejora la
  política (Estudios 24, 33); lo que se mueve de verdad es (1) filtrar por confianza y (2) usar el precio exacto de
  liquidación. Priorizar estudios sobre esas dos palancas antes que variables nuevas.
- **Literatura de microestructura (2026-11-02, solo resúmenes del buscador; las páginas no abren desde la nube):**
  Binance lidera la formación del precio de BTC frente a Coinbase, y la integración se rompe a frecuencias muy altas.
  Una tesis con datos tick a tick vio bolsas que siguen a otras con hasta 15 s de retraso; un tutorial no vio líder
  claro entre Binance y OKX a 1 s. Encaja con lo nuestro: las bolsas en USDT copian a Binance en segundos (la ventaja
  sobrevive), y las de dólares tienen su propio ruido. Consecuencia: variables de «qué bolsa va adelantada» solo
  pueden servir al segundo, no con velas de 1 min.
- **El acierto del modelo va por rachas (Estudio 48, 2026-11-05):** si viene fallando una semana, suele seguir algo
  peor la siguiente (correlación 0,36–0,40). Saltar las malas rachas sube el acierto por operación (~57,4 % frente a
  56,5 %), pero casi no sube la ganancia total. Es una 4.ª forma de «confianza», útil para operar menos.
- **La ventaja del blitz vive en los últimos 20 s de cada minuto (Estudio 50, 2026-11-07):** un modelo que decide
  cada 10 s acierta 58 % en los segundos 40–50 y 51 % (azar) en los segundos 20–30. En conjunto es peor que el blitz
  actual (54,7 % frente a 56,8 % con p ≥ 0,57) y nunca llega a p ≥ 0,60. Revisar más seguido no da más señales
  buenas; para más señales hay que vigilar **más monedas** (Estudio 51, ETH).
- **IQ Option por dentro (2026-11-07, revisado en la sesión del usuario, sin operar):**
  - **Blitz con precio real:** solo Bitcoin y Solana, cerrados el fin de semana (abren el domingo 22:00).
  - **ETH, XRP, Litecoin, Dogecoin, Cardano y Polkadot:** solo versión «(OTC)», con precio propio de la plataforma. El
    ETH/USD (OTC) iba 140 USD por encima del real y en otra dirección.
  - **«Ethereum» real:** solo binaria de 15 min (87 %) y digital al próximo múltiplo de 5 min (84 %, compra hasta 30 s
    antes).
  - **Regla:** nunca estudiar ni recomendar activos OTC.
- **Más monedas = más señales (Estudio 51, 2026-11-07):** la receta del blitz funciona con ETH tan bien como con BTC
  (56,9 % con p ≥ 0,57) y da 4,5 veces más señales; casi nunca coinciden. Es la vía para tener más señales sin bajar el
  acierto, siempre que la plataforma tenga el contrato de esa moneda.
- **Evaluaciones únicas (2026-11-07):** antes de calcular, comprobar que no falte ningún día de datos (el registro
  diario a veces llega tarde). El Estudio 49 ya lo hace; las confirmaciones que se programen en enero (12, 14, 15, 16,
  19, 21, 29, 35, 40, 43, 44, 46) deben hacerlo igual.
- **Copy trading (2026-11-03):** copiar a quien va ganando aumenta el riesgo heredado, no el acierto; las listas de
  cuentas «verificadas» ya están filtradas por supervivencia. No buscar ahí reglas; como mucho, piezas medibles con
  su historial completo.
- **El usuario:** opera solo en demo; tiene libres las noches desde las 21:00 de Bogotá; su plataforma (IQ Option)
  no tiene BTC a 1 min (sí binaria de 15 min con pago del 87 %).

## Ideas pendientes (prioridad de arriba abajo; repriorizado el 2026-11-01)

| # | Idea | Por qué | Estado |
|---|---|---|---|
| 0 | **Aprender con el precio de la plataforma**: entrenar y juzgar los modelos con el precio con que liquida IQ Option (promedio con pesos de bolsas en USDT, Estudio 47) | Estudios 34, 36–38, 41, 42 y 47 | **Estudio 42 PASA en desarrollo** (55,3 %, EV +0,029, 12 de 13 meses); con el precio reconstruido del Estudio 47, 55,3 % (octubre 56,3 %). Modelo congelado `BTCUSDT-blitz3-compuesto-0f8694`, modo de práctica (`scripts/iniciar_blitz.sh`). Confirmación: Estudios 44 (H44a–c) y 46, una vez, después del 2027-01-18. **Siguiente:** (a) variables del propio precio reconstruido (no del de Binance) en un estudio nuevo pre-registrado, sin tocar el modelo congelado; (b) **ETH en blitz: Estudio 51 PASA, pero NO aplica a IQ Option** (allí solo hay ETH/USD OTC, precio propio; 2026-11-07) (2026-11-07): p ≥ 0,57 → 31 señales/día con 56,9 % (4 bolsas 56,7 %), casi sin coincidir con BTC; modelo congelado `ETHUSDT-blitz3-compuesto-5d7319`, modo `scripts/iniciar_blitz.sh --eth`, registro `blitz_eth` en la nube; confirmación: Estudio 52 (enero de 2027). **Siguiente:** Solana, la única otra criptomoneda con blitz de precio real en IQ Option (Estudio 53; verificar su duración, pago y precio cuando abra, domingo 22:00) |
| 1 | Verificar en la demo de IQ Option el precio de entrada, el empate y el pago del blitz con las anotaciones del usuario (`tbot blitz comparar`) | Regla: la señal solo sirve con el MISMO precio de liquidación | Pendiente del usuario (sesión local). Sin esto, no recomendar el blitz ni siquiera en demo como algo más que práctica |
| 1b | **Medir el retraso del precio de IQ Option frente a Binance, al segundo** (con las capturas o anotaciones de la demo: hora al segundo + precio, frente a las 6 bolsas que graba el modo blitz) | Literatura (2026-11-02): Binance domina la formación del precio y otras bolsas lo siguen con unos segundos de retraso. El Estudio 47 sospechó un pequeño retraso de IQ Option. Si su precio va atrasado varios segundos, el movimiento de Binance en esos segundos anticiparía el precio de entrada y el de cierre del blitz | Pendiente del usuario (sesión local; se puede hacer junto con la idea 1). **No** sirve hacerlo con velas de 1 min: el retraso entre bolsas es de segundos y nuestra decisión llega ≥ 60 s después del último cierre de 1 min. Ya existe `c_disp` (Binance − compuesto) en el modelo del blitz |
| 2 | Traders con historial **verificado** (Myfxbook, Darwinex, eToro, ranking de TradingView): ¿quién acierta ≥ 60 % de verdad y cómo? | El usuario cree que hay algo detrás de quien acierta a diario | Primera revisión hecha (docs/06, sección 3b): menos del 1 % gana de forma repetida; el acierto alto suele esconder pérdidas grandes. Segunda revisión (2026-11-03, docs/06 sección 3c): copiar sube el riesgo (Management Science 2020), sin ganancia tras costos; ~7 % cobra en empresas de fondeo. Las páginas de cuentas concretas no abren desde la nube. **Siguiente:** solo en sesión local, bajar el CSV completo de 2–3 cuentas verificadas con ≥ 3 años (Myfxbook/Darwinex) y desarmar hora, duración y riesgo; los martes en la nube, pasar a la idea pendiente de mayor prioridad |
| 3 | Auditoría prospectiva de canales (Estudio 32) y más canales con señales **no OTC** publicadas antes de la entrada | Comprobar con datos frescos si alguien acierta | En marcha (captura cada hora, 12 canales; auditados del 2026-10-29 al 11-04). Solo 2 canales dan señales verificables, y gotraderssinaisfree dejó de publicar señales tras el 2026-10-31 (solo publicidad): en la práctica queda 1 (QuotexSignalfreee). Canales nuevos: solo en sesión local (t.me no abre desde la nube). Veredicto único el 2027-01-31 |
| 4 | Selector BTC + ETH con p ≥ 0,60 en el horario del usuario (21:00–01:00 Bogotá) | Más señales de alta confianza en sus horas | **Baja prioridad:** el modelo congelado de ETH (Estudio 35) dio 0 señales en sus primeros 5 días registrados (conteo, sin aciertos); además el usuario no tiene BTC/ETH a 1 min en su plataforma |
| 4b | **Filtro de «racha reciente» del propio modelo** (acierto de sus últimas 500 operaciones o de los últimos 7 días ≥ equilibrio) | Tercera forma de «confianza»; la ventaja va por épocas (Estudios 20 y 41) | **Estudio 48 PASA** (2026-11-05): +2,3–2,5 puntos entre tomadas y saltadas en desarrollo, +3,9–4,5 en verificación; persistencia semanal 0,36–0,40. Pero la ganancia total casi no cambia (−6 % / +5 %): sirve para operar menos con la misma ganancia. Confirmación pre-registrada: **Estudio 49** (señales registradas de H16b, código listo, se niega a correr antes del 2027-01-19; potencia ~45 %). Nada que hacer hasta entonces |
| 5 | Comparar precios de Deriv con HistData en los mismos minutos | Validar la fuente del registro nocturno | **Baja:** Deriv quedó descartado para operar; solo afecta a la medida científica |

### Ideas cerradas (no repetir)

| Idea | Cierre |
|---|---|
| Variables de «reloj» (:00/:15/:30/:45, financiación) en el GBM de BTC | Estudio 33: NO PASA (log-loss sí, política no). 2026-10-31 |
| Reversión en Deriv (cualquier horario) | Deriv bloquea divisas < 5 h de 21:00 a 23:59 UTC y cobra la reversión en el pago (Estudios 39–40, ítem 49) |
| Réplica de la reversión nocturna + filtro de diferencial normal | Estudio 34: se replica, pero vive en el diferencial abierto (60–66 %); con diferencial normal 53 % |
| Confirmación de ETH con umbral | Pre-registrada y con modelo congelado (Estudio 35); se evalúa tras el 2027-01-18 |
| Estrategias de «ChatGPT» elegidas por su prueba sobre el pasado | Estudio 45: no destacan después |
| Blitz «continuo» (decidir cada 10 s en vez de una vez por minuto) | Estudio 50: NO PASA (2026-11-07). Queda solo la idea de una 2.ª decisión en el segundo 40, para datos nuevos |
