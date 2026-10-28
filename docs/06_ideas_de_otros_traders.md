# Ideas de otros traders: qué probamos, qué aprendimos y cómo detectar estafas

> Documento vivo (inicio: 2026-10-25). Reúne las herramientas, consejos y errores que el usuario encuentra en
> redes sociales, videos y vendedores de indicadores. Cada idea se trata como una **pieza que podría mejorar
> nuestro modelo**, nunca como un servicio para contratar. Una idea entra al bot solo si pasa una prueba
> pre-registrada con datos antiguos y luego con datos nuevos (docs/01).

## 1. Lo que dicen los estudios serios sobre los traders de redes

| Estudio | Qué midió | Resultado |
|---|---|---|
| Kakhbod, Kazempour, Livdan y Schürhoff, *Finfluencers* (SFI 23-30; AEA 2025) | Recomendaciones de «finfluencers» en una plataforma de acciones | 28 % con habilidad, 16 % sin habilidad, **56 % «antihabilidad»** (sus consejos rinden peor que el azar). Los de antihabilidad tienen **más seguidores**. Hacer lo contrario de lo que recomiendan daba +1,2 % al mes |
| Chague, De-Losso y Giovannetti, *Day Trading for a Living?* (Brasil, 2013–2015) | Todos los que hicieron day trading en futuros de índice ≥ 300 días | **97 % perdió dinero**; solo 0,4 % ganó más que un cajero de banco; no hay evidencia de que aprendan con la práctica |
| Barber, Lee, Liu y Odean (Taiwán, *Review of Financial Studies* 2011) | Más de 360 000 day traders | La mayoría pierde después de costos; según una reseña, menos del 1 % gana de forma consistente |

**Lección:** la popularidad en redes no mide la calidad. Lo que más se comparte suele ser lo más
entretenido u optimista, no lo que funciona. Por eso aquí nada se acepta sin prueba.

## 2. Errores que se repiten (y cómo los evita el bot)

| Error visto en redes | Ejemplo | Por qué engaña | Cómo lo evita el proyecto |
|---|---|---|---|
| **Sumar «confirmaciones» que dicen lo mismo** | Roger: compras agresivas en verde + CVD en verde + velas verdes + rebote en muro de compras… y el precio cayó | Las tres primeras miden lo mismo: el flujo de los últimos minutos. Tres copias de una señal no son tres señales. Un vendedor pasivo grande puede absorber las compras agresivas, y un muro del libro puede retirarse antes de tocarse (*spoofing*, documentado en cripto) | El modelo pondera cada dato según cuánto predice de verdad. El flujo agresor se probó (Estudio 3) y **no mejoró** la predicción a 15 min. En la literatura solo anticipa segundos |
| **Explicar después lo que no se predijo antes** | El autor respondió: «el precio bajó para buscar stops y liquidez» | Siempre se puede inventar una historia después. Si no se dice **antes**, cuándo ocurrirá, no sirve para operar | Cada regla se escribe y se congela antes de mirar los datos |
| **Reglas contrarias a la tendencia por «sobrecompra»** | Danny: RSI sobrecomprado en diario y semanal → solo ventas | Lo sobrecomprado tiende a seguir subiendo durante un tiempo (momentum) | **Estudio 9:** la regla acierta 46–49 % en BTC, ETH, oro y EUR/USD; pierde en los cuatro |
| **Contar el acierto con repeticiones** | «M2/M3», «gale» | Con 2 repeticiones, una moneda «acierta» 87 % y aun así pierde | docs/05, sección 2: medimos una sola entrada |
| **Winrate sin costos ni tamaño de pérdidas** | Tabla de «Winrate» del Golden BIAS | Un TP pequeño con SL grande da un winrate alto y pierde | Exigimos ganancia esperada neta > 0, no solo acierto |
| **«Habrías evitado tus perdedoras»** | Video oro–DXY: mirar la correlación antes de entrar | Cualquier filtro que opere menos «evita» perdedoras. La pregunta correcta es si evita **más** perdedoras que ganadoras | **Estudio 10:** el filtro quitó el 89 % de las perdedoras y el 90 % de las ganadoras: no mejora nada |
| **Confundir relación simultánea con anticipación** | «El oro y el dólar van al revés» | Es cierto en el mismo momento (correlación −0,40), pero eso no dice qué hará el oro **después** | Solo cuenta lo que se sabe antes de entrar |
| **Captura de una sola operación ganadora** | «XAUUSD buy 10, +9 266 USD», «cobré 9,8 lotes» | Una ganancia no dice nada sin todas las pérdidas. Cerrar parciales no cambia la ganancia esperada | Solo cuentan los historiales completos |
| **Respuestas imposibles de comprobar** | «¿Cómo ves la dirección?» → «descuentos y desplazamientos» | Si no se puede escribir como regla exacta, no se puede probar | Cada regla se escribe completa antes de probarla |
| **Un 50 % que parece «funcionar»** | «El precio rebota en la zona dorada» | Desde la mitad del impulso, cualquier punto da 50 % de llegar arriba antes que abajo: es geometría, no Fibonacci | Se compara siempre con la referencia del azar y con zonas vecinas (Estudio 17) |
| **Mostrar el mejor mes** | Capturas de canales | De 1 000 canales al azar, 124 muestran ≥ 90 % en un mes | Muestra fija y datos nuevos |
| **Comprar indicadores** | Isaac Martínez: «no conozco un solo trader que haya hecho mucho dinero comprando indicadores» | — | Coincide con lo medido: el Golden BIAS reconstruido pierde (Estudio 8) |

