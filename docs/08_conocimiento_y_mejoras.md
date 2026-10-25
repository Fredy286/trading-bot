# Conocimiento de mercado, disección de herramientas y mejoras propuestas (2026-10-25)

> Enfoque acordado con el usuario: **no copiamos herramientas de otros ni las probamos para pegarlas al bot.**
> Las desarmamos para entender **qué datos usan, qué lógica siguen y qué pieza, si la hay, contiene información
> real**, aunque sea un 0,5 %. Esa pieza se valida fuera de muestra y solo entonces se integra al modelo propio.

## 1. Lo que hay que saber antes de buscar ventajas

### 1.1 Por qué existe una ventaja (y por qué casi siempre es pequeña)

Una regularidad de precios solo puede durar si alguien la **causa** y nadie la elimina del todo. Las causas
documentadas son pocas:

| Causa | Ejemplo | Plazo en que actúa | ¿La usa nuestro bot? |
|---|---|---|---|
| **Órdenes grandes repartidas en pedazos** (flujo con memoria) | Un fondo compra 500 BTC en cientos de órdenes pequeñas: la presión dura más que una vela | Segundos a minutos | **Sí: es la pieza principal (sección 2)** |
| **Pago por dar liquidez** | Tras un movimiento brusco, quien absorbe la presión cobra una reversión pequeña | Segundos a horas | Indirectamente |
| **Flujos forzados** | Liquidaciones, financiación del perpetuo, fixings de divisas, rebalanceos | Minutos a horas | No (Estudio 3: sin mejora a 15 min) |
| **Sesgos de comportamiento** | Reacción lenta a noticias y luego exceso (momentum de meses, reversión de años) | Días a meses | No (plazo distinto) |
| **Diferencias de velocidad entre mercados** | BTC se mueve segundos antes que algunas altcoins | Segundos a 1–2 min | Candidata (Estudio 12, ETH) |

Si un patrón no tiene una causa así, lo más probable es que sea **ruido que se vio en el pasado**.

### 1.2 Por qué las estrategias dejan de funcionar

1. **Competencia:** cuando una ventaja se conoce, más gente la explota hasta agotarla. McLean y Pontiff
   (Journal of Finance, 2016) midieron 97 patrones académicos:
   - rinden un 26 % menos fuera de la muestra original;
   - rinden un **58 % menos después de publicarse**.

   La hipótesis de mercados adaptativos de Lo dice lo mismo: la eficiencia cambia con los participantes.
2. **Cambio de régimen:** el proyecto lo vio en carne propia. Las ventajas de ~55 % a 15 min hasta 2025
   desaparecieron en el último año (Estudios 2 y 4).
3. **Costos:** una ventaja de 0,5 puntos en dirección desaparece si el contrato exige 54,05 % o si el
   spread se come el movimiento.
4. **Sobreajuste:** cuantas más variantes se prueban con los mismos datos, más probable es que una «gane»
   por suerte. Bailey y López de Prado lo formalizan con la razón de Sharpe deflactada y la probabilidad de
   sobreajuste del backtest. Por eso este proyecto congela las reglas antes y confirma con datos nuevos.

### 1.3 Los temas que pediste, con lo que dice la evidencia

