# Análisis del informe «El secreto del trading profesional» y qué sirve para el bot (2026-10-24)

> Documento analizado: `informe-trading-profesional.pdf` (20 páginas, guía educativa fechada en octubre de
> 2026, entregado por el usuario en una memoria USB). Se leyó completo. Las cifras de la sección 2 salen de
> `scripts/simulacion_grupos_senales.py` → `results/grupos_senales.json` (velas reales de BTC/USDT, semilla
> fija, reproducible). Las de la sección 3, de los resultados ya registrados en este repositorio.

## 0. Respuesta corta

1. **El PDF no contiene ninguna tasa de acierto ni ninguna prueba con datos.** Es una guía de *método*:
   contexto → zona → reacción → confirmación → entrada → gestión → revisión. Sus fuentes (CME, IG,
   Reserva Federal de Nueva York, artículos académicos) son serias, pero ninguna promete 80–90 %.
2. **El «90 %» de los grupos se fabrica con aritmética, no con predicción.** Con señales **al azar** sobre
   velas reales de BTC, contando «acierto» como lo cuentan los grupos (repetir con el doble tras perder:
   «gale», «M2», «M3»), el acierto por ciclo es **87,4 %** con 2 repeticiones y **93,7 %** con 3, y aun así
   se **pierde** ~7,9 % de lo apostado. De 1 000 canales que publican señales al azar, **124 muestran
   ≥ 90 %** en un mes. El PDF mismo menciona «M2 y M3» y las «reentradas» (sección 13 del PDF).
3. **El número que hay que superar no es 90 %, es 54,05 %** (con pago del 85 %). El proyecto ya lo superó
   una vez con evidencia sólida: BTC 1 min con entrada automática a +2 s, **57,63 %** en 3 500 alertas
   sin empate (Enmienda 2), aunque la ventaja se debilitó después (54,1 %). Sin repeticiones, el **mejor**
   de 1 000 canales al azar llega a 58,7 % en un mes… y al mes siguiente cae a 46,7 %.
4. **Del PDF se puede aprovechar** sobre todo una idea que el proyecto nunca probó: las **zonas** (soportes,
   resistencias, máximos/mínimos del día anterior y **números redondos**), que tienen respaldo académico
   (Osler, Reserva Federal de Nueva York). Se pre-registró y ejecutó un **Estudio 6** (sección 6): **no mejora**, SIN SEÑAL. También
   se adoptan las partes de **gestión y diario**, útiles para la prueba en cuenta demo.
5. Lo que **no** se adopta: la martingala/reentradas para recuperar pérdidas y cualquier promesa de
   80–90 %.

## 1. Qué es el PDF y qué afirma realmente

El propio documento se declara «guía educativa y cuaderno de trabajo» y separa «propuestas», «plantillas»
y «protocolos» de los hallazgos de investigación. Sus 23 secciones se agrupan así:

| Bloque del PDF | Contenido | ¿Contiene evidencia de acierto? |
|---|---|---|
| Principio central, conocer el instrumento, leer la estructura | Ficha del instrumento; clasificar el mercado en subida, bajada, rango, compresión, expansión | No |
| Zonas y reacción | Marcar máximos/mínimos previos, extremos de rango, números redondos; leer la reacción de las velas | Cita a Osler (ver 4.1) |
| Separar dirección y entrada | Contexto H1, preparación M15, ejecución M5 | No («organización propuesta, no universal») |
| Volumen y órdenes | Desequilibrio del flujo de órdenes | Cita a Cont, Kukanov y Stoikov y a Kolm et al. (ver 4.2) |
| Indicadores, noticias, posicionamiento (COT) | Dar una función a cada herramienta; calendario; informes semanales de la CFTC | No |
| M2 y M3, reentradas | Repetir la entrada tras un intento fallido | No (ver sección 2) |
| Gestión, ejecución, diario, disciplina | Presupuesto por operación/idea/sesión; registrar precio pedido vs. ejecutado | No, es método |

Dos frases del PDF coinciden exactamente con la forma en que trabaja este proyecto: «escribe sus reglas
antes de revisar los resultados» y «comprueba posteriormente las mismas reglas en observaciones nuevas»
(sección 16 del PDF). Eso es el pre-registro y el periodo bloqueado.

