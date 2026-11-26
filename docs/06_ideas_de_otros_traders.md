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
| Video «Le doy $1 000 a ChatGPT para que haga trading por mí» (audio por WhatsApp, 2026-10-30) | Pedir 5 estrategias «rentables» de BTC a ChatGPT, probarlas en TradingView sobre el pasado y quedarse con las 2 que ganaron (+927 % y +1 588 % en 6 meses) | 45 | SIN SEÑAL: elegir las 2 mejores de 5 no predice el semestre siguiente (6 de 10, p = 0,38); rinden +2,7 % por semestre frente a +10,0 % de comprar y mantener. En los últimos 6 meses la mejor dio +9,9 % sin apalancamiento y no llega a +927 % ni con 50×. Ni eligiendo después la mejor estrategia y el mejor apalancamiento de cada semestre desde 2021 se pasa de +687 % (con caída del 86 %) |
| Foros de trading: «operar la curva de capital» (meta-etiquetado de López de Prado) | Seguir operando solo si el sistema viene acertando (últimas 500 operaciones o 7 días ≥ equilibrio) | 48, 49 | **Pasa en desarrollo** con el modelo propio de BTC: el acierto sube ~0,6–0,9 puntos, pero la ganancia total casi no cambia. Confirmación con datos nuevos (Estudio 49, enero) |
| Video «Conecta Claude a TradingView y que haga por ti en menos de 1 minuto» (WhatsApp, 2026-11-15) | Instalar un MCP de terceros (tradesdontlie/tradingview-mcp) y abrir TradingView Desktop con el puerto de depuración 9222 para que Claude cambie el gráfico, ponga indicadores, dibuje máximos y mínimos (de ayer, de la semana y de 52 semanas) y cree alertas. Al final: «uso la IA para crear estrategias rentables y ponerlas en mis cuentas», con capturas de pagos (axi SELECT, Darwinex, certificados de fondeo) y un formulario de nombre y correo | — | **Sin estudio: no es una regla, es un control remoto del gráfico.** No da datos que el bot no tenga (Binance de 1 s, libro de OKX). Los máximos y mínimos de ayer ya se probaron como zonas (Estudio 6, sin señal). Su propio README advierte que puede violar los términos de TradingView (riesgo de que cierren la cuenta), que usa interfaces internas que pueden romperse y que no se debe usar para decisiones automáticas con los datos extraídos. Lo de «estrategias rentables» cumple las alertas 6 y 10 de la sección 4 y termina en un formulario; los dos pagos grandes de la captura (29 274 y 207 397 USD) llevan nombres de otras personas. Pedirle estrategias a una IA ya se probó (Estudio 45) |
| Prompt de «Quantitative Trader y NLP» (WhatsApp, 2026-11-15): redes, foros y comunidades | Sentimiento de Reddit, Telegram, Bluesky y otros; velocidad de menciones; polaridad; divergencia entre narrativa y precio | docs/11 | **SIN SEÑAL.** Ninguna fuente de texto sirve en vivo sin cuenta (Reddit llega 4–6 h tarde). 11 111 titulares de Telegram: la polaridad acierta 50,1 % y las noticias van detrás del precio. La literatura (52 hallazgos) dice lo mismo: el sentimiento predice volatilidad, no dirección |
| Mismo prompt: posicionamiento de la multitud | Ratio largo/corto de cuentas (Binance, Bybit), interés abierto, liquidaciones (Gate), «la multitud siempre pierde» | docs/11 (P7) | **SIN SEÑAL:** AUC 0,500; las liquidaciones copian el movimiento ya ocurrido. Trampa: en los «metrics» de Binance, `create_time` es el inicio del periodo (5 min de futuro si se une mal) |
| Mismo prompt: 13 creencias de las comunidades | «Desplome de las 10», subida del domingo, caída del lunes, venta asiática, hueco del CME, comprar el miedo, squeeze por financiación, números redondos | docs/11 | **Azar (49,5–51 %).** «La tendencia es tu amiga» funciona AL REVÉS a 5–15 min (continúa 47–49 %) → vetos D1 (no seguir la tendencia de 60 min) y D2 (no operar en la apertura de Nueva York), pre-registrados como **Estudio 72**: en el blitz en horas abiertas de IQ, 54,5 % → 55,9 % y +114 → +247 en desarrollo |

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

## 3b. ¿Hay gente que acierta 60 % o más de verdad? (2026-10-29)

Pregunta del usuario: «no creo que tiren al azar; debe haber algo detrás de quien acierta todos los días».
Lo que dicen los estudios con datos completos (no capturas de pantalla):

