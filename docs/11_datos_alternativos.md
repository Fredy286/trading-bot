# Datos alternativos: redes, foros, posicionamiento de la multitud y noticias (2026-11-21)

> **Pedido del usuario (2026-11-15):** un prompt de «Quantitative Trader y especialista en NLP». Pide minar redes
> sociales, foros y comunidades de traders y convertir lo que dicen (sentimiento, sesgos, contradicciones) en
> variables y reglas para el bot. Exige demostrar con datos que mejoran el acierto y llevar una memoria viva de lo
> probado.
>
> **Cómo se hizo:** un equipo de agentes trabajó con las reglas del proyecto.
> - Fuentes sin cuenta: texto social, posicionamiento en derivados, noticias y calendario.
> - Literatura seria y lógicas de las comunidades.
> - Exploración *post hoc* con las predicciones de desarrollo (≤ 2026-10-25).
>
> Las dos pistas más fuertes se volvieron a calcular con código propio antes de pre-registrarlas (Estudio 72).
> Todo lo de este informe es *post hoc*: sirve para proponer estudios, no para afirmar que algo funciona.

## Respuesta corta

1. **Las redes sociales, el posicionamiento de la multitud y las noticias no predicen la dirección a 1–15 min:
   SIN SEÑAL.** Siguen al precio en vez de anticiparlo, y a lo sumo anuncian volatilidad.
2. **Ninguna fuente de texto social sirve en vivo con las reglas del proyecto.** Las que tienen historia no llegan a
   tiempo; las que llegan a tiempo no tienen historia, y X, Discord y TradingView exigen cuenta o prohíben la recolección
   automática.
3. **Lo único útil salió de desarmar las creencias de las comunidades:**
   - «la tendencia es tu amiga» funciona AL REVÉS a 5–15 min;
   - en la apertura de Nueva York nuestros modelos pierden la ventaja.

   De ahí salen dos **reglas para NO operar** (vetos), que se confirman con datos nuevos en el **Estudio 72**.
4. **Lo que suben:** en el pasado, en las horas en que IQ Option tiene abierto el blitz de Bitcoin real, el p42
   pasaba de 54,5 % a **55,9 %** y de +114 a **+247** de ganancia con los vetos. Lo más probable en enero es «sin
   confirmar», por falta de señales.

## 1. Mapa de fuentes

**Criterios para que una fuente sirva:**
1. historia al segundo que cubra 2025-09 → 2026-10 (los meses de prueba);
2. dato en vivo, sin cuenta y con segundos de retraso;
3. suficientes mensajes por ventana de decisión;
4. términos de uso claros, y la misma forma de recoger el dato en la historia y en vivo.

**Texto social y noticias:**

| Fuente | Qué es | Veredicto | Por qué |
|---|---|---|---|
| Reddit (Arctic Shift) | Comentarios con hora al segundo, 420 de 420 días | Parcial | En vivo llega con 4–6 h de retraso desde mediados de octubre. Solo 1,6 comentarios/min sobre BTC, y bajando. El agregado por minuto trae la hora corrida 1–2 h: usarlo sin corregir mete futuro |
| Telegram público (t.me/s) | Canales de noticias (Watcher.Guru, Cointelegraph) con hora al segundo | Viable | Historia completa y vivo sin cuenta. Fue la fuente de la prueba de noticias |
| Bluesky, Nostr, 4chan /biz/ | Mensajes en vivo | Parcial | Sin historia accesible (~38 h o nada). El archivo de 4chan prohíbe robots |
| X/Twitter, Discord, TradingView, Stocktwits | — | Inviable | Exigen cuenta o prohíben la recolección automática (docs/07) |
| Calendario macro (Fed, BEA, NY Fed) | Hora exacta de IPC, empleo, FOMC, PIB, PCE | Viable | La BLS bloquea a los programas; ForexFactory solo da la semana en curso |
| GDELT, RSS de medios | Noticias con tono | Inviable | GDELT llega horas tarde (el 10-oct-2025, 2,5 h después del desplome) y pesa ~300 GB. Los RSS guardan solo 2–3 días |
| Wikipedia, Google Trends, CryptoPanic | Atención | Inviable o diaria | Con historia, Wikipedia solo da vistas por día. Trends y CryptoPanic exigen cuenta o clave |