## 2. ¿Cómo «aciertan 90 %» otros? Cinco mecanismos, medidos

### 2.1 Repeticiones tras perder («gale», «M1/M2/M3»)

En los grupos de señales, si la entrada pierde se repite en la vela siguiente con más dinero, y el ciclo
se anota como «acierto» si gana en **cualquier** intento («WIN», «WIN en gale»). Simulación con dirección
**aleatoria** en 200 000 ciclos sobre velas reales de BTC/USDT de 1 minuto (2025-09 → 2026-08), pago 85 %,
empate reembolsado:

| Forma de contar | «Acierto» por ciclo | Ciclos perdidos | Pérdida cuando se pierde | Ganancia por unidad apostada |
|---|---|---|---|---|
| Una sola entrada (lo que mide el proyecto) | 49,9 % | 50,1 % | −1 | **−0,076** |
| 1 repetición (apuestas 1, 2) | 74,7 % | 25,3 % | −3 | **−0,081** |
| 2 repeticiones (1, 2, 4) | **87,4 %** | 12,6 % | −7 | **−0,079** |
| 3 repeticiones (1, 2, 4, 8) | **93,7 %** | 6,3 % | −15 | **−0,077** |
| 2 repeticiones «para recuperar» (1; 2,18; 4,75) | 87,4 % | 12,6 % | −7,93 | **−0,078** |

Lanzar una moneda con 3 repeticiones da **93,7 % de «acierto»**. Las repeticiones solo cambian *cómo se
cuenta*, no el resultado: se pierde lo mismo por cada peso apostado, pero en golpes grandes y poco
frecuentes que llegan de repente. (Confirma con datos reales el cálculo exacto de docs/02, sección 6.1.)

### 2.2 Muchos canales, se ve solo el que tuvo suerte

Se simularon 1 000 «canales» que publican 300 señales al azar en un mes, y se miró el mismo canal el mes
siguiente:

| | Sin repeticiones | Con 2 repeticiones |
|---|---|---|
| Acierto mediano de los 1 000 canales | 50,0 % | 87,3 % |
| Canales con ≥ 90 % en el mes | 0 | **124** |
| Mejor canal del mes | **58,7 %** (+25,6 unidades) | **93,7 %** (+78,1 unidades) |
| Ese mismo canal al mes siguiente | 46,7 % (**−41** unidades) | 88,3 % (**−51,9** unidades) |
| Canales que ganaron dinero en el mes | 74 de 1 000 | 55 de 1 000 |

Los canales que pierden cierran o cambian de nombre; los que tuvieron un buen mes publican capturas. Desde
fuera solo se ve el ganador, que al mes siguiente vuelve a lo normal. Por eso el proyecto exige **miles**
de operaciones y un periodo nuevo para confirmar.

### 2.3 Definiciones flexibles de «acierto»

- En el estudio de Osler (sección 4.1), el precio «rebotó» en niveles **elegidos al azar** el **56,2 %** de
  las veces, por cómo se define «rebote» (no cruzar el nivel en 15 minutos). Los niveles profesionales
  rebotaron el 60,8 %. La diferencia real es de **4,6 puntos**, no de 60.
- En docs/02 (sección 6), entradas al azar con objetivo de ganancia pequeño y límite de pérdida grande
  dan **79 % de «acierto»** y pierden dinero en los cuatro instrumentos.

### 2.4 Lo que no se puede medir desde fuera

Borrar señales perdidas, publicar la señal *después* del movimiento, no contar empates o contar «acierto
parcial». Ninguna de las cifras de 80–90 % que se buscaron en la revisión del 2026-10-03 (docs/02, 6.3) se
pudo rastrear a un registro verificable.

### 2.5 El contrato juega en contra

Con pago del 85 % hay que acertar 54,05 % solo para no perder. La autoridad europea de valores (ESMA)
**prohibió** las opciones binarias para minoristas en 2018 porque los análisis de los supervisores
nacionales encontraron pérdidas constantes en las cuentas de clientes, una rentabilidad esperada
negativa propia del producto y un conflicto de interés entre el proveedor y el cliente.

**Conclusión de la sección:** no estamos «por debajo» de los grupos. Medimos con una regla más estricta.
Medido con la regla de ellos (2 repeticiones), cualquier sistema, incluso uno al azar, ronda el 87 %.