1. **Sí existen traders con habilidad, pero son rarísimos.**
   - En Taiwán (1992–2006, todos los day traders del país), **menos del 1 %** gana de forma predecible y repetida
     después de comisiones. Los 500 mejores del año anterior siguieron ganando unos 0,38 % al día; los peores
     siguieron perdiendo.
   - En Brasil, de 19 646 personas que empezaron a hacer day trading en el mini-índice (2013–2015), solo el 7,9 %
     siguió más de 300 sesiones. De esas, **17 personas (1,1 %) ganaron más que el salario mínimo** y nadie mostró
     aprendizaje.
2. **«Verificado» no quiere decir «rentable».** El sello de Myfxbook solo confirma que los datos vienen del bróker;
   muchas cuentas verificadas pierden. Un acierto alto suele esconder **pérdidas grandes y raras**: muchas ganancias
   pequeñas y, de vez en cuando, una pérdida que se lo lleva todo (martingala, rejillas, operar sin stop). Las
   propias tiendas de robots de MQL5 muestran que sus sistemas de mayor acierto tienen las caídas más profundas.
3. **Lo que se ve en redes está filtrado.** Miles de personas lo intentan y solo se muestran las rachas buenas
   (sesgo de supervivencia). Las cifras de las plataformas («79 % de nuestros Popular Investors ganaron en 2021») las
   publican ellas mismas y no cuentan a los que se fueron.
4. **En binarias, el acierto sí importa, porque el pago es fijo.** Pero ahí aparecen otras trampas, ya medidas en
   este proyecto:
   - el gale (al azar da 87,5 %);
   - el OTC (precio del propio bróker, imposible de verificar);
   - publicar después de la operación.

   En 20 000 señales publicadas por adelantado, la primera entrada acertó 49–51 % (Estudio 23).

**Qué hay «detrás» cuando alguien acierta de verdad:** una ventaja pequeña (55–60 %), en condiciones concretas
(hora, mercado, volatilidad) y medida con disciplina. Es lo mismo que encontramos aquí: BTC a 1 min ~57 % y ~60 %
con alta confianza; la reversión nocturna en divisas ~57 % y ~62 % a las 17 h de Bogotá. **No** hay evidencia de nadie
con 80–90 % sostenido sin martingala ni OTC.

**Cómo lo seguimos comprobando:** la vigilancia hacia adelante de canales (Estudio 32) guarda lo que publican antes
de la operación. Si alguien acierta de verdad, aparecerá ahí, y entonces desarmaremos qué hace.

Fuentes:
- [Barber, Lee, Liu y Odean, *The cross-section of speculator skill: Evidence from day trading* (J. Financial Markets, 2014)](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html)
  y [documento de trabajo](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf);