**Posicionamiento en derivados:**

| Fuente | Qué es | Veredicto | Por qué |
|---|---|---|---|
| Binance «metrics» (5 min) | Ratio largo/corto de cuentas y de grandes cuentas, interés abierto, ratio tomador | Viable, con trampa | `create_time` es el INICIO del periodo: unir por esa hora mete 5 min de futuro. En vivo publica 0,5–4,75 min tarde. Binance regeneró el histórico en 2026 |
| Bybit (5 min) | Ratio de cuentas e interés abierto | Viable | Publica en 12–24 s y no cambia después |
| Gate | Liquidaciones por lado, cada 5 min | Parcial | Solo 180 días; la fila T cubre [T−1, T+4) |
| Deribit, Coinbase, F&G, stablecoins | Volatilidad implícita, prima, índices diarios | Viable | Diarios o lentos para 1–15 min |

## 2. Qué se encontró (desarrollo, *post hoc*)

**Posicionamiento de la multitud (≈ 410 variantes).**
- Ratio de cuentas de Bybit y Binance: AUC 0,500. «La multitud siempre pierde» no se ve a 1–15 min.
- Interés abierto: nada.
- Liquidaciones: copian el movimiento ya ocurrido (correlación −0,46 con los 15 min previos) y no dicen nada del
  siguiente.
- «Giro brusco» (salto del ratio o del interés abierto): el modelo de 1 min acierta 53,7 % frente a 58,3 %, pero es
  un marcador de volatilidad. Quitarlo deja la misma ganancia con menos operaciones, como el Estudio 48.
- **docs/08 P7 queda cerrada:** sin señal.

**Noticias (11 111 titulares de Telegram, 89 variantes).**
- La velocidad de titulares sigue a la volatilidad.
- La polaridad del léxico (alcista o bajista) acierta 50,1 %.
- La «divergencia narrativa-precio» es solo la reversión del propio precio.
- Las noticias van detrás del precio: los titulares de precio repiten el signo de los 30 min anteriores el 70,6 % de
  las veces. El arancel del 100 % (10-oct-2025) se publicó con BTC ya −0,9 % en 30 min.
- Única pista: una hora después de un titular polarizado, el gran bot de OKX 5 min acierta 53,1 % frente a 56,8 %.
  Pero no sube la ganancia y no se repite en OKX 15, el blitz ni BTC 1 min. **Débil, no se adopta.**

**Calendario macro.**
- BTC se mueve mucho en el minuto del dato: IPC ×14,5, empleo ×6,9, FOMC ×6,5.
- Pero evitar esas ventanas toca menos del 1 % de las operaciones y no cambia la ganancia: sin señal.
- Sirve solo como aviso informativo en el panel («IPC en 12 min»).

**Literatura (52 hallazgos).**
- El sentimiento predice volatilidad, volumen y saltos, no la dirección.
- El mejor resultado publicado a 1–15 min con Twitter es 51–54 %, sin ganancia tras costos (Jaquart et al. 2021).
  El bot ya está en 55–57 % solo con precio.
- El sentimiento sigue al precio más de lo que lo anticipa.
- El ratio largo/corto de Binance no tiene ni un estudio revisado por pares.

**Lógicas de las comunidades (13 creencias de dirección y 10 reglas defensivas).**
- Dan entre 49,5 y 51 %, como una moneda:
  - «el desplome de las 10» y «la subida del domingo»;
  - «la caída del lunes» y «la venta asiática»;
  - «el relleno del hueco del CME» (se rellena igual que un nivel puesto al azar a la misma distancia);
  - «comprar el miedo», «el squeeze por financiación» y «los números redondos».
