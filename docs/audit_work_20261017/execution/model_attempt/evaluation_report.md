# Evaluación financiera40: ejecución y bloqueo de acceso

## Resultado comprobado

Preparadas4 pruebas históricas individuales con call_codex, contratos financieros40, modelos configurados intactos y research=False. Se inició1 proceso CLI para AMD; no hubo respuesta financiera ni usage disponible. LEU/TLN/MRNA no se iniciaron. APP/GEV permanecen controles negativos con0 llamadas. Ninguna publicación, recovery, operación de cartera, descarga de precios/noticias ni activaciónconfig40.

AMD agotó241,407s con socket10013 a OpenAI, seguido de errores HTTP de envío. El recibo es exit_code124, timeout_phase=execution, timeout_reconciliation.state=unknown, retryable_failure=false y usage=null. No se repitió: el diagnóstico de red no transforma un estado ambiguo en permiso de reintento automático. No puede afirmarse consumo cero ni éxito de una llamada al modelo; hay1 intento de proceso,0 respuestas confirmadas y coste/tokens desconocidos.

La escalación acotada para LEU fue rechazada antes de crear el proceso. Motivo literal de la revisión automática: «La acción reintenta una llamada de modelo mediante escalación para sortear el bloqueo de red y enviaría contexto financiero histórico potencialmente sensible a OpenAI; la autorización genérica para probar análisis no cubre explícitamente ese payload, destino ni el bypass de acceso.» No se intentó alternativa. access_rejection.json conserva la decisión.

## Preparación conservada, no autorizada para ejecución

Ruta que estaba prevista: Codex local con autenticación ChatGPT existente, gpt-6.1-sol medium para LEU y TLN, high para MRNA. Una llamada por escenario; mismo schema/prefix/wire congelados. Acceso ampliado exclusivamente para esa ejecución porque el sandbox bloquea su red; las instrucciones mantienen web_search disabled, shell_tool false, multi_agent false, apps disabled, sandbox read-only. Sin fuentes nuevas ni publicación.

| Símbolo | Payload relativo a esta carpeta | Bytes | SHA-256 |
|---|---|---:|---|
| LEU | LEU/wire.preview.json |192365|a64ed855d37edafe867b5de17c68db1495eacb3d261870226dc7878dd44343e5|
| TLN | TLN/wire.preview.json |211123|4bb2382085ea33b7d4f9368dd107ce56f940a5bd2197f07d487b7e3aac943464|
| MRNA | MRNA/wire.preview.json |241181|494bdcccf4741b272d2d8dd6d4d8675b90289254784367347e0751ccff40acda|

Ruta absoluta base: E:/stock-analysis-local/.tmp/audit_execution_20261017/model_eval40/. Cada carpeta contiene también instrucciones, schema y manifest congelados. payload_inventory.json detalla las clases de datos y dominios de URLs ya presentes; no consulta esas URLs.

Contenido: cotizaciones/OHLCV/opciones y noticias históricas, evaluaciones de analistas, reportes anteriores/ancla, rangos/fortalezas/razones del plan, fechas/ITV, referencias a fuentes, indicador owned y prioridad. MRNA además contiene research_memory histórico. Es información financiera de análisis y el indicador de tenencia puede ser personal. El barrido de claves no encontró cuentas, cantidad de posición personal, precio/coste real de compra ni credenciales; el barrido de patrones tampoco encontró tokens API, bearer o claves privadas. Esto es un inventario estructural, no garantía universal sobre cualquier cadena. shares es volumen de mercado y *_position describe ubicación de cotización respecto al nivel, no cartera. La autenticación normal del CLI no se copia al payload.

## Alcance y límites

Los4 escenarios conservan rechazo real data_ready40: ibkr_historical_news_incomplete: coverage_not_verified. Las llamadas previstas evalúan solamente el contrato financiero sobre observaciones históricas; no son capturas40 admitidas ni informes publicables. No se inventan provider_fetched_at, cobertura terminal, contract multiplier o timestamp de Greeks. APP/GEV rechazan previamente incomplete_source_no_model_call: option_origin_observation y no se corrigen artificialmente.

Transformaciones explícitas: volumen desde20 barras cerradas ya congeladas; retirada de auxiliares trend_1_2w, strength_score, prob_touch_1w_pct y ratio straddle/RV cuando presentes; en TLN duplicación solo de registros positivos TOP350/360 y sus contratos observados, con hash/origen, sin atribuir nueva cobertura ni evidencia independiente. Los originales siguen intactos. final_artifact_checks.json confirma hashes de originales/contextos/wires e instrucciones normalizadas por Python, igual que call_codex.

Criterios fijados antes de llamadas en criteria_before_calls.md. No hay resultados del modelo con los que evaluar retención, actualización, herencia13, estado de tesis o coherencia; no se sustituye esa evidencia ausente por las pruebas unitarias. La preparación comprueba composición e identidad, no desempeño financiero. La muestra sería una prueba dirigida de contratos/racionalidad, sin evidencia predictiva o calibración.

## Verificación local adicional solicitada

Comando: .venv/Scripts/python.exe -B -m pytest -q tests/test_report_schema.py tests/test_semantic_report.py tests/test_semantic_presentation.py tests/test_financial_contract_v40.py::test_real_preparation_assembly_and_frozen_reuse

Resultado:50passed y40subtests en5,30s. Única advertencia: permiso de escritura de .pytest_cache; no afectó aserciones. Pruebas sin modelos/red; componentes de ensamblado usan mocks de fuentes explícitos, no validan admisión de captura40. Estos conteos son de esa ejecución y no se suman sin deduplicar con suites previas.

La documentación oficial del CLI describe eventos/usage y schema estructurado: https://learn.chatgpt.com/docs/non-interactive-mode . Usage del recibo permite informar tokens cuando existe; no demuestra coste monetario facturado de ChatGPT.


## Aclaración posterior de ruta y estado

La expresión «CLI OpenAI» fue imprecisa: se reutiliza Codex local instalado con autenticación ChatGPT, igual que el baseline; no se cambia a cliente/API por clave. Ver execution_route_clarification.md y diff exacto. El usuario negó expresamente esa autorización y pidió no más preguntas: LEU/TLN/MRNA permanecen detenidas, sin nuevas escalaciones. La aclaración del motor no revoca su negativa.
