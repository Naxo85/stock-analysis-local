# Auditoria de benchmarks de Mercado - 2026-09-05

Esta auditoria evalua si el ETF ayuda a distinguir un movimiento de grupo de un
movimiento idiosincratico. No evalua si el ETF ni sus componentes son una buena
inversion.

## Escala

- `Directo`: el mandato y las posiciones del fondo representan estrechamente el bloque.
- `Util`: representa el factor principal, con exposiciones que no encajan del todo.
- `Proxy`: aporta contexto, pero no es el indice natural del bloque.

## Resultado

| Bloque | ETF | Ajuste | Valoracion | Motivo operativo |
|---|---|---|---|---|
| Cuantica | QTUP | Sustituye a QTUM | Directo | Fondo pure-play; IONQ y QBTS son dos de sus mayores posiciones. Tiene poco historial desde junio de 2026. |
| Memoria | DRAM | Se mantiene | Directo | Mandato especifico de HBM, NAND y DRAM; incluye los principales productores del bloque. |
| Espacio | UFO | Sustituye a XAR | Directo | Incluye RKLB, ASTS y SPCX; XAR mezclaba el movimiento espacial con defensa aeroespacial tradicional. |
| Chips y hardware | SOXX | Se mantiene | Util | Representa bien siete nombres de semiconductores; CLS introduce fabricacion electronica no cubierta de forma pura. |
| Nuclear y red | NLR | Se mantiene | Util | Cubre uranio, reactores, generacion y servicios nucleares; la red/electrificacion de GEV y TLN no queda aislada. |
| Infraestructura IA | AIQ | Provisional | Proxy | Es IA generalista. AIPO solo cubre IREN/CIFR con pesos pequenos y tampoco resuelve el bloque completo. |
| Plataformas IA | IGV | Se mantiene | Util | PLTR y APP encajan en software; RDDT e INOD tienen motores distintos. |
| Fintech y cripto | FINX | Se mantiene | Util | El mandato fintech y la presencia de COIN dan contexto; cripto y brokerage pueden divergir. |
| Equipamiento chips | EUV | Se mantiene | Directo | Su mandato incluye litografia y equipos; cubre ASML, LRCX y AMAT. Tiene poco historial desde abril de 2026. |
| Minerales criticos | REMX | Se mantiene | Util | MP esta entre sus posiciones principales; USAR puede divergir por fase y financiacion. |
| Biotecnologia | XBI | Se mantiene | Directo | Benchmark amplio del subsector biotecnologico de MRNA. |
| Autonomia | DRIV | Se mantiene | Util | Mandato de vehiculos autonomos/electricos y presencia de TSLA; AUR conserva riesgo propio. |
| Salud digital | IHF | Provisional | Proxy | IHF concentra aseguradoras y proveedores. EDOC encaja mejor y contiene HIMS, pero `GOOGLEFINANCE` devuelve `#N/A`. |
| Industriales | XLI | Nuevo | Directo | CAT y RTX estan entre sus principales posiciones; maquinaria y aeroespacial/defensa son dos de sus mayores industrias. |

## Fuentes oficiales principales

- [QTUP, Defiance Pure Quantum ETF](https://www.defianceetfs.com/qtup/)
- [DRAM, Roundhill Memory ETF](https://roundhillinvestments.com/etf/dram/)
- [UFO, Procure Space ETF](https://procureetfs.com/ufo/)
- [SOXX, iShares Semiconductor ETF](https://www.ishares.com/us/products/239705/ishares-pihl-semiconductor-etf)
- [NLR, VanEck Uranium and Nuclear ETF](https://www.vaneck.com/us/en/investments/uranium-nuclear-energy-etf-nlr/)
- [AIQ, Global X Artificial Intelligence and Technology ETF](https://www.globalxetfs.com/funds/AIQ)
- [IGV, iShares Expanded Tech-Software Sector ETF](https://www.ishares.com/us/products/239771/ishares-north-american-tech-software-etf)
- [FINX, Global X FinTech ETF](https://www.globalxetfs.com/funds/finx)
- [EUV, Corgi Lithography and Semiconductor Photonics ETF](https://corgiinvest.com/euv)
- [REMX, VanEck Rare Earth and Strategic Metals ETF](https://www.vaneck.com/us/en/investments/rare-earth-strategic-metals-etf-remx)
- [XBI, State Street SPDR S&P Biotech ETF](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-biotech-etf-xbi)
- [DRIV, Global X Autonomous and Electric Vehicles ETF](https://www.globalxetfs.com/funds/driv)
- [IHF, iShares U.S. Healthcare Providers ETF](https://www.ishares.com/us/products/239510/ishares-us-healthcare-providers-etf)
- [XLI, State Street Industrial Select Sector SPDR ETF](https://www.ssga.com/us/en/individual/etfs/state-street-industrial-select-sector-spdr-etf-xli)

La adecuacion se revisara cuando cambie el universo o el mandato/posiciones de
un ETF. Un benchmark `Proxy` no se usa para decidir una entrada; solo aporta
contexto relativo.