- **Funcionan al revés:**
  - «la tendencia es tu amiga»: la tendencia de 60 min continúa solo el 47–49 % de las veces a 5–15 min;
  - «las mechas se rellenan»: domina la continuación, que ya es la pieza `clpos` del modelo.
- **Información real, pero ya dentro del modelo:** la reversión tras una cascada (56–57 % a 15 min, más débil en 2026).
- **Contradicen a la comunidad:** no operar el fin de semana (el bot acierta MÁS: H5b del Estudio 5 aprobó con
  58,2 %), no operar tras una cascada y evitar el mercado lateral.

## 3. Reglas exactas que se adoptan para confirmar (Estudio 72, congeladas)

- **tend60(t)** = signo(ln C[t−1] − ln C[t−61]), donde C es el cierre de 1 min del contado de Binance y t la vela de
  decisión.
- **D1 (veto):** no operar si la señal va a favor de tend60.
- **D2 (veto):** no operar si el contrato empieza de lunes a viernes entre las 9:30 y las 10:59 de Nueva York. En
  Bogotá es de 8:30 a 9:59 con el horario de verano de EE. UU. y de 9:30 a 10:59 el resto del año. Nunca toca el
  horario del usuario.
- **Rol:** solo filtros defensivos, que nunca generan señales.
  - D1 no es «poca confianza»: dentro de cada tercil de confianza, las vetadas aciertan 47,5–50,1 % frente a 54,5–56,9 %
    (logística: z = −4,1).
  - El modelo de 3–15 min sigue confiado cuando apuesta a que la tendencia continúa, y a esos plazos domina la
    reversión.

| Contrato (desarrollo) | Sin veto | Vetadas | Con veto |
|---|---|---|---|
| Blitz p42, horas abiertas de IQ | 7 979 op., 54,53 %, +113,9 | 1 722 (21,6 %), 49,6 %, −133,6 (p ≈ 0,002; 12/12 meses peores) | 6 257 op., **55,89 %**, **+247,4** |
| Gran bot de OKX 15 min | 18 135 op., 55,79 %, +484,1 | 3 273 (18 %), 51,3 %, −58,7 (p ≈ 0,044) | 14 862 op., 56,78 %, +542,8 |
| Gran bot de OKX 5 min | — | +6,5 al quitarlas (p ≈ 0,42) | No se aplica |
| BTC 1 min | — | D1 no sirve (las vetadas son iguales o mejores) | No se aplica |

## 4. Arquitectura de integración

- **Una capa de veto DESPUÉS del modelo,** sin reentrenar nada ni tocar las piezas congeladas.
- **Datos:** usa solo los cierres de 1 min de Binance que el bot ya lee y el reloj de Nueva York. No hace falta
  ninguna fuente nueva, cuenta ni clave.
- **Blitz:** se aplica solo dentro del horario real de IQ Option (`config/horario_iq_blitz.json`).
- **En el panel,** solo si se confirma: la señal vetada no suena y se muestra el motivo («a favor de la tendencia de
  1 h» o «apertura de Nueva York»).
- **Las fuentes de redes y noticias NO se integran:** no aportan dirección, llegan tarde o violan términos de uso.
  Única excepción posible: un aviso informativo del calendario macro en el panel, sin cambiar las señales.

## 5. Plan de validación (pre-registro defc48c, código 33e3833)

1. **H72a:** en el blitz con p42 congelado, en horas abiertas de IQ, la suma de lo vetado es < 0.
2. **H72b:** en el gran bot de OKX 15 min, la suma de lo vetado es < 0.
3. **Prueba:** 10 000 remuestreos por semanas ISO; ≥ 100 señales vetadas; Holm entre las dos hipótesis.
4. **Tres miradas, una vez cada una:** enero (α 0,01), abril (0,02) y julio de 2027 (0,02), con los registros sellados
   `blitz` y `gran15`. Comando: `tbot research study72 --mirada …`.