- [Chague, De-Losso y Giovannetti, *Day Trading for a Living?* (FGV, 2020)](https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full);
- [MQL5: los tres mayores aciertos tienen las tres mayores caídas](https://www.mql5.com/en/blogs/post/777108) y
  [por qué un acierto alto puede perder](https://www.mql5.com/en/blogs/post/778171) (blogs de vendedores);
- [Reseña de Myfxbook 2026](https://takeprofitapp.com/en/learn/myfxbook-review-2026);
- [eToro sobre sus Popular Investors (cifras propias)](https://etoro.com/news-and-analysis/copytrader/popular-investors-with-3-or-more-years-profit);
- [Darwinex: atributos invertibles (compara contra 10 000 estrategias al azar)](https://help.darwinex.com/what-are-investable-attributes).

## 3c. Copy trading, plataformas de señales y empresas de fondeo (2026-11-03)

Segunda revisión (martes). Objetivo: encontrar cuentas concretas con historial largo y verificado y desarmar su estilo.
**No se logró:** desde la nube no abren darwinex.com, mql5.com, ideas.repec.org ni thegodfunded.com; solo vi los
resúmenes del buscador, así que las cifras de abajo no están comprobadas en el original.

1. **Copiar aumenta el riesgo, no el acierto.** En un experimento publicado en *Management Science* (2020), ver el éxito
   de otros subió la toma de riesgo y poder copiarlos la subió aún más. Unos dos tercios no copiaron; quienes copiaron
   ya habían elegido antes los activos más riesgosos. Motivo: el que «va ganando» puede haber tenido suerte o haber
   corrido más riesgo, y el que copia hereda ese riesgo sin saberlo.
2. **Tras costos no queda ganancia.** Un estudio de 2018 sobre plataformas de social trading (*Quarterly Review of
   Economics and Finance*) dice que ninguna estrategia de copia da rentabilidad anormal positiva tras costos de
   transacción (modelo de cuatro factores de Carhart).
3. **La persistencia es débil en los extremos.** En asesores de futuros (CTA), algo de persistencia a 3 meses, pero se
   desvanece al mirar solo el mejor y el peor cuartil: el «número uno» de hoy no suele seguir arriba.
4. **Las listas ya vienen filtradas.** MQL5 y Darwinex solo muestran las cuentas que siguen vivas; la mayoría termina
   en silencio (se deja de operar o se cierra la cuenta), no con una pérdida visible. ZuluTrade tuvo que poner avisos a
   proveedores con 100 % de operaciones ganadoras y un tope de pérdida flotante de 700 pips (señal de martingala y de
   operar sin stop).
5. **Empresas de fondeo (datos más grandes, aunque de segunda mano):** en un conjunto de más de 100 000 cuentas de
   10 empresas, el 86 % falló el examen y solo ~7 % llegó a cobrar algo (en promedio ~4 % del tamaño de la cuenta).
   FTMO publica solo totales pagados, no qué parte de sus clientes cobra.

**Pieza útil para el bot:** ninguna regla nueva. Se confirma lo de la sección 3b: no hay evidencia pública verificable
de alguien con ≥ 60 % sostenido en plazos cortos sin martingala; los historiales «verificados» se eligen después de ver
quién sobrevivió. Para desarmar una cuenta concreta hace falta su lista completa de operaciones (CSV de Myfxbook o
Darwinex), y eso solo se puede bajar en una sesión local.

Fuentes (resúmenes del buscador):
- [Apesteguia, Oechssler y Weidenholzer, *Copy Trading*, Management Science 66(12), 2020](https://bse.eu/research/publications/copy-trading)
  y [resumen de la BSE](https://focus.bse.eu/copy-trading-risk-taking/);
- [Estudio de 2018 sobre social trading (QREF, vol. 70)](https://ideas.repec.org/a/eee/quaeco/v70y2018icp160-171.html) (no abrió);
- [Persistencia de CTA (J. Futures Markets, 2010)](https://ideas.repec.org/a/wly/jfutmk/v30y2010i8p725-752.html) (no abrió);
- [MQL5: sesgo de supervivencia en las listas de señales](https://www.mql5.com/en/blogs/post/777995) (no abrió);
- [ZuluTrade explicado (forexop)](https://forexop.com/signals/zulutrade);
- [Tasa de cobro en empresas de fondeo (tradeinformer)](https://www.tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances)
  y [The Funded Trader: 1 de cada 20 aprueba (Finance Magnates)](https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader/).

## 3d. Investigación académica reciente sobre BTC a segundos y minutos (2026-11-07)

Búsqueda pedida por el usuario («busca estrategias, investiga»). Sirvió para diseñar el Estudio 50, no para copiar
nada:

| Trabajo | Qué encontró | Qué nos sirve |
|---|---|---|
| Kim y Hansen, *The Quarter-Hour Effect* (arXiv 2607.09426, 2026). Futuros perpetuos de Binance (BTC, ETH, XRP, SOL, DOGE, ADA), 2021–2024 | Ráfagas de volumen y volatilidad en las marcas de 1, 5 y 15 min (algoritmos que operan con el reloj). El rendimiento de los primeros 10 s tras cada cuarto de hora se puede predecir fuera de muestra (acierto medio 57 %), pero vale unos 0,5 puntos básicos: menos que cualquier costo. El desequilibrio de órdenes del primer tramo anticipa movimientos de 4 a 12 h | La ventaja de nuestro modelo podría vivir en los cierres de minuto. El Estudio 50 lo mide (acierto por segundo del minuto). Nada operable a 3 min |
| Bieganowski y Ślepaczuk, *Explainable Patterns in Cryptocurrency Microstructure* (arXiv 2602.00776, 2026). Libro de órdenes y operaciones de futuros de Binance cada segundo, 2022–2025 | El desequilibrio del flujo de órdenes y el diferencial explican el rendimiento de corto plazo de forma parecida en BTC, LTC, ETC y otras | Apoya usar el desequilibrio comprador/vendedor de las velas de 1 s (`s_tib`, ya en el Estudio 50). El libro de órdenes completo no está en los archivos públicos que usamos |
| Descubrimiento de precio entre futuros de CME y contado de Binance (arXiv 2506.08718, 2025) | Los futuros de CME van ~0,05 s por delante del contado de Binance | Demasiado rápido para una operación manual |

## 3e. Bots públicos de los contratos de 5 min de Polymarket (2026-11-10)

Búsqueda pedida por el usuario («busca más estrategias»). Ninguno publica resultados verificados; se desarmó qué
explota cada uno:

| Bot (GitHub) | Qué hace | Qué medimos |
|---|---|---|
| AllAboutAI-YT/polymarket_bot_beginner; jmazzini/5m-poly-bot | Compra el lado que va ganando en los últimos segundos | En Polymarket (marzo–mayo de 2026) el favorito gana más de lo que dice su precio: +6 a +11 puntos con 15 s por delante (*post hoc*, docs/01, nota del Estudio 59). En OKX, dentro de la ventana casi no hay libro (0,97/0,03): se está midiendo |
| Novals83/5min-btc-polymarket | Entra con ~2 min por delante si BTC ya se movió 70–100 USD | Es el mismo sesgo del favorito, más temprano (+3 a +4 puntos a los 150–240 s en Polymarket) |
| dearolaf/Polymarket-BTC-5Minutes-Trading-Bot; Josh-Alot/polymarket_5min_bot | Velas y libro de Coinbase o Binance para adivinar la dirección antes de la ventana | Es lo que hace nuestro modelo. **Estudio 59:** al abrir la ventana, Polymarket ya cobraba casi toda esa información (0,555 por un lado que acierta 56,8 %) |
| AI-Degen-69/polymarket-btc-updown-bot | Kelly para el tamaño de apuesta | No cambia la ganancia esperada; ya está en docs/08 (P5) |

**Lección:** en un mercado con muchos bots, la información de los últimos segundos ya está en el precio al empezar
la ventana. La ventaja solo existe frente a quien cotiza sin mirarla, o en sesgos de comportamiento como el del
favorito, que necesitan alguien dispuesto a vender en la ventana.

## 3f. Los resultados publicados por la familia «Gavin» (GavinVIPResults, 2026-11-13)

El canal público GavinVIPResults (vigilado desde el 2026-10-28) publica cada hora la lista de sus operaciones con
«WIN», «WIN¹», «WIN²» o «LOSS». Contando **sus propias listas** del 2026-10-28 al 2026-11-13 (5 138 operaciones, todas
en activos OTC: no se pueden comprobar con un precio real):

| Resultado según el canal | Operaciones | Proporción |
|---|---|---|
| Gana en la 1.ª entrada | 2 562 | 49,9 % |
| Gana en la 2.ª (gale 1) | 1 278 | 24,9 % |
| Gana en la 3.ª (gale 2) | 621 | 12,1 % |
| Pierde las tres | 677 | 13,2 % |

Su «tasa de acierto» publicada (69–74 % en los resúmenes diarios, 86,8 % con gales) es **exactamente lo que da una
moneda al aire**: con 50 % por intento, ganar en alguno de tres intentos es 87,5 %. Ni siquiera con sus propias cifras
la primera entrada supera el azar, y con pago 85 % y martingala la ganancia esperada es negativa (docs/05). Descriptivo,
con las cifras del propio canal (puede haber operaciones repetidas entre listas); no cambia el veredicto del Estudio 32.

## 3g. Literatura del 2026-11-16: fin de semana, apertura de Asia y sesgo del favorito (solo resúmenes)

Las páginas no abren desde la nube (concretumgroup.com, karlwhelan.com, ifo.de dan «host no permitido»); todo sale de
los resúmenes del buscador, sin cifras de rentabilidad verificadas.

- **«Monday Asia Open Effect»** (Zarattini, Pagani y Barbon, *Catching Crypto Trends*, SSRN 2025, rev. oct. 2025): una
  cartera de modelos de tendencia de alta frecuencia en BTC gana más al abrir Asia el lunes; lo atribuyen a liquidez y
  posiciones nuevas que marcan movimientos de varias horas, más fuerte desde mediados de 2020. En contra: Kaiser (Finance
  Research Letters 64, 2024) dice que el «efecto lunes» de BTC no persiste después de 2015 y que la estacionalidad en
  cripto no es robusta. **Lectura:** es tendencia de horas, no de 1 min; no se convierte en estudio (sería buscar una
  franja horaria a posteriori, lo que ya falló con la «catalogación»). Nuestro efecto de fin de semana (H5b confirmada)
  es otro: se mide en datos nuevos y no depende de una hora concreta.
- **Sesgo del favorito en Kalshi** (Bürgi, Deng y Whelan, *Makers and Takers*, CESifo WP 12122 / CEPR DP20631, 2025–26;
  más de 300 000 contratos): los contratos baratos ganan menos de lo que dice su precio (sesgo favorito–longshot); los
  precios mejoran cerca del cierre; los que ponen órdenes en el libro (*makers*) ganan más que los que las toman
  (*takers*); rendimiento medio de −20 % a −22 %. Un blog sin método verificable dice que el sesgo es más fuerte en los
  contratos de 5 min de cripto. **Lectura:** apoya la lógica del Estudio 62 (comprar al favorito dentro de la ventana de
  OKX), ya pre-registrado; no se cambia nada. Y recuerda que en OKX compramos como *taker*: la parte que gana en esos
  mercados es la que deja órdenes esperando (anotado como idea 1d en docs/10, sin estudio).

## 3h. Hyperliquid: el único historial de traders verificado al 100 % (2026-11-17, solo resúmenes)

En Hyperliquid (bolsa de futuros perpetuos en su propia cadena) cada orden y cada cuenta son públicas: es el único
sitio donde el «historial verificado» no depende de una captura ni de un bróker. Las páginas y la API
(api.hyperliquid.xyz, stats-data.hyperliquid.xyz, htx.com, hyprswarm.pages.dev) **no abren desde la nube**; todo sale de
los resúmenes del buscador, sin poder comprobar cifras.

- **La mayoría pierde:** de 1 000 cuentas, 166 con ganancia (16,6 %, The Coin Republic, 2025-06); otro informe con datos
  de Hyperdash da 14 %; otro, 75 % pierde (HTX).
- **Acierto alto ≠ ganancia:** según HyprSwarm, las carteras más grandes aciertan menos del 40 % y son las que más ganan;
  una cuenta con 28 % de acierto ganó 4,48 M USD en 50 operaciones; la de «64,75 % de acierto» es de alta frecuencia (por
  su estilo, probablemente un creador de mercado que cobra el diferencial, no alguien que adivina la dirección).
- **Las listas engañan:** Protos (2025) cuenta cifras de ganancias mal leídas de las tablas de clasificación que se
  difundieron en redes; ordenar por acierto saca arriba a cuentas de poca ganancia.

**Lectura:** confirma las secciones 3b y 3c con datos que nadie puede maquillar: quien acierta ≥ 60 % de forma estable
suele ganar poco por operación o cobrar el diferencial (lo que hace el *maker*, idea 1d de docs/10), no predecir mejor.
No hay estudio: no tenemos acceso a la API desde la nube, y «seguir a las ballenas» es copiar, lo que ya se descartó.
Queda como idea 2b de baja prioridad (docs/10): solo si GitHub Actions llega a la API, medir si las posiciones de las
cuentas grandes anticipan el minuto siguiente de BTC, con pre-registro y datos hasta el 2026-10-25.

## 3i. El «efecto del cuarto de hora» en futuros cripto (2026-11-18, solo resúmenes)

- **Fuente:** Kim y Hansen (UNC), *The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability in
  Cryptocurrency Futures*, arXiv 2607.09426 (julio de 2026; https://ideas.repec.org/p/arx/papers/2607.09426.html).
  arxiv.org, alphaxiv.org y cryptoslate.com no abren desde la nube: solo resúmenes del buscador; autoría y cifras sin
  verificar en el texto.
- **Qué dice:** la actividad se dispara en los **primeros 10 s** de cada cuarto de hora (sobre todo en la hora en punto)
  y casi desaparece en el bloque siguiente; bajan las operaciones de tamaño «redondo» (bots programados). Con datos
  previos a la marca predicen la dirección de esos 10 s (AUC ~0,60), pero la mejor regla gana en promedio **0,51 pb por
  operación antes de comisiones** (según la reseña de cryptoslate).
- **Lectura para nosotros:** encaja con el Estudio 57 (más volumen en Binance en torno a las marcas de 5 min) y con la
  observación *post hoc* de que nuestro GBM acierta 1–2 puntos menos al entrar en :00/:05… Lo que se puede predecir dura
  10 s y ya pasó cuando entra un clic humano (+10 s); 0,51 pb no paga ni la comisión de Binance Futures (4–10 pb).
  **Sin estudio nuevo:** las variables de «reloj» ya fallaron (Estudio 33) y la brecha en las marcas se confirma con el
  Estudio 58 (enero de 2027). Si el 58 la confirma, la mejora natural es **no avisar en las entradas de :00/:15/:30/:45**,
  pre-registrada aparte con datos nuevos.

## 3j. Horas de financiación de los perpetuos: el «17:00 de Nueva York» de las cripto (2026-11-19, solo resúmenes)

Búsqueda del jueves (mecanismos de liquidez parecidos a la reversión nocturna de divisas). Solo resúmenes del buscador;
mdpi.com no abre desde la nube.
- «Perpetual Futures Contracts and Cryptocurrency Market Quality» (afajof.org, datos de libro 2017–2023; resumen del
  Cornell): alrededor de cada liquidación de la financiación (00:00, 08:00 y 16:00 UTC en Binance) suben el volumen
  al contado y el diferencial, en forma de U dentro del ciclo de 8 h; lo explican por más operadores informados, no
  por presión de precio que luego se devuelva.
- Un artículo de MDPI de 2026 (26 bolsas, 812 símbolos, nov-2025 → ene-2026) ve el máximo del diferencial unas 2 h
  después de esas horas. Es un resultado de diferencial, no de reversión.
- Quantpedia (Padyšák y Vojtko) ve rendimientos horarios de BTC mayores a las 22–23 UTC: es una deriva de horas, no
  algo medible en una vela de 1 min.

**Lectura:** a diferencia de las 17:00 de NY en divisas, aquí el diferencial se abre por información, no por falta de
liquidez; no hay motivo para esperar una reversión. Y la distancia a la financiación ya se probó como variable en el
Estudio 33 (no mejoró la política). **Sin estudio nuevo.**

## 3k. Microestructura de cripto: flujo de órdenes, Hawkes y umbral de confianza (2026-11-23, solo resúmenes)

Búsqueda del lunes (literatura). Solo resúmenes del buscador: mdpi.com, link.springer.com, ceur-ws.org y
delphicalpha.substack.com no abren desde la nube.
- Informe de Delphi Digital (feb-2026, blog sin revisión; https://delphicalpha.substack.com/p/crypto-orderflow-alpha-report-feb):
  con fotos de 1 s de Binance (BTC, ETH, SOL, BNB), las señales de desequilibrio del flujo pierden la mitad de su valor
  en 5 s de retraso. Coincide con nuestro Estudio 15 (la ventaja extra vive en 1–2 s; a +10 s ≈ 0).
- Raffaelli, Cestari, Marazzina y Formentin, «Forecasting Bitcoin price movements using multivariate Hawkes processes
  and limit order book data» (Decisions in Economics and Finance, 2026; precursor https://arxiv.org/abs/2312.16190):
  predicen el signo del siguiente movimiento con eventos del libro. Necesita el libro completo evento a evento, que no
  tenemos en historia pública (Binance solo publica operaciones y velas).
- Kuznetsov, «Blockchain-Native Asset Direction Prediction: A Confidence-Threshold Approach…» (Algorithms 18(12) 758,
  2025; https://www.mdpi.com/1999-4893/18/12/758): separar «hacia dónde» de «cuándo operar» con un umbral de confianza
  posterior; con más confianza, menos operaciones y más ganancia por operación; lo mejor a 400–600 min. Un artículo del
  mismo autor (Applied Sciences 15(20) 11145) dice 82,68 % de acierto con 12 % de cobertura: **no verificado** (no
  pudimos leer el método) y a horizontes de horas, no de 1–5 min.
- Krohn, Mueller y Whelan (ya en la bitácora): las 17:00 de NY son la hora de mayor diferencial y menor volumen en
  divisas; Mueller (BIS, https://www.bis.org/events/221213_bis_bdi_ecb_exchange_rates/mueller.pdf) dice que el patrón
  diario no lo explica el diferencial. Es un patrón de horas; nuestro Estudio 34 mide minutos y sí ve que la reversión
  vive en el diferencial abierto. No se contradicen: son horizontes distintos.

**Lectura:** todo repite dos lecciones que ya teníamos: (1) filtrar por confianza es lo único que sube el acierto, y
(2) la información del flujo dura segundos. **Sin estudio nuevo.**

## 3l. Historial verificado, cuarta pasada: Darwinex, señales de MQL5 y concentración de ganancias (2026-11-24, solo resúmenes)

Búsqueda de los martes (traders con historial verificado). Solo resúmenes del buscador; no se abrieron las páginas.

- **Darwinex (resumen DarwinIA, enero de 2026):** publica rentabilidades medianas a 6 meses y caídas, sin porcentaje de
  acierto, y antes de comisiones (1,2 % de gestión y 20 % de éxito). Es material de la propia empresa.
- **Señales de MQL5 enlazadas a Darwinex:** cuentas sueltas con aciertos muy distintos (57 % en 962 operaciones; 12 % en
  una cuenta con apalancamiento 1:200). Son autodeclaradas y elegidas por quien las publica; no se pueden generalizar.
- **Concentración (Finance Magnates sobre datos de iSAM Securities):** el 1 % de las cuentas minoristas ganadoras se
  llevó el 66,5 % de la ganancia de todos los clientes en un año, y el 5 %, el 85,5 %. Encaja con Hyperliquid (3h).
- **Acierto ≠ ganancia (reseña de Cohen, Makov y Schwartz, «The Winning Trade», 2023; no se leyó el artículo):** la
  mayoría de los minoristas gana más operaciones de las que pierde y aun así el 82 % pierde dinero.

**Lectura:** nada nuevo para probar. Repite lo de 3b, 3c y 3h: el acierto alto no es la medida, la ganancia se concentra
en muy pocos y las listas verificadas no dan reglas desarmables sin el historial completo de cada cuenta (solo en sesión
local, idea 2 de docs/10).

Fuentes: https://blog.darwinex.com/hubfs/DarwinIA_SILVER_GOLD_Darwinex/Recap%20Jan%2026.pdf?hsLang=en ;
https://www.mql5.com/en/signals/2310741 ; https://mql5.com/en/signals/2235392 ;
https://www.financemagnates.com/forex/the-winning-few-top-1-of-retail-traders-cause-two-thirds-of-broker-losses/ ;
https://dataconomy.com/?p=98348 ; https://www.mql5.com/en/blogs/post/775015

## 3m. Modelo de BTC 1 min: perpetuo frente a contado y variables de varios plazos (2026-11-25, solo resúmenes)

Búsqueda de los miércoles (mejorar el modelo de BTC 1 min). Solo resúmenes del buscador; researchsquare.com y mdpi.com
no abren desde la nube.

- **Perpetuo frente a contado, al segundo:** no apareció ningún estudio revisado de 2026 que mida, al segundo, si el
  perpetuo de Binance adelanta al contado. Un preprint de Research Square (sin revisión) compara el perpetuo de Binance
  con el de Hyperliquid: Binance recibe los datos casi sin demora y Hyperliquid ~0,48 s después; su medida de
  adelanto usa casillas de 5 s. Lo demás que circula (perpetuos con 4–10 veces el volumen del contado) son cifras de
  volumen, no pruebas de adelanto, y en parte contenido patrocinado.
- **Variables de varios plazos (revista Forecasting 8(3) 40, 2026):** según el resumen, un AUC de 0,60 no basta para
  operar con ganancia y las variables más útiles son de 4 h o más, no de 1 min.
- **«Separation Index» para el minuto de BTC (arXiv 2406.17083, 2024):** elegir las observaciones más informativas;
  es otra forma del filtro por confianza (Estudios 20–21).

**Lectura:** nada que pruebe algo nuevo. La única pieza no probada es el perpetuo de Binance en los segundos 0–49 del
minuto (idea 2c de docs/10), pero el Estudio 24 (ETH y BTC/USDC en esos segundos) mejoró el log-loss sin mejorar la
política, y el Estudio 15 mostró que la información de segundos se pierde antes del clic a +10 s. No se pre-registra.

Fuentes: https://www.researchsquare.com/article/rs-10147582/v1 ; https://www.mdpi.com/2571-9394/8/3/40 ;
https://arxiv.org/html/2406.17083v2 ;
https://cryptoquant.com/insights/quicktake/6a1c6342ae348e5baf3fbb6a-Bitcoin-Dominates-the-Perpetuals-Arena-as-Altcoin-Derivatives-Heat-Up

## 3n. Reversión nocturna: ¿qué plataformas liquidan divisas con precio medio a esas horas? (2026-11-26, solo resúmenes)

Búsqueda de los jueves (reversión nocturna, 21–24 UTC). Solo resúmenes del buscador; kalshi.com y datawallet.com no
abren desde la nube.

- **Nadex (hoy Crypto.com Derivatives North America, solo EE. UU.):** binarias de divisas de 5 min que liquidan con la
  media de los últimos 10 precios MEDIOS antes del vencimiento (justo lo que nuestra reversión necesita). Pero vencen
  cada 5 min de 18:05 a 17:00 de Nueva York: **cierran de 17:00 a 18:05 NY**, que es exactamente nuestra hora fuerte
  (22 UTC en invierno, 21 UTC en verano). Lectura: quien liquida con precio medio se aparta justo cuando el diferencial
  se abre; refuerza que parte de la reversión es efecto de la cotización (docs/10).
- **IG «digital 100s» de 5 min** (EUR/USD, GBP/USD, AUD/USD, USD/JPY): liquidan con el precio medio de IG; no se pudo
  ver su horario a 21–24 UTC. Es un producto de apuestas con diferencial del Reino Unido, no disponible en Colombia.
- **Kalshi:** existe una serie de contratos de EUR/USD a 15 min (KXEURUSD15M; un ejemplo con vencimiento a las 04:00
  de NY del 2026-10-21). Un registro ante la CFTC de un contrato «EUR/USD por encima/debajo de… en <periodo>» nombra
  como fuente a **Pyth Network** (no se pudo leer la regla exacta de la serie de 15 min). Kalshi dice operar en más de
  140 países sin publicar la lista; no se encontró un bloqueo de Kalshi en Colombia, pero Coljuegos bloqueó Polymarket y
  su presidente llama «apuestas disfrazadas» a los mercados de predicción.

**Lectura:** nada que probar hoy. Kalshi 15 min sería la única vía con precio externo (Pyth), pero falta saber (1) si
abre de 21 a 24 UTC, (2) cómo calcula Pyth el precio a esas horas (medio o no) y (3) si es legal y accesible desde
Colombia. Las tres respuestas requieren una sesión local (kalshi.com no abre desde la nube). Queda como idea 5b de
docs/10, de prioridad baja. No se pre-registra nada.

Fuentes: https://cftc.gov/filings/ptc/ptc121614nadexdcm003.pdf ; https://website-prod.nadex.com/contract-specs-forex ;
https://www.ig.com/en/help-and-support/articles/681865-digital-100s-spread-bet-product-details ;
https://kalshi.com/markets/kxeurusd15m/15minute-eurusd/kxeurusd15m-26oct210400 (no abrió) ;
https://www.cftc.gov/filings/orgrules/rules042623963.pdf ; https://help.kalshi.com/en/articles/14026044-international-access-eligibility ;
https://www.bloomberglinea.com/mercados/el-boom-de-polymarket-y-kalshi-apunta-a-us1-billon-pero-enfrenta-bloqueos-en-america-latina/ ;
https://www.pulzo.com/nacion/bloquean-polymarket-colombia-denuncia-por-apuestas-electorales-PP5102235

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
10. Muestra solo las estrategias que salieron bien en una prueba sobre el pasado (por ejemplo, «2 de 5») y no las prueba en un periodo posterior (Estudio 45).
11. Da señales para activos «(OTC)» de las plataformas de binarias: su precio lo produce la propia plataforma, que también es la contraparte. En IQ Option, el «ETH/USD (OTC)» iba 140 USD por encima del Ethereum real y en otra dirección (2026-11-07, docs/01). Ninguna estrategia basada en el mercado aplica ahí.

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

- Efecto del cuarto de hora: https://arxiv.org/abs/2607.09426 ; microestructura explicable: https://arxiv.org/abs/2602.00776 ;
  descubrimiento de precio CME/Binance: https://arxiv.org/abs/2506.08718

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
- MCP de TradingView (README con sus advertencias sobre términos de uso y riesgo de la cuenta): https://github.com/tradesdontlie/tradingview-mcp
- Literatura del 2026-11-16: Concretum (SSRN): https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/ ;
  Kaiser 2024: https://ideas.repec.org/a/eee/finlet/v64y2024ics1544612324004598.html ;
  Kalshi: https://www.ifo.de/DocDL/cesifo1_wp12122.pdf ; https://econpapers.repec.org/RePEc:cpr:ceprdp:20631 ;
  https://www.ucd.ie/economics/t4media/WP2025_19.pdf ; blog de contratos de 5 min (sin verificar):
  https://oddsreference.pages.dev/predictions/research/kalshi-crypto-binary-options
- Hyperliquid (2026-11-17, solo resúmenes): https://www.thecoinrepublic.com/2025/06/16/hyperliquid-crypto-only-166-of-1000-traders-profitable-whats-going-on/ ;
  https://hyprswarm.pages.dev/blog/why-biggest-wallets-worst-win-rate/ ;
  https://www.htx.com/news/data-75-of-traders-on-hyperliquid-are-losing-money-what-are-R2h1lIXH/ ;
  https://beincrypto.com/hyperliquid-traders-profitability ;
  https://protos.com/hyperliquid-leaderboards-confuse-traders-as-hype-hits-all-time-high
- Efecto del cuarto de hora (2026-11-18, solo resúmenes): https://ideas.repec.org/p/arx/papers/2607.09426.html ;
  https://www.emergentmind.com/papers/2607.09426 ; https://cryptoslate.com/the-invisible-opening-bell-inside-cryptos-endless-trading-day/ ;
  líder futuros/contado (resumen de CCN sobre Easley, O'Hara, Yang y Zhang 2024): https://www.ccn.com/analysis/technology/perpetuals-account-majority-crypto-market-behavior/
- Horas de financiación (2026-11-19, solo resúmenes): https://afajof.org/management/viewp.php?n=169764 ;
  https://business.cornell.edu/centers/?p=5984 ; https://www.mdpi.com/2227-7072/14/5/103 (no abre desde la nube) ;
  https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin ; https://ledger.pitt.edu/ojs/ledger/article/view/213