## 3. Herramientas de otros probadas hasta hoy

| Fuente | Herramienta | Estudio | Resultado |
|---|---|---|---|
| PDF «El secreto del trading profesional» | Zonas: números redondos, máx./mín. del día anterior, toques | 6 | SIN SEÑAL: no mejora el modelo (BTC, EUR/USD) |
| PDF | Flujo de órdenes y desequilibrio | 3 | SIN SEÑAL a 15 min |
| PDF y grupos de señales | Reentradas M2/M3 (martingala) | docs/02 §6.1, docs/05 §2 | Descartada: no cambia la ganancia esperada |
| Video de «Kronos AI» | Kronos, análogos, Kalman, otro activo (ETH) | 7 | SIN SEÑAL: Kronos solo acierta 50,03 %; análogos y Kalman no aportan. ETH, prometedora (57,0 % frente a 55,8 %) pero no significativa: hipótesis para datos nuevos |
| TradingView «Golden BIAS 200» | SMA15/SMA200, retroceso, sesiones, flechas multitemporales | 8 | SIN SEÑAL: pierde en las 4 versiones |
| Comentario de Facebook (Danny Roggers) | RSI diario + semanal, estructura 4H, entrada 15M | 9 | SIN SEÑAL: acierta < 50 % |
| Video de redes: oro + índice del dólar | Correlación negativa (< 0) + oro en zona de demanda + DXY respetando su zona de oferta | 10 | SIN SEÑAL: 48,2 % a 15 min y 49,9 % a 60 min. El filtro evita el 89 % de las perdedoras… y el 90 % de las ganadoras |
| Video «regla de la primera vela» + capturas de «Smart Money Concept» | Rango de 9:30–9:35 NY, ruptura con FVG, retesteo con envolvente, 3:1 | 11 | SIN SEÑAL: Nasdaq −0,18 R, S&P −0,09 R, oro −0,34 R por operación; TP solo 23–28 % |
| Video «Así se usa Fibonacci» | Retroceso al 50–61,8 % («zona dorada») y extensiones | 17 A | SIN SEÑAL: en BTC, oro y EUR/USD la zona dorada se comporta exactamente como el azar (50,0 / 50,4 / 49,8 % frente a 50 % de referencia) y no es mejor que sus vecinas |
| Video «10 conceptos ICT» | FVG, toma de liquidez, quiebre de estructura, premium/descuento, máximos y mínimos iguales | 17 B | SIN SEÑAL: no mejora el modelo de BTC (log-loss sin cambio; EV baja de +0,048 a +0,038). Un preprint de 2026 tampoco encuentra ventaja en ICT y muestra que el barrido de liquidez predice **continuación** |
| Comentario de Facebook (Roger Va Cr) | Mapa de calor del libro, CVD, muros | — | No se puede probar con datos históricos gratuitos del libro completo. Lo más cercano (flujo agresor) ya falló en el Estudio 3. Candidata futura: profundidad agregada del libro de futuros de Binance |
| Comunidades brasileñas de binarias (blogs, PDF del Catalogador OB, bots de GitHub) | 17 reglas de «cuadrantes»: MHI 1/2/3 mayoría y minoría, Milhão, Torres Gêmeas, Três Vizinhos, Padrão 23, Melhor de 3, 3x1, C3, Moonwalker, «3 velas» | 22 | SIN SEÑAL: 6,6 millones de operaciones en 5 mercados, mediana **50,0 %**; igual que el placebo sin alinear al reloj. Con 2 gales «aciertan» 85–89 % de los ciclos y pierden 13–51 centavos por ciclo |
| Bots de Pocket Option / guías de Quotex (GitHub, India) | SMA3/SMA8 + 3 cierres; EMA20/EMA50 + RSI14; EMA5/EMA20 + RSI 50 | 22 | SIN SEÑAL: 47,6–50,0 % (por debajo del azar) |
| «Listas de señales» (catalogadores) | Horarios HH:MM que acertaron ≥ 80 % en los últimos 10 días | 22 | SIN SEÑAL: al día siguiente aciertan 50,0–51,5 %: es elegir el pasado, no predecir |
| Turn Over (IQ Option, 15 min) | Vela de :45 → contra en la de :00 | 22 | SIN SEÑAL: 51,1–52,4 % |
| smart-lab.ru (Rusia) | Bollinger (20, 2) con reversión, 3 min, 21–24 UTC | 22, 25, 27 | **Desarmada y pasa el desarrollo** (Estudio 27: 57,2 % con precio medio y clic a +10 s en 24 pares). Antes, en el Estudio 22: 53,3–55,6 % (2025–26) y 54,7–57,6 % (2021–25) en divisas. No pasa Holm, cae a 51,5–52,8 % si el empate pierde y se debilita con los años. Candidata P10 (docs/08) |
| 70 canales públicos de Telegram (pt, es, en, ru, id, hi) | Señales publicadas a diario (55 887 extraídas; 33 186 no OTC) | 23 | SIN SEÑAL: con ~20 000 señales publicadas ANTES de la entrada, la primera entrada acierta 49–51 % (como el azar). Lo que anuncian (83–99 %) es con gale; Tigers y VIPBinary publican casi todo después de la hora |