| Tema | Qué es | Qué dice la evidencia | Plazo útil | Uso propuesto |
|---|---|---|---|---|
| Comportamiento y psicología del mercado | Reacciones exageradas o lentas, efecto manada | Momentum de 1–12 meses y reversión de largo plazo (Moskowitz, Ooi y Pedersen); los finfluencers con peores consejos tienen más seguidores | Días a meses | No a 1 min; sí para entender por qué fallan las reglas contrarias (Estudio 9) |
| Análisis técnico | Patrones de velas, medias, RSI, zonas | Sin ventaja neta tras costos en divisas y oro (H4 de la Fase 1B; Estudios 8–11) | — | Solo como variables del modelo, nunca como reglas sueltas |
| Gestión de riesgo | Tamaño de la apuesta, límites de pérdida | El criterio de Kelly maximiza el crecimiento, pero con errores de estimación lleva a apostar de más; se usa una fracción (¼–½) | — | **Sí: propuesta P5** |
| Flujo de órdenes (*order flow*) | Quién compra y quién vende agresivamente | Explica el movimiento del mismo instante; predice segundos (Cont et al.; Kolm et al.) | Segundos | **Sí: es lo que el bot ya explota (sección 2)** |
| Liquidez | Cuánto se puede operar sin mover el precio | Con poca liquidez hay más reversión y más ruido; en cripto, la reversión diaria se concentra en monedas ilíquidas | Minutos a días | Variable de régimen (propuesta P3) |
| Financiación (*funding*) | Pago cada 8 h entre largos y cortos del perpetuo | Mide el desequilibrio del apalancamiento; útil en horas o días, demasiado lenta para 1 min | Horas a días | No a 1 min (Estudio 3: sin mejora) |
| Interés abierto | Contratos abiertos en futuros | Identifica cuándo se acumula apalancamiento, no cuándo estalla | Horas a días | Variable de régimen, baja prioridad |
| Liquidaciones | Cierres forzados por falta de margen | Las cascadas son reales, pero los avisos no anticipan cada caída. Binance ya no publica el historial evento a evento | Minutos | No hay datos históricos gratuitos completos |

**Material gratuito recomendado para aprender** (en orden):
1. **Babypips, School of Pipsology:** curso gratuito de 11 niveles, desde cero, sobre divisas y lo básico.
2. **CME Group Institute:** más de 60 cursos gratuitos y un simulador; futuros, gestión de riesgo y
   contratos.
3. **Coursera, *Market Microstructure* (Marco Pagano, Universidad de Nápoles):** cómo se forman los
   precios y qué es el flujo de órdenes. También está en Federica Web Learning; en Coursera, revisar si
   permite verlo gratis.
4. **Lecturas clave, gratuitas:**
   - Lo, *The Adaptive Markets Hypothesis* (MIT);
   - McLean y Pontiff, sobre el deterioro después de publicar;
   - Bailey y López de Prado, *The Deflated Sharpe Ratio* (SSRN).

## 2. Disección de nuestro propio modelo: de dónde sale su ventaja

Análisis exploratorio (`scripts/analisis_importancia_btc.py` → `results/analisis/importancia_btc.json`):
- GBM de BTC a 1 min entrenado con 2024 y medido fuera de muestra en 2025-01 → 2025-08 (338 467 decisiones);
- se mide cuánto empeora la predicción al barajar cada grupo de datos.

| Grupo de datos | Empeora el log-loss al quitarlo | Lectura |
|---|---|---|
| **Dónde cerró la última vela dentro de su rango (`clpos`)** | **+0,0029** | La pieza principal |
| Nivel de volatilidad | +0,0015 | Modula la pieza principal |
| Medias, RSI, Bollinger | +0,0005 | Poco |
| Último minuto (`r0`) | +0,0003 | Poco |
| Tendencia de 5–240 min | +0,0002 | Poco |
| Minutos 2 a 5 | +0,0002 | Poco |
| Hora y día | +0,00005 | Casi nada |
| Tamaño de la última vela; volumen y spread; calendario | ≈ 0 | Nada |

**Qué hace exactamente esa pieza:**

| Cierre de la última vela | La siguiente sube |
|---|---|
| En el 10 % más bajo de su rango | 47,3 % (baja el 52,7 %) |
| En la mitad | ≈ 50 % |
| En el 10 % más alto | **52,8 %** |

Es **continuación** de la presión de los últimos segundos. En las velas que cierran en un extremo, la
continuación acierta:
- **55,4 %** con volatilidad baja (cuartil inferior);
- 52,7 % en el segundo cuartil;
- 50,9 % en el tercero;
- 50,3 % con volatilidad alta.

**Por qué existiría:** es el flujo de órdenes con memoria (Lillo y Farmer, citado en el PDF que trajo el
usuario). Quien empuja el precio al final de un minuto suele seguir empujando al comienzo del siguiente,
porque reparte una orden grande. Con volatilidad baja, esa presión destaca más sobre el ruido.

**Por qué se apaga con el retraso de entrada:** la continuación ocurre en los **primeros segundos** del
minuto siguiente. Por eso el Estudio 5 midió 58,1 % a +2 s, 57,0 % a +5 s, 56,1 % a +10 s y 55,4 % a +20 s.