## 3. Dónde está el proyecto, con la regla correcta

| Configuración | Acierto (una sola entrada) | ¿Supera 54,05 %? | Estado |
|---|---|---|---|
| Divisas y oro, 1–60 min | 50,5–51,3 % | No | SIN SEÑAL |
| BTC 1 min, entrada automática +2 s (Enmienda 2, sep. 2026) | **57,63 %** [lím. inf. 55,98 %] | **Sí** | Aprobó; ventaja debilitada después (54,1 %) |
| BTC 1 min, entrada +10 s (manual realista), datos nuevos oct. 2026 | **56,11 %** [lím. inf. 54,46 %], EV +0,034 | **Sí** | **Estudio 5, H5a APRUEBA** (2026-10-25): solo demo. Entre semana 53,2 %, fin de semana 58,4 % |
| BTC 15/60 min, ETH 15 min, flujo de órdenes (Estudios 2–4) | 52,9–54,2 % | No | SIN SEÑAL |
| Mejor canal al azar en un mes (sección 2.2) | 58,7 % | Por suerte | Al mes siguiente, 46,7 % |

Un sistema que acierte **56–58 % de forma sostenida, en miles de operaciones** gana dinero con pago del
85 %. Eso es lo que buscamos, y ya apareció una vez en BTC. Lo que falta es confirmar que se mantiene
con datos nuevos y con una entrada que el usuario pueda hacer.

## 4. Las ideas del PDF, una por una

| Idea del PDF | Evidencia | ¿Ya la probó el proyecto? | ¿Sirve para el bot? |
|---|---|---|---|
| Análisis multitemporal (H1 contexto, M15 preparación, M5 entrada) | Recomendación de IG/CME, sin cifras | **Sí**: el modelo usa rendimientos de 1 a 240 min, medias de 20 y 60, posición en el rango (Fase 1B) | Ya incluido; en divisas no dio señal |
| Indicadores (medias, RSI, Bollinger, volatilidad) | — | **Sí** (H4): no superan al azar tras costos en divisas/oro | Ya incluido |
| **Zonas: soportes/resistencias, máximos/mínimos del día anterior, números redondos** | **Osler 2000 y 2003** (4.1); barreras en múltiplos de 1 000 en BTC (estudios con datos diarios) | **Sí** (Estudio 6, 2026-10-24) | **No**: no mejoran; SIN SEÑAL |
| Flujo de órdenes (desequilibrio del libro) | Cont et al. 2014; Kolm et al. 2023 (4.2) | **Parcial**: Estudio 3 (flujo agresor por minuto) no mejoró | No para señales manuales (horizonte de segundos) |
| Noticias y calendario | La dirección depende de la sorpresa, que no se conoce antes | **Sí** (H5): el filtro de noticias reduce caídas | Ya incluido (política BN) |
| Posicionamiento COT (CFTC) | Publicación semanal con datos del martes | No | No a 1–15 min (llega con días de retraso) |
| M2/M3 y reentradas para recuperar | Sección 2.1: no cambia la ganancia esperada | **Sí** (docs/02, 6.1) | **No**: descartada |
| Presupuesto por operación, por idea y por sesión | Método (CME) | Parcial (`execution/guard.py` limita monto y pérdida diaria en dinero real) | **Sí**: adoptar en la prueba demo (5.3) |
| Diario: precio pedido vs. ejecutado, hora de envío y de ejecución | Método (CME, Vanguard) | Parcial (libro de la cuenta simulada) | **Sí**: es justo lo que exige la prueba demo del Estudio 5 |
| «Aprender de otros traders» reconstruyendo qué sabían antes de entrar | Método | No | **Sí**: auditor de señales de terceros (5.4) |

### 4.1 Zonas y números redondos (Osler, Reserva Federal de Nueva York): lo más aprovechable

- **Osler (2000)**, *Support for Resistance*: niveles publicados a diario por 6 firmas (1996–1998;
  dólar-marco, dólar-yen, dólar-libra), con precios de 1 minuto. El precio «rebotó» (no cruzó el nivel en
  los 15 minutos siguientes) el **60,8 %** de las veces en niveles publicados, frente al **56,2 %** en
  niveles arbitrarios. La diferencia fue significativa en todos los pares y duró al menos una semana. La
  autora **no comprobó si era rentable**. Además, el 96 % de los niveles terminaba en 0 o 5.