**Lo que sí funcionó:** solo el modelo propio de BTC a 1 minuto:
- Estudio 5 (H5a): 56,11 % con datos nuevos y entrada a +10 s;
- Estudio 20: repetido mes a mes en 2025-09 → 2026-10 con el aviso del segundo 50, 57,60 % en 22 129
  operaciones, y **62,5 % cuando el modelo está seguro (p ≥ 0,60)**.

Ninguna herramienta de terceros lo ha mejorado todavía.

**Cómo «aciertan» los canales (Estudios 22 y 23 y el informe local `data/raw/senales_terceros/INFORME.md`):**
1. cuentan como acierto lo ganado tras 1 o 2 gales: al azar eso ya da 87,5 %;
2. ponen los ✅ después o editan las listas;
3. reciclan marcadores, a veces con cifras imposibles;
4. esconden las pérdidas;
5. operan casi todo en OTC (precio propio del bróker, imposible de verificar).

El negocio está en el enlace de registro y el «grupo VIP», no en la señal.

## 4. Señales de alerta de estafa (lista de control)

Si una oferta cumple **dos o más**, trátala como sospechosa:

1. Se paga por Telegram o por mensaje privado, sin factura ni empresa identificable.
2. Código cerrado o «solo invitación», sin forma de revisar las reglas.
3. «Alta precisión», «90 %», «sin pérdidas», sin un registro verificable de señales publicadas **antes**
   de cada operación.
4. Incluye «canal VIP» o «grupo de señales» (el negocio es vender la suscripción, no operar).
5. Cuenta los aciertos con «gale», «M2/M3» o «recuperación».
6. Muestra capturas de ganancias, nunca un historial completo con pérdidas.
7. No menciona costos (spread, comisión, pago de la plataforma, empates).
8. Presiona con urgencia («últimos cupos», «precio sube mañana»).
9. Explica las pérdidas después con historias («cazaron stops») en lugar de reglas fijadas antes.

**TradingView:** guía de uso y trampas de su backtest en `docs/07_tradingview.md`.

## 5. Cómo traer una idea nueva para probarla

Lo más útil es copiar la regla **exacta**: qué indicador, qué valores, qué marco de tiempo, cuándo se entra,
cuándo se sale y en qué instrumento. Con eso:
1. la regla se escribe y se congela en docs/01;
2. se prueba con años de datos antiguos;
3. si pasa, se confirma con datos nuevos;
4. solo entonces se suma al bot.

Si la regla es vaga, la reconstrucción se declara como interpretación nuestra (así se hizo con el Golden
BIAS).

## Fuentes

- Finfluencers: https://www.sfi.ch/en/publications/n-23-30-finfluencers ;
  https://www.aeaweb.org/conference/2025/program/paper/i3ry3n4t ; resumen:
  https://quantpedia.com/what-can-we-extract-from-the-financial-influencers-advice/
- Day Trading for a Living?: https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full ;
  https://www.cxoadvisory.com/investing-expertise/day-trading-a-bust/
- Taiwán: https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf ;
  reseña con la cifra de < 1 %:
  https://my.tradingview.com/chart/EURUSD/pJsnrpJF-The-Ineffectiveness-of-Day-Trading-A-Critical-Review-of-Empiric
- Spoofing en cripto: https://arxiv.org/pdf/2504.15908 ;
  https://www.elliptic.co/corpus/gen-2504/market-abuse/spoofing-and-layering-in-crypto-order-books-on-chain-and-off-chain-detection-signals.html ;
  https://bookmap.com/blog/how-price-reacts-around-fake-liquidity-bait-walls-and-phantom-size
- Oro y dólar, dependencia cambiante (datos de 5 min, 2017–2019): https://pmc.ncbi.nlm.nih.gov/articles/PMC8566682 ;
  indicador público oro vs DXY: https://jp.tradingview.com/script/FsuB2iFG-Gold-vs-DXY
- Momentum: Moskowitz, Ooi y Pedersen, *Time Series Momentum*: https://papers.ssrn.com/abstract=2089463 ;
  RSI sobrecomprado (practicante): https://sentimentrader.com/blog/overbought-on-every-time-frame