**Riesgo de que desaparezca:** es el tipo de ventaja que los algoritmos rápidos compiten por eliminar.
Hay que vigilarla con el monitor de deterioro y con datos nuevos.

## 3. Disección de las herramientas de otros: qué pieza tenía algo

| Herramienta | Datos que usa | Lógica | ¿Pieza con información? | Medido | Por qué |
|---|---|---|---|---|---|
| Grupos de señales «90 %» | — | Repeticiones tras perder (gale) | **No** | Al azar da 87–94 % | Contabilidad, no predicción |
| PDF: zonas (Osler) | Precio, números redondos | Órdenes agrupadas en niveles | Mínima | En BTC, acierto global 52,9 % → 53,1 % con zonas, sin mejora significativa (Estudio 6) | El efecto de Osler era sobre rebotes en divisas de 1996–98 |
| PDF: flujo de órdenes | Compras y ventas agresoras | Presión de compra/venta | **Sí, pero a 1 min** | Sin mejora a 15 min (Estudio 3); **es la pieza principal de nuestro modelo a 1 min** (sección 2) | La información del flujo se agota en segundos o minutos |
| Kronos (IA) | OHLCV de 512 velas | Modelo de lenguaje de velas | **No** a 1 min | 50,03 % (Estudio 7) | Aprende a imitar velas realistas, no la presión de los últimos segundos; su correlación publicada en cripto es 0,03–0,04 |
| «Momentos parecidos» | 12 rendimientos pasados | Promedio de lo que pasó después | No nueva | 50,4 %; el GBM ya lo contiene | Usa los mismos datos que el modelo |
| Kalman | Precio suavizado | Tendencia y pendiente | No a 1 min | 50,4 % | Suaviza justo la información de la última vela |
| Otro activo (ETH) | Rendimiento de ETH 1 y 5 min | Adelanto entre activos | **Posible** | 52,0 % sola; mejora puntual no significativa | Diferencias de velocidad entre mercados. **Estudio 12** la confirma con datos nuevos |
| Golden BIAS (oro) | SMA15/200, sesiones | Seguir la tendencia en retroceso | No | Binaria 5 min 49,1 %: leve **reversión** | A 5 min el oro revierte un poco tras una vela a favor; la continuación es más corta |
| RSI 1D/W + 4H | RSI diario y semanal | Vender lo sobrecomprado | No, **al revés** | 46–49 %; al revés 51–54 % | La sobrecompra suele seguir (momentum); pocos episodios |
| Oro + DXY | Correlación de 20 velas | Confirmación cruzada | No hacia adelante | Correlación −0,40 real; acierto 48–50 % | La relación es simultánea: no dice qué viene después |
| Primera vela (ORB + FVG) | Rango de apertura de Nueva York | Ruptura con hueco y retesteo | Mínima, bruta | TP 23–28 %, R neto negativo; ORB simple ≈ 0 tras costos | Hay un pequeño momentum intradía documentado que los costos se comen |

**Patrón general:**
- La información que se puede aprovechar está en la **presión de muy corto plazo** (segundos a 1 minuto),
  en **otros activos que se mueven antes** y en el **régimen de volatilidad**.
- Casi todo lo demás que circula en redes, como tendencias de varias velas, zonas, RSI o correlaciones
  simultáneas, no añade información a ese plazo.

## 4. Mejoras propuestas, cada una con su base y su validación

Todas siguen el mismo camino:
1. pre-registro;
2. fase de desarrollo con datos antiguos (walk-forward);
3. confirmación con datos que nadie ha visto (posteriores al 2026-10-26);
4. solo entonces, demo.