- **Osler (2003)**, *Currency Orders and Exchange Rate Dynamics* (Journal of Finance), con ~9 700 órdenes
  reales de un banco: las órdenes de **toma de ganancias** se agrupan **en** números redondos (explica los
  rebotes) y las de **stop-loss** justo **después** de ellos (explica las aceleraciones al romper). El
  informe posterior n.º 150 encontró movimientos inusualmente rápidos al llegar a esas zonas.
- En BTC, estudios con datos diarios encontraron barreras en múltiplos de 1 000 y 10 000 y agrupamiento en
  múltiplos de 10 y 100. Es plausible que hoy las liquidaciones de apalancamiento se agrupen también ahí.

**Por qué puede servir aquí y por qué podría no servir:** el mecanismo (órdenes acumuladas en niveles
conocidos) es real y documentado, y nuestro modelo **no sabe dónde están esos niveles**. Pero la
evidencia en divisas es de 1996–1998, el efecto medido es de ~4–5 puntos en la frecuencia de rebote (no
en dirección a 15 minutos con pago fijo) y puede haberse reducido desde entonces. Se prueba con un
estudio nuevo, sin promesas.

### 4.2 Flujo de órdenes: real, pero demasiado rápido para operar a mano

- **Cont, Kukanov y Stoikov (2014):** el desequilibrio del libro explica bien el cambio de precio **del
  mismo intervalo** (es simultáneo, no anticipa minutos).
- **Kolm, Turiel y Westray (2023, Mathematical Finance):** redes neuronales con el libro de 115 acciones del
  Nasdaq. Según el resumen de Quantpedia, la precisión es máxima a **dos cambios de precio** de distancia
  (segundos) y baja después.
- **Estudio 3 del proyecto:** el flujo agresor por minuto (contado y perpetuo) no mejoró la predicción a
  15 minutos.

Solo serviría en una **automatización** con entrada en segundos y datos del libro en vivo (portátil
encendido o servidor). El usuario hoy no quiere automatizar, así que queda archivada.

## 5. Plan de trabajo (en orden de prioridad)

### 5.1 Terminar el Estudio 5 (lo más cercano a una señal manual utilizable)

Ya está pre-registrado (docs/01). Con el ritmo de septiembre (~177 alertas sin empate por día), se estima
que la muestra de **H5a** (3 500, todas las horas) se completa hacia **finales de octubre de 2026** y la de **H5b** (2 500,
solo fines de semana UTC) hacia el **2026-11-22**, antes del plazo del 2026-12-13. Son estimaciones; el
conteo real lo dará la reproducción.

**Código listo (2026-10-24):** `tbot study5-verdict` y el flujo `.github/workflows/estudio5.yml` (Actions →
«Estudio 5» → Run workflow, con el día final excluido). Reproduce desde el 2026-10-04 con entrada a +10 s.

**Enmienda del mismo día (antes de ver datos nuevos):** Bonferroni (α = 0,025 por hipótesis) en lugar de
Holm. Así **H5a se evalúa en cuanto su muestra está completa**, sin esperar a H5b. De una hipótesis
incompleta solo se informa el conteo. H5b se evalúa cuando se complete, hacia el 2026-11-24.

### 5.2 Estudio 6: zonas — ejecutado, SIN SEÑAL (sección 6)

Es la única idea del PDF con respaldo académico que el proyecto no ha probado.

### 5.3 Gestión y diario para la prueba en cuenta demo (si el Estudio 5 aprueba)

Del PDF, sección 14–17, adaptado:
- **Presupuesto fijo** por operación (p. ej., 1 unidad = 1 % de la cuenta demo); **sin** repeticiones.
- **Pérdida máxima por sesión**: se detiene el día al perder 10 unidades. Esto *no* mejora el acierto,
  solo evita la ruina en rachas, que en BTC 1 min llegaron a −280 unidades en un año (docs/02, sección 5).
- **Diario por operación**: hora de la alerta, hora real del clic, precio de la plataforma vs. Binance al
  entrar y al vencer, pago ofrecido, empate o no. Así se comprueba lo que exige el Estudio 5 antes de
  cualquier otra cosa: que el precio del intermediario sigue al de Binance, que el empate se reembolsa y
  que el pago es ≥ 85 %.