5. **Potencia realista** (en el registro hay 4 veces menos señales del p42 que en desarrollo): ~5 % en enero, ~20 % en
   abril y ~30 % en julio para H72a. Lo más probable en enero: «sin confirmar».
6. **Consecuencia:** solo si pasa, el modo de práctica deja de avisar las vetadas. Nunca dinero real.

## 6. Rúbrica de alfa (para cada idea nueva)

1. Mecanismo escrito antes de mirar los datos.
2. Regla exacta, calculable antes del segundo 50 con datos gratis y sin cuenta, también en vivo, con la latencia
   medida.
3. Para una entrada: tasa base ≥ equilibrio + 2 puntos en los dos periodos. Para un veto: efecto en la mayoría de los
   contratos y que no baje la ganancia total.
4. Estable en ≥ 70 % de los meses y no explicado por la confianza del modelo ni por la volatilidad.
5. Prueba de causalidad inversa: correlación con el pasado frente al futuro.
6. Las comparaciones hechas, contadas; la familia, pre-registrada con Holm o Bonferroni.
7. Confirmación única con datos posteriores al 2026-10-25 y piezas congeladas.

## 7. Memoria viva (hipótesis y estado)

| Hipótesis | Estado | Por qué / qué la reabriría |
|---|---|---|
| Sentimiento de redes (velocidad, polaridad, consenso) como disparador o confirmación | Descartada | Literatura y pruebas: sigue al precio. Reabrir solo con una fuente con historia y vivo sin cuenta |
| Reddit como variable en vivo | Sin datos | Arctic Shift hoy llega con 4–6 h. Reabrir si vuelve a ~1 min |
| Posicionamiento de la multitud (ratio de cuentas, interés abierto, liquidaciones; P7) | Descartada | AUC 0,500; las liquidaciones copian el pasado |
| «Giro brusco» del posicionamiento como filtro de 1 min | Débil, no se adopta | Misma ganancia con menos operaciones (volatilidad) |
| Titulares: velocidad, polaridad, divergencia | Descartada | 50 %; van detrás del precio |
| «Presencia» de titular como filtro de OKX 5 min | Débil, no se adopta | No sube la ganancia y no generaliza |
| Calendario macro como veto | Descartada (solo aviso) | Toca < 1 % de las operaciones |
| D1 + D2 (tendencia de 60 min y apertura de NY) | **A confirmar (Estudio 72)** | Enero, abril y julio de 2027 |
| D3: volatilidad alta en el contrato de 1 min (P6) | Pendiente, baja | El usuario no tiene BTC a 1 min en su plataforma |
| D4: no operar contra la brecha abierta del CME | Pendiente, baja | 5 de 5 conjuntos peor, pero sin mecanismo claro |
| Reversión tras cascada a 15 min | Ya dentro del modelo | 91–95 % de las señales ya van a la reversión |
| Fin de semana como veto (creencia de la comunidad) | Contradicha | El bot acierta más el fin de semana (H5b, Estudio 70) |

## 8. Trampas evitadas (para la próxima vez)

- **Marcas de tiempo:**
  - Binance «metrics»: `create_time` es el inicio del periodo;
  - Gate: la fila T termina en T+4 y aparece hacia T+4:49;
  - Arctic Shift: el agregado por minuto trae la hora corrida 1–2 h.

  Unirlas sin cuidado mete minutos u horas de futuro.
- **Comparaciones múltiples:** el posicionamiento probó ~410 variantes, las noticias 89 y las comunidades ~110.
  Con tantas pruebas, algunas «salen» por azar. Por eso solo se pre-registró lo que se repite en varios contratos, tiene
  mecanismo y se recalculó de forma independiente.
- **Filtrar no es ganar:** varias pistas suben el acierto pero no la ganancia total (Estudio 48). El criterio es la
  suma de lo que se quita.
- **El cómputo local se pierde al apagar el PC:** las búsquedas largas con agentes murieron dos veces. Lo importante
  queda en git; lo descargado, en el scratchpad, se borra al reiniciar.