| ID | Mejora | En qué dato o lógica se basa | Validación | Estado |
|---|---|---|---|---|
| **P1** | **Microestructura dentro de la vela con velas de 1 s:** rendimiento de los últimos 5, 10 y 20 s del minuto, compras agresoras de los últimos 10 s y número de operaciones | La pieza principal es la presión del final de la vela (sección 2). Hoy el modelo la ve solo a través de `clpos`; con 1 s se mide directamente | Estudio nuevo: walk-forward en 2022–2025 con velas de 1 s de Binance (gratuitas), luego datos nuevos. Criterio: mejora de log-loss frente al GBM actual | **Propuesta: la más prometedora** |
| **P2** | ETH como dato para BTC | Adelanto entre activos (sección 1.1) | **Estudio 12**, pre-registrado; se evalúa tras el 2027-01-18 | En curso (esperando datos) |
| **P3** | Selector multimoneda | Más candidatas; la misma microestructura en otras monedas | **Estudio 13**, pre-registrado | Fase de desarrollo en ejecución |
| **P4** | Velocidad de entrada | La ventaja cae de 58,1 % a +2 s a 55,4 % a +20 s | Medir en demo la latencia real del clic y diseñar la alerta (sonido, orden lista) para bajar de 10 s | Propuesta práctica, sin riesgo estadístico |
| **P5** | Tamaño de apuesta con Kelly fraccional | Con el acierto de H5a (56,1 %) y pago 85 %, Kelly completo = 4,5 % del capital; con el límite inferior (54,5 %), 0,9 %. Con error de estimación se recomienda ¼–½ | Simulación con el libro de H5a: rachas, caída máxima y probabilidad de ruina con 0,25 %, 0,5 % y 1 % por operación | Propuesta: **apostar ≤ 0,5 % por operación en demo** y parar el día tras 10 pérdidas netas |
| **P6** | Régimen de volatilidad visible en la alerta | La continuación es más fuerte con volatilidad baja (55,4 % frente a 50,3 %) | Ya lo usa el GBM. Como filtro explícito debe pre-registrarse y confirmarse con datos nuevos: es una lectura *post hoc* | Propuesta, prioridad media |
| **P7** | Variables de régimen de cripto: interés abierto y ratio largo/corto cada 5 min | Apalancamiento acumulado → más volatilidad | Estudio nuevo; esperable que no mejore la dirección a 1 min | Baja prioridad |

**Lo que no se propone:** martingala; reglas sueltas de análisis técnico; indicadores de pago; cualquier
cambio en las señales sin confirmación con datos nuevos.

## Fuentes

- McLean y Pontiff (2016): https://Www.Gwern.net/doc/economics/2016-mclean.pdf ;
  https://ivey.uwo.ca/media/3775549/pontiff.pdf
- Lo, mercados adaptativos: https://dspace.mit.edu/bitstream/1721.1/75362/1/Lo_Adaptive%20Markets.pdf
- Bailey y López de Prado: https://papers.ssrn.com/abstract=2460551 ; https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf
- Perpetuos y financiación: He, Manela, Ross y von Wachter, https://arxiv.org/pdf/2212.06888 ;
  https://arxiv.org/pdf/2506.08573
- Liquidaciones: https://arxiv.org/pdf/2607.27070 ; https://cryptoslate.com/?p=551122
- Reversión y momentum en cripto: https://ideas.repec.org:443/a/eee/ecofin/v62y2022ics1062940822000833.html ;
  https://earsiv.medeniyet.edu.tr/items/23a96c9f-3952-4bdf-aec5-abafb3aaab70 ; https://arxiv.org/pdf/2009.04200 ;
  https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/
- Adelanto entre criptomonedas: https://www.businessperspectives.org/index.php/journals/investment-management-and-financial-innovations/issue-421/a-tick-by-tick-level-measurement-of-the-lead-lag-duration-between-cryptocurrencies-the-case-of-bitcoin-versus-cardano ;
  https://ideas.repec.org:443/a/eee/riibaf/v50y2019icp306-321.html ; https://arxiv.org/pdf/2506.08718
- Fin de semana en cripto: https://ideas.repec.org/a/eee/finlet/v64y2024ics1544612324004598.html
- Kelly: https://en.wikipedia.org/wiki/Kelly_criterion ; https://www.arxiv.org/pdf/2503.17927
- Cursos: https://www.cmegroup.com/education ; https://forums.babypips.com/t/school-of-pipsology/1228940/10 ;
  https://www.coursera.org/learn/market-microstructure ; https://lms.federica.eu/course/view.php?id=722