### 5.4 Auditor de señales de terceros

Si el usuario sigue un grupo que dice acertar 90 %, la forma profesional de comprobarlo es la del PDF
(sección 18): registrar **cada** señal *antes* de que empiece la vela (captura con hora) y calcular con
nuestros datos:
- el acierto de la **primera** entrada;
- el acierto contando repeticiones;
- la ganancia neta.

Se puede añadir un comando `tbot` que lea esas señales de un archivo y las evalúe contra las velas de
Binance. Si alguna vez un grupo muestra más de 54,05 % en la primera entrada con cientos de señales
registradas de antemano, eso sí sería información útil para el proyecto.

### 5.5 Lo que no se hará

- Martingala, gale o reentradas para recuperar pérdidas.
- Anunciar un acierto que no salga de una muestra fija evaluada en datos nuevos.
- Operar con dinero real sin autorización expresa y específica del usuario.

## 6. Estudio 6: zonas de precio — resultado: SIN SEÑAL

Pre-registrado el 2026-10-24 en docs/01 (commit bc97dc0). El código se congeló antes de ejecutarlo
(37fdd3f). Fase de desarrollo 2022-01 → 2025-08, a 15 minutos, entrando 1 minuto después:

| Instrumento | Acierto solo precio | Acierto precio + zonas | ¿Las zonas mejoran la predicción? |
|---|---|---|---|
| BTC/USDT | 55,61 % (EV +0,029) | 55,19 % (EV +0,021) | **No** (IC del log-loss incluye 0; la ganancia baja) |
| EUR/USD | 53,76 % (EV −0,005) | 51,64 % (EV −0,044) | **No** (empeora) |

Las zonas que describe el PDF (números redondos, máximo y mínimo del día anterior, extremos recientes y
sus toques) **no añaden información** a lo que el modelo ya sabe del precio. El efecto de Osler era sobre
«rebotes» en divisas de 1996–1998. No aparece como ventaja de dirección a 15 minutos en 2022–2025. Como no
pasó el desarrollo, no hay fase de confirmación.

## 7. Kronos y la estrategia del video (2026-10-25)

### 7.1 Qué es Kronos, con datos verificados

- **Origen:** modelo de investigación de la Universidad Tsinghua (arXiv 2508.02739), aceptado en AAAI 2026,
  con código abierto (licencia MIT) y modelos públicos en Hugging Face: mini 4,1 M, small 24,7 M y base
  102,3 M de parámetros; large 499 M no es público.
- **Cómo funciona:** convierte cada vela en **6 números** (apertura, máximo, mínimo, cierre, volumen e
  importe) y los comprime en **tokens binarios** de 2 × 10 bits. Después un modelo tipo GPT predice el
  siguiente «token-vela», igual que un chatbot predice la siguiente palabra. Es exactamente lo que
  describe el video en su primera parte.
- **Datos de entrenamiento:** más de 12 000 millones de velas de 45 bolsas, incluidas velas de 1 minuto de
  perpetuos de Binance, **hasta junio de 2024**.
- **Resultados publicados por los autores:** miden correlación de rango (RankIC), no porcentaje de acierto.
  - En cripto, la correlación con el rendimiento siguiente es **≈ 0,03–0,04**. Eso equivale, como mucho,
    a **~51 % de acierto en dirección**.
  - La única prueba de inversión es con acciones chinas a 5 días.
- **Pruebas independientes:** son pocas y no revisadas.
  - Una de BTC a 5 minutos (497 operaciones) no encontró ventaja sobre un paseo aleatorio.
  - Un ajuste fino en acciones de la India mejoró la calibración pero no dio ganancia.
- **El propio repositorio advierte** que su ejemplo «no es un sistema de trading listo para producción».

### 7.2 La estrategia del video, pieza por pieza

El video mezcla Kronos con tres herramientas clásicas. No se encontró el código exacto del video. Las
partes se reconocen así:

