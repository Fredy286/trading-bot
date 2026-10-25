# TradingView: qué es, cómo usarlo con este proyecto y qué trampas evitar (2026-10-25)

> Documento vivo. TradingView es la herramienta que más mencionan los traders en redes. Aquí se explica para
> qué sirve **a este proyecto**: dónde ayuda, dónde no, y cómo convertir lo que se ve allí en pruebas serias.

## 1. Qué es

TradingView (https://es.tradingview.com/) es una plataforma web y de móvil para ver gráficos de casi
cualquier mercado (divisas, oro, cripto, índices, acciones). Ofrece:

| Función | Para qué la usan los traders | ¿Sirve al proyecto? |
|---|---|---|
| Gráficos con varias temporalidades | Ver la estructura (1 min, 5 min, 1 h, diario) | **Sí**, para mirar lo que dice el bot y entenderlo |
| Indicadores de la comunidad (miles de *scripts*) | Medias, RSI, FVG, «Smart Money», etc. | **Sí, como fuente de ideas**: los de código abierto se pueden traducir y probar aquí |
| Pine Script, su lenguaje | Programar indicadores y estrategias | **Sí**: podemos leer los scripts y traducirlos a Python |
| *Strategy Tester* (backtest interno) | «Probar» una estrategia | **Con cuidado**: tiene trampas (sección 3) |
| Alertas y *webhooks* | Avisar o mandar órdenes a otro programa | Posible en el futuro (sección 4) |
| *Paper trading* (cuenta de práctica) | Practicar sin dinero | **Sí**: útil para practicar la ejecución manual, como la demo del Estudio 5 |
| Operar con un bróker conectado | Ejecutar órdenes desde el gráfico | No por ahora: el proyecto no opera dinero real |

## 2. Cómo lo vamos a usar

1. **Como cantera de ideas, no como juez.** Cuando veas un indicador interesante, mira si dice «Open-source
   script» (código abierto). Si lo es, copia el enlace o el código: se traduce a Python y se prueba con el
   mismo método de siempre:
   - reglas congeladas antes de mirar;
   - años de datos;
   - costos;
   - confirmación con datos nuevos.

   Así se probaron el «Golden BIAS 200» (Estudio 8) y la regla de la primera vela (Estudio 11).
2. **Para mirar el mercado mientras el bot da señales.** Para BTC a 1 minuto, usa el gráfico
   `BINANCE:BTCUSDT` en 1 minuto. Es el mismo precio que usa el bot.
3. **Para practicar la entrada manual en *paper trading*.** El Estudio 5 aprobó solo con entrada en
   ≤ 10 s. Practicar en TradingView o en la demo del intermediario mide cuánto tardas de verdad en hacer
   clic.
4. **No como fuente de datos del bot.** Los términos de TradingView limitan sus datos a **ver en pantalla**,
   y prohíben usarlos en procesos automáticos o descargarlos con herramientas no oficiales. No tiene una
   API pública para bajar históricos. El bot usa sus propias fuentes (Binance, HistData), que sí lo
   permiten.

## 3. Trampas del backtest de TradingView (por qué sus «resultados» engañan)

| Trampa | Qué pasa | Cómo lo evita el proyecto |
|---|---|---|
| **Repintado** (*repainting*) | Un indicador que pide datos de una temporalidad mayor (`request.security`) puede usar en el pasado la vela grande **sin cerrar**. En el histórico parece perfecto y en vivo cambia | Solo usamos velas ya cerradas (p. ej., Estudios 8 y 9: «última vela cerrada») |
| **`lookahead_on` sin desfase** | El script ve el cierre del día antes de que ocurra (fuga de futuro). La propia documentación de Pine lo advierte | Pruebas de causalidad en cada estudio: cambiar el futuro no cambia el pasado |
| **Costos en cero por defecto** | El *Strategy Tester* empieza sin comisión ni deslizamiento | Siempre cobramos spread y comisión |
| **Llenado optimista** | Si TP y SL caen en la misma vela, el simulador puede suponer lo mejor | Cuenta el SL (conservador) |
| **Optimizar parámetros con el mismo histórico** | Mover las entradas hasta que la curva sale bonita es sobreajuste | Parámetros fijados antes, fase B y datos nuevos |
| **Historia corta** | Según el plan, el backtest ve pocas velas de 1 minuto | Usamos años de datos minuto a minuto |
| **Scripts «solo por invitación»** | Código cerrado, sin forma de verificar; suelen venderse por Telegram | Se reconstruye la regla publicada y se prueba (Golden BIAS: pierde) |

**Regla práctica:** una captura del *Strategy Tester* con «winrate 80 %» no es evidencia. Hay que preguntar
cuántas operaciones son, con qué costos, si repinta y si se probó en un periodo que no se usó para
ajustarla.

## 4. Lo que se podría construir más adelante (solo si el usuario lo pide)

- **Un indicador propio en Pine Script, de código abierto**, que marque en el gráfico de BTC las horas y los
  días donde el Estudio 5 encontró ventaja, o que dibuje las señales del bot a partir de un archivo. Solo
  sería una ayuda visual: el modelo GBM no se puede ejecutar dentro de TradingView.
- **Alertas de TradingView → bot** (*webhook*): TradingView puede enviar un mensaje JSON a una dirección
  web cuando se cumple una condición. El proyecto no lo necesita hoy, porque el bot calcula sus propias
  señales, y exige un servidor accesible desde internet.

## 5. Lo aprendido de las capturas de redes (2026-10-25)

- Muchos comentaristas operan con «Smart Money Concept»: barridos de liquidez, CHoCH, FVG, «descuentos y
  desplazamientos». La versión más concreta (regla de la primera vela con FVG y envolvente, 3:1) se probó
  en el **Estudio 11** y pierde en Nasdaq 100, S&P 500 y oro.
- Las capturas de **una** operación ganadora (p. ej., «XAUUSD buy 10, +9 266 USD») no dicen nada sin el
  historial completo, incluidas las pérdidas. Cerrar el 98 % con ganancia y «dejar correr» el resto
  tampoco cambia la ganancia esperada.
- Respuestas como «descuentos y desplazamientos» ante «¿cómo ves la dirección?» no son reglas
  comprobables. Si no se puede escribir como regla exacta, no se puede probar ni automatizar.

## Fuentes

- Términos de TradingView (datos solo para mostrar en pantalla): https://in.tradingview.com/policies ;
  documentación del API para brókers (no para descargar datos): https://tw.tradingview.com/broker-api-docs/data/history
- Repintado y temporalidades mayores, FAQ oficial de Pine Script:
  https://www.tradingview.com/pine-script-docs/faq/other-data-and-timeframes/ ;
  publicación de referencia: https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/
- Webhooks de alertas (documentación de terceros): https://docs.traderspost.io/docs/tradingview ;
  https://help.signalstack.com/kb/signal-source-integrations/tradingview-alerts-f07455cf99ed63bd
- ORB: Zarattini y Aziz, *Can Day Trading Really Be Profitable?*: https://papers.ssrn.com/abstract=4416622 ;
  réplica neta de costos: https://www.mql5.com/en/blogs/post/776235
- FVG con control placebo (indicador público): https://fr.tradingview.com/scripts/backtest/ ;
  tasa de relleno de FVG (blog de bróker): https://fxnx.com/en/blog/fair-value-gap-fill-rate-measured-across-thousands-gaps
