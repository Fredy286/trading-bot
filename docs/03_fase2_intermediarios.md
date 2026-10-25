# Fase 2 — Comparativa de intermediarios para una eventual ejecución automática

> **Estado:** documento de investigación. La Fase 2 **no está habilitada**: solo se considerará si
> alguna configuración alcanza el estado `VALIDADO` (desarrollo + periodo bloqueado + observación en
> vivo sin dinero) y usted otorga una autorización expresa y específica (`execution/guard.py`).
> No se abrió ninguna cuenta ni se probó ninguna integración con intermediarios.

## 1. Marco regulatorio en Colombia (resumen, no es asesoría legal)

- La SFC indica que las actividades de trading, forex o mercado de valores del exterior **no pueden
  promocionarse en Colombia sin su autorización**, y que no hay plataformas autorizadas para promover
  forex ([SFC](https://www.facebook.com/superintendencia.financiera/posts/las-actividades-de-trading-forex-o-mercado-de-valores-del-exterior-no-pueden-pro/1513155767510374/);
  [Ámbito Jurídico](https://www.ambitojuridico.com/noticias/mercantil/financiero-cambiario-y-seguros/ofrecimiento-de-forex-por-personas-no-0)).
- Según análisis publicados, ninguna norma prohíbe que una persona natural contrate **por iniciativa
  propia** con una firma extranjera; lo que requiere autorización es la promoción en el país
  ([Rankia](https://www.rankia.co/blog/trading-desde-cero/7409499-legal-operar-cfds-brokers-extranjeros)).
  Implicación práctica: si algo sale mal con un intermediario del exterior, **la SFC no lo supervisa**.
- La vía supervisada localmente para exposición al dólar son los derivados sobre la TRM de la Bolsa de
  Valores de Colombia, vía comisionistas de bolsa (contratos grandes, liquidación diaria)
  ([Valores Bancolombia — futuros](https://valores.bancolombia.com/productos-servicios/futuros)). No sirven
  para horizontes de minutos.
- En la Unión Europea la ESMA **prohibió** vender opciones binarias a minoristas desde 2018
  ([ESMA](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors)).
- Temas tributarios y cambiarios (declaración de activos en el exterior, régimen cambiario del Banco de
  la República) deben consultarse con un contador. No se evaluaron aquí.

## 2. Tabla comparativa

| Intermediario | API oficial documentada | Automatización | Cuenta demo | Contratos relevantes | Datos | Costos / pago | Supervisión | Riesgos principales |
|---|---|---|---|---|---|---|---|---|
| **Deriv** | Sí: WebSocket + REST ([docs](https://developers.deriv.com/docs/), [Python](https://deriv-com.github.io/python-deriv-api/)) | Permitida y documentada (app_id) | Sí, incluida al registrarse | Opciones Rise/Fall en forex (duración mínima reportada **15 min** en pares mayores — [referencia](https://www.quora.com/Does-anyone-use-Deriv-for-option-trading-How-do-I-use-a-1-minute-trading-strategy-in-Deriv-It-shows-the-lowest-duration-is-15-minutes); se debe confirmar con la llamada `contracts_for`); 1 min solo en **índices sintéticos** | Ticks en tiempo real y velas por API | Pago por contrato (consultable con `proposal` antes de comprar) | Entidades en el exterior; **no** SFC | Contraparte es el propio intermediario; los índices sintéticos son generados por un **RNG** y **no son predecibles por diseño** ([Deriv](https://deriv.com/markets/derived-indices/synthetic-indices)) |
| **IQ Option** | **No** (solo librerías no oficiales, «ONLY FOR STUDY» — [GitHub](https://github.com/iqoptionapi/iqoptionapi)) | Riesgo de violar términos y de bloqueo de cuenta | Sí | Binarias/digitales desde 1 min | Solo en plataforma | Pago variable por activo y hora | No SFC | Robo de credenciales con «robots» de terceros; contraparte |
| **Quotex / Pocket Option / Olymp Trade / Binomo** | **No** | Solo raspando la web (frágil, contra términos) | Sí | Binarias desde segundos/1 min | Solo en plataforma, feed propio | Pagos anunciados «hasta 90–98 %», fluctuantes ([comparativa](https://tradersunion.com/brokers/forex/view/pocket-option/pocket-option-vs-quotex/)) | No SFC | Feed propio no auditable, conflicto de interés, retiros |
| **Interactive Brokers** | Sí: TWS/IB Gateway y Web API ([IBKR API](https://www.interactivebrokers.com/en/trading/ib-api.php)) | Permitida | Sí (cuenta de papel) | Forex al contado (IDEALPRO), futuros, acciones; **no** binarias de pago fijo | Tiempo real en forex sin cuenta fondeada ([nota](https://supa.is/article/interactive-brokers-paper-trading-how-to-set-up-switch-live-demo-2026)) | 0,20 pb del valor, **mínimo USD 2 por orden** ([ForexBrokers](https://www.forexbrokers.com/reviews/interactive-brokers)) → en montos pequeños el mínimo domina | Reguladores de EE. UU./UE; acepta residentes en Colombia ([lista de países](https://www.interactivebrokers.com/en/accounts/open-account-country-list.php)) | Complejidad; comisión mínima alta para montos pequeños |
| **OANDA** | Sí: REST v20 ([docs](https://developer.oanda.com/rest-live-v20/introduction/)) | Permitida (token personal) | Sí (práctica) | Forex/CFD | Precios bid/ask y velas por API | Spread (+ comisión según cuenta) | Según división; **disponibilidad para Colombia sin confirmar** | Verificar si abre cuentas a residentes en Colombia |
| **Brókeres MetaTrader 5** | Paquete oficial `MetaTrader5` para Python (**solo Windows**) ([MQL5](https://www.mql5.com/en/docs/python_metatrader5)) | Permitida por la plataforma; depende del bróker | Sí | Forex/CFD | Terminal MT5 | Spread + comisión según bróker | Variable por bróker | Elegir bróker con regulación sólida; CFD apalancados |
| **Derivados TRM (BVC) vía comisionista** | Normalmente sin API minorista | Manual | No | Futuros USD/COP | Mercado local | Comisiones del comisionista | **Sí, SFC** | Contratos grandes; horizonte de días |

### 2.1 Verificación directa con la API de Deriv (2026-10-03)

Consulta pública de solo lectura (sin cuenta ni token) a la API de opciones nueva
(`wss://api.derivws.com/trading/v1/options/ws/public`, llamadas `active_symbols` y `contracts_for`; la
dirección antigua `ws.derivws.com/websockets/v3` respondió HTTP 520):

| Instrumento | Opciones «sube/baja» (CALL/PUT) | Duración mínima intradía |
|---|---|---|
| BTC/USD (`cryBTCUSD`) | **No**: solo multiplicadores (MULTUP/MULTDOWN, sin vencimiento) | — |
| EUR/USD, USD/JPY | Sí | **15 min** |
| Oro (XAU/USD) | Sí | **5 min** |

Consecuencia: la única configuración con ventaja estadística (BTC/USDT a 1 minuto) **no tiene ningún
intermediario con API oficial** donde operarse como opción de 1 minuto. Las plataformas que sí ofrecen
BTC a 1 minuto (IQ Option, Quotex, Pocket Option, Olymp Trade, Binomo) no tienen API oficial, liquidan con
su propio feed y no las supervisa la SFC. En divisas y oro, las duraciones de Deriv (5–15 min) ya se
estudiaron: **sin señal** a 5 y 15 minutos.

**Prueba con cuenta demo, mientras dura la observación:** solo puede ser manual y no cuenta para el
veredicto (Aclaración 2, punto 9). Si el usuario sigue a mano alertas «EXPERIMENTAL — NO OPERAR» en
una demo, conviene anotar para cada una: hora, dirección, precio de entrada y de cierre **de la
plataforma**, pago ofrecido y resultado. Así se puede comparar después el feed de la plataforma con el
de Binance (la limitación declarada en la sección 6 del informe).

### 2.2 Revisión del 2026-10-25: ¿dónde entrar en 1–2 segundos de forma automática y legal?

**Motivo:** la ventaja de BTC a 1 minuto, con y sin el bloque de 1 s del Estudio 15, se concentra en los
**primeros 1–2 segundos** después del cierre de la vela:
- referencia: 56,0 % a +1 s y 54,0 % a +10 s;
- con el bloque de 1 s: 57,3 % a +1 s y 54,1 % a +10 s.

Para usarla hace falta automatizar la entrada.

**Primer filtro, el tipo de contrato.** En las operaciones de la política B (desarrollo del Estudio 15), el
movimiento medio **a favor** en 60 s es **+0,47 pb** a +1 s; en el 1 % de mayor confianza, +0,70 pb. El
movimiento absoluto medio es de 2,8 pb.
- Una comisión de 4–10 pb hace imposible ganar comprando o vendiendo el activo: el costo es 10–20 veces
  la ventaja.
- **Solo un contrato de pago fijo** (sube/baja) convierte acertar la dirección en ganancia, porque paga
  igual sin importar el tamaño del movimiento.

| Opción | ¿Pago fijo a 1 min en BTC? | API oficial y demo | Legal desde Colombia | Veredicto |
|---|---|---|---|---|
| Binance USDⓈ-M Futures | No (lineal) | Sí: API oficial y red de pruebas | Uso por iniciativa propia; sin supervisión de la SFC | **No sirve:** comisión 0,02 % + 0,02 % (dando liquidez) a 0,05 % + 0,05 % (tomándola) = 4–10 pb frente a +0,47 pb de ventaja |
| **Deriv**: multiplicadores de BTC/ETH | No (lineal apalancado) | Sí (API WebSocket; consultada hoy) | Igual que arriba | **No sirve:** comisión consultada con `proposal` = 0,82 USD por 10 USD con multiplicador 100 = **8,2 pb** de lo expuesto |
| **Deriv**: Rise/Fall | **No para cripto**: verificado hoy, BTC y ETH solo tienen MULTUP/MULTDOWN; Rise/Fall en divisas (15 min) y oro (5 min) | Sí | Igual | Sin señal a esas duraciones (Fase 1B) |
| Polymarket: «Bitcoin Up or Down» de 5 y 15 min | Pago fijo, pero a **5 o 15 min**, no a 1 | Sí (API CLOB oficial) | **No recomendable:** Coljuegos ordenó bloquearla en Colombia (sept. 2025) por considerarla juego; no está en la lista de bloqueo propia de Polymarket | No sirve: nuestra ventaja es de 1 min (a 5–15 min no hay señal); comisión del tomador de ~2 % cerca de 50/50; problema legal |
| Kalshi, Nadex, Crypto.com NA | Contratos de eventos | Sí | **Solo residentes en EE. UU.** | No aplica |
| IQ Option, Quotex, Pocket Option, Olymp Trade, Binomo | **Sí**, desde 1 min | **No hay API oficial** | Del exterior, sin supervisión de la SFC | Automatizar exige herramientas no oficiales: viola términos y expone credenciales. **Solo manual** |

**Conclusión (2026-10-25):** hoy **no existe** una vía legal, con API oficial y accesible desde Colombia,
para automatizar un contrato de pago fijo de 1 minuto sobre BTC. Quedan tres caminos:
1. **Anticipar la señal** para que el clic manual caiga justo al cierre. En vez de avisar después del
   cierre, el bot avisaría unos segundos **antes** (p. ej., en el segundo 50–55) con la información
   disponible hasta ese momento. Así la latencia humana se convierte en anticipación. Es una hipótesis
   nueva que debe pre-registrarse y validarse con las velas de 1 s (propuesta en docs/08).
2. **Ejecución manual lo más rápida posible** en la demo de una plataforma de 1 minuto. Hay que medir el
   tiempo real de clic y comprobar el precio, el empate y el pago (Estudio 5).
3. **Vigilar nuevos productos:** la investigación diaria (docs/09) debe revisar si Deriv, Binance u otro
   intermediario regulado lanza contratos de pago fijo cortos sobre cripto con API.

Fuentes: comisiones de Binance Futures (https://www.binance.com/es/support/articles/360033544231 ;
https://www.finder.com/binance-futures-fees); API de Deriv, consulta pública `active_symbols`,
`contracts_for` y `proposal` del 2026-10-25 en `wss://api.derivws.com/trading/v1/options/ws/public`;
Polymarket, comisiones (https://unchainedcrypto.com/polymarket-introduces-taker-fees-in-15-minute-markets/ ;
https://bitquery.io/investigations/polymarket-five-minute-casino) y bloqueo en Colombia
(https://docs.polymarket.com/developers/CLOB/geoblock ; https://startpolymarket.com/countries/colombia/).

## 3. Recomendación condicionada

1. **Hoy no hay base para ejecutar automáticamente.** Primero debe existir una configuración
   `VALIDADO`. Si el estudio concluye «sin señal», la Fase 2 no procede.
2. Si una configuración de **opciones de pago fijo a ≥ 15 min en forex** llegara a validarse, el
   único intermediario de la tabla con API oficial para ese tipo de contrato es **Deriv** (cuenta
   demo primero). Hay que medir con su propio feed (el contrato se liquida con sus precios) y
   consultar el pago real con `proposal` antes de cada alerta.
3. Si la ventaja validada fuera en **contado a horizontes largos**, la opción más sólida por
   regulación y API es **Interactive Brokers** (cuenta de papel primero); ojo con la comisión mínima.
4. **Descartadas para automatización:** plataformas sin API oficial (IQ Option, Quotex, Pocket Option,
   Olymp Trade, Binomo). Automatizarlas exige herramientas no oficiales, expone credenciales y puede
   violar sus términos.
5. **Índices sintéticos de Deriv:** descartados para predicción; son aleatorios por construcción.

## 4. Controles de la Fase 2 ya implementados

- `execution/guard.py`: el dinero real está bloqueado salvo variable de entorno explícita, archivo de
  autorización con frase de consentimiento exacta, límites de monto y pérdida diaria, fecha de
  caducidad y modelo `VALIDADO`. Probado en `tests/test_alerts_system.py`.
- **No existe ningún adaptador de envío de órdenes reales** en el código. Es intencional.
- `execution/paper.py`: cuenta simulada para la observación en vivo.

## 5. Qué se necesita de usted para avanzar (cuando corresponda)

- Decidir el tipo de contrato que quiere evaluar (binaria ≥ 15 min vs. contado).
- Abrir **solo cuenta demo** en el intermediario elegido y crear el `app_id`/token.
- Guardar las credenciales en el archivo `.env` de su PC (nunca en el código ni en GitHub).