| Pieza del video | Qué es en términos técnicos | ¿El proyecto la tenía? |
|---|---|---|
| «Cada vela en 6 dimensiones → tokens binarios» | Tokenizador de Kronos | No |
| «Busca en el historial los momentos más parecidos y promedia lo que pasó después» | Pronóstico por análogos (vecinos más cercanos) | No |
| «Kalman afina la proyección» | Filtro de Kalman de tendencia (nivel + pendiente) | No (el modelo usa medias móviles) |
| «Otros activos afinan» | Información cruzada (ETH para BTC) | Solo a 15 min (Estudio 3, sin mejora) |
| «Dibuja 12 velas; si el retorno supera el umbral, señal larga o corta» | Umbral sobre el rendimiento previsto | Sí: la política B hace lo mismo con la ganancia esperada |

### 7.3 Cómo se prueban: Estudio 7 (pre-registrado, commit 1492079)

Se tratan como **herramientas para mejorar nuestro modelo**, como pediste. La pregunta no es «¿Kronos
acierta?», sino «¿nuestro modelo acierta más si le añadimos Kronos, los análogos, el Kalman o ETH?».
- **Instrumento:** BTC a 1 minuto, el que aprobó H5a.
- **Periodo:** 20 000 minutos sorteados entre octubre de 2024 y agosto de 2025. Empieza **3 meses después**
  del fin del entrenamiento de Kronos, para que no «recuerde» los datos.
- **Criterio:** cada herramienta debe mejorar la predicción con un margen estricto (corrección por
  probar 4 a la vez) y no bajar la ganancia esperada.
- **Expectativa declarada:** probablemente ninguna mejore, porque el modelo ya usa los movimientos
  recientes y la correlación publicada de Kronos es baja. Si alguna mejora, se confirma con datos nuevos
  antes de tocar las señales.

## 8. Fuentes consultadas (2026-10-24 y 2026-10-25)

- Osler, C. (2000). *Support for Resistance: Technical Analysis and Intraday Exchange Rates*. FRBNY
  Economic Policy Review, julio de 2000. https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.html
  (se leyó el texto completo: cifras 60,8 % vs. 56,2 %, datos 1996–1998, rebote = no cruzar en 15 min).
- Osler, C. (2003). *Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success
  of Technical Analysis*. FRBNY Staff Report 125 / Journal of Finance.
  https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.html
- Osler, C. *Stop-Loss Orders and Price Cascades in Currency Markets*. FRBNY Staff Report 150.
  https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.html
- Cont, R., Kukanov, A., Stoikov, S. (2014). *The Price Impact of Order Book Events*. https://arxiv.org/pdf/1011.6402
- Kolm, P., Turiel, J., Westray, N. (2023). *Deep order flow imbalance: Extracting alpha at multiple
  horizons from the limit order book*. Mathematical Finance 33(4), 1044–1081.
  https://ideas.repec.org/a/bla/mathfi/v33y2023i4p1044-1081.html (hallazgo de horizontes según el resumen de
  Quantpedia: https://quantpedia.com/tag/order-flow/; no se leyó el artículo completo).
- Barreras psicológicas en criptomonedas: https://repositorio.upt.pt/bitstreams/d51ddf5d-267b-4b39-94f1-ba85a5a03486/download
  y https://dspace.kaist.ac.kr/handle/10203/284836 (solo resúmenes).
- ESMA (2018). *ESMA agrees to prohibit binary options and restrict CFDs to protect retail investors*.
  https://www.esma.europa.eu/node/84933
- Kronos: https://arxiv.org/html/2508.02739v1 (leído: tokenizador, datos hasta junio de 2024, tablas de cripto),
  https://github.com/shiyu-coder/Kronos (licencia, modelos, advertencias). Pruebas independientes (no verificadas):
  https://digitechbytes.com/?p=48934 y https://huggingface.co/sahil007123/kronos-nse-1d.
- Herramientas análogas en TradingView: https://kr.tradingview.com/script/TiOb6SUA-K-NN-Pattern-Forecast/
  (análogos) y https://vn.tradingview.com/script/OxYmisSS-Kalman-Filter-Loxx (Kalman).
- Formato de señales con «gale» en grupos de Telegram: ejemplos de encargos y de indicadores públicos
  (https://www.workana.com/job/criacao-de-sala-de-sinais-automatica-para-telegram,
  https://es.tradingview.com/script/c3PBuxF5). No se encontró una definición estándar de «M2/M3»; el
  PDF las define como intentos o niveles de una secuencia.
