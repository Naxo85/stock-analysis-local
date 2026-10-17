# Estado: paralelismo de ChatGPT Web

El pool ya esta implementado y `Analizar mercado en local` usa tres perfiles
Firefox independientes, un lock por perfil y grupos de cinco tickers por chat.
El progreso informa workers activos, bloqueados, reintentos y limites.

La guia operativa y el procedimiento para cambios de interfaz estan en
`docs/chatgpt_browser_provider.md`.
