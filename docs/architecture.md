# Arquitectura y estado actual del sistema

Punto de entrada vigente al **17-10-2026**. Describe el árbol local inspeccionado y distingue evidencia guardada de una comprobación remota actual. Esta auditoría no ejecutó modelos, lotes, recuperación, publicación ni despliegue.

## Propósito y alcance

El sistema ayuda a seguir acciones, revisar el deterioro empresarial y seleccionar zonas de compra en retrocesos. Conserva una tesis y un Setup internos, catalizadores, evento y un plan público con **Entry y Washout opcionales**, cada uno con fortaleza. Desde revisión 35 no selecciona resistencia; desde 29 no produce stops numéricos ni target. Esas retiradas son preferencias de alcance, no evidencia de que el riesgo desaparezca.

El modelo debe separar origen verificable del soporte, vigencia compradora actual, fortaleza y selección. Puede dejar ambas compras vacías; no hay cuota de niveles ni ruptura automática por porcentaje, ATR o cierres. Una zona perdida no se conserva como operación de recuperación. Los cruces marginales no demuestran por sí solos un cambio de plan.

La consistencia de datos, fuentes y cálculos es comprobable; publicar correctamente no valida la utilidad financiera de pesos, umbrales y decisiones. El [cuaderno de estrategia](estrategia_compra_bolsa.md) conserva acuerdos y preguntas de producto; no autoriza implementar reglas nuevas.

## Ruta de lectura

| Necesidad | Documento |
|---|---|
| Último estado documentado e incidencias | [Relevo actual](handoff_current.md) |
| Modelos, contratos, prompts y decisiones | [Motor adaptativo](codex_adaptive_analysis.md) |
| Método financiero real y limitaciones | [Descripción vigente](codex_adaptive_analysis.md#metodología-financiera-vigente-y-límites-de-interpretación), [ampliación metodológica](audit_analysis_system_20261017.md#14-ampliación-qué-conservaríamos-y-qué-rediseñaríamos) |
| Comandos y efectos | [Operaciones](operations.md), [lotes](batch_workflow.md), [ticker individual](standard_analyze_workflow.md) |
| Evidencia, hallazgos y límites | [Auditoría independiente](audit_analysis_system_20261017.md) |
| Propuestas y observaciones pendientes | [Backlog canónico](pending_work_current.md) |
| Componentes y consumidores | [Mapa](component_map.md) |
| Instalación, cola, broker y app | [Instalación](new_computer_setup.md), [cola](command_queue.md), [Gateway](ibkr_gateway_automation.md), [Android](android_app.md) |

`AGENTS.md` conserva sus instrucciones operativas. El texto previo de esta arquitectura está [archivado con contexto](history/architecture_before_audit_20261017.md). «Vigente» en un archivo histórico describe la fecha de esa entrada.

## Configuración y evidencia de ejecución

| Capa | Árbol local | Evidencia disponible y límite |
|---|---|---|
| Motor diario | `config/codex_analysis.json`: revisión 39, production_enabled=true | Configuración leída; el lote seleccionado del 16-10 está congelado en 38 |
| Mantenimiento | `gpt-6.1-sol`, medium; nombre heredado Luna | Recibos 16-10 confirman el modelo; Luna no significa otro modelo |
| Full | Mismo modelo, high; petición expresa, ITV o causa crítica | Full 36 del 14-10 y full IBKR 38 del 16-10 registrados |
| Concurrencia | Techo 6 modelos, admisión compartida reduce por saturación; runner máximo 8 | Controles locales de procesos/capacidad; no garantía de capacidad del proveedor |
| ITV | 5 sesiones NYSE para prioridad y seguimiento; solo full reinicia | Fechas Nueva York; no cinco días naturales ni cinco análisis |
| Raw/slim | Orígenes dirigidos 39 | Artefactos origins 39-20261016 con tráfico 100% y captura APP; sin consulta remota 17-10 |
| Mercado | Soportes visibles desde 65; sólido desde 70; extensión 36 | Evidencia guardada solid 65 del 15-10; sin revisión remota actual |
| Fuente local | Runner, servicios y pruebas presentes | HEAD git `7b2a401` del 06-09 y muchos cambios sin commit; git no reconstruye todo octubre |

## Recorrido completo

```mermaid
flowchart LR
    S[Sheets Mercado / Apps Script] --> Q[GCS: configuración y órdenes]
    Q --> W[Worker local / run_batch]
    W --> P[Preparación por ticker]
    R[Raw: mercado / opciones / OHLCV] --> L[Slim]
    L --> P
    N[IBKR: noticias, analistas y eventos] --> P
    A[GCS: CURRENT y ancla full] --> P
    P --> C[Contexto, catálogo y prompts congelados]
    C --> M[Sol 6.1 medium o high]
    M --> V[Validación y reparación limitada]
    V --> D[retain / update / full]
    D --> O[Memoria, JSON, Markdown y HTML]
    O --> G[Publicación GCS y mirror]
    G --> U[Controller / reports / API móvil]
    U --> S
```

| Etapa | Entradas → salidas | Responsabilidad y transformación |
|---|---|---|
| Adquisición técnica | Proveedores de cotización, OHLCV y cadenas Tradier → raw | Indicadores, perfil diario aproximado, reacciones. Muestrea vencimientos y selecciona TOP. Una captura técnica puede escribir su mirror normal: no es una lectura externa sin efectos |
| Slim | Raw → JSON compacto | Reduce candidatos/campos; conserva evidencia, hasta 20 sesiones anteriores al díaUTC de la captura, option_details y observaciones dirigidas. No representa todas las opciones ni todos los soportes posibles |
| Fuentes informativas | IBKR/estado local/Finnhub → noticias, acciones de analistas y earnings | Titulares no equivalen a cuerpo completo; agregado no equivale a revisión nueva de cada firma. Investigación web en la misma llamada habilitada |
| Preparación | Slim, noticias, CURRENT, ancla, propiedad → input/política/instrucciones | Comprueba captura, cobertura y frescura de envoltorios antes de congelar. Solicita identidades tipadas de opciones y AVWAP previos |
| Catálogo/contexto | Input lógico → contexto y schema | Identidades por contenido/alcance, agenda de cambios y antecedentes. Un hecho anterior autenticado no es un origen vivo |
| Modelo | Contexto/instrucciones/schema → JSON y eventos | Juicio financiero y materialidad; mantenimiento revisa y actualiza lo rutinario. No sustitución automática de modelo |
| Validación | Respuesta + fuentes/autoridad → candidato o rechazo | Copia hechos, deriva sumas/categorías, comprueba autoridad, origen, continuidad y aritmética aplicable. No demuestra causalidad, rentabilidad ni toda la verdad de la prosa |
| Reparación | Errores tipados reunidos → una corrección medium | Sin bucle ni full por mero estilo/contrato. Segundo rechazo visible; riesgo e ITV conservan autoridad propia |
| Memoria/ancla | Decisión válida → CURRENT y revisión | Retain conserva finanzas fechadas; update cambia campos autorizados. Full crea ancla. Memoria informativa puede avanzar sin publicar cada investigación |
| Render | semantic_report → MD/HTML y espejos JSON | Desde 15 la estructura precede al texto. Presentación 32/33 selecciona drivers sin borrar historia. Extensión inferior fechada no es stop ni garantía |
| Publicación | Bundle local → latest, snapshots, mirror, current/ancla | Secuencial, con comprobaciones y lock local; no transacción multiobjeto. Véanse huecos reproducidos en auditoría |
| Consumo | Informes/proyecciones + cotizaciones → Sheet/reportes/móvil | Controller filtra desde 65 y colorea; reports sirve formatos; móvil proyecta lectura. Fallo adaptativo visible en lote/logs, no necesariamente en cada lector del último informe |

## Componentes mantenidos

Los módulos sin prefijo pertenecen a `src/local_runner/`.

| Ruta | Responsabilidad |
|---|---|
| `run_batch.py` | Tres fases concurrentes, checkpoint, reintentos y resumen |
| `adaptive_stage.py` | Preparar, analizar y publicar; flujo individual adaptativo |
| `adaptive_policy.py`, `adaptive_maintenance.py` | ITV, rutas, autoridad y mantenimiento |
| `adaptive_codex.py`, `adaptive_budget.py`, `adaptive_capacity.py`, `codex_call_evidence.py` | Invocación, admisión, presupuesto/recibos, evidencia y tiempos |
| `semantic_report.py`, `semantic_sources.py`, `semantic_binding.py` | Contrato, fuentes e integridad durante validación |
| `volume_arithmetic.py`, `volume_rubric.py`, `reaction_comparison.py` | Cálculos, herencia, dirección y metodología versionada |
| `adaptive_current.py`, `analysis_state.py`, `review_memory.py` | CURRENT, ancla y memoria |
| `reader_report.py`, `catalyst_editorial.py`, `support_validity.py` | Presentación y metadatos visuales |
| `gcp_functions/support_resistances_raw/`, `support_resistances_slim/` | Fuentes técnicas mantenidas; `incoming_from_gcp/` es histórico |
| `gcp_services/stock_controller/` | Mercado, cotizaciones, layout, cartera y sincronización |
| `gcp_functions/reports_reader/`, servicios móviles | Lectores de informes y API móvil; rutas concretas en [Android](android_app.md) |
| `apps_script/` | Interfaz, cola y espejos en Sheets; no modelos ni IBKR |
| `android/` | Cliente Growth, sin autoridad financiera sobre el análisis |

El árbol local no prueba el contenido de la imagen desplegada. Los parches cloud recientes partieron de imágenes activas concretas y conservaron runtime. No confundir ese artefacto con el árbol acumulado sin commit.

## Estado, fuentes y fechas

- Trabajo adaptativo: `logs/batch/<fecha>/<hora>/adaptive/<TICKER>/`; individuales: `logs/adaptive_individual/`. Contienen input, política, instrucciones, schemas, responses, receipts, eventos y review/failure.
- `output/<TICKER>/latest.*` es copia local de trabajo/resultado; no sustituye el estado publicado ni el original congelado del lote.
- GCS almacena `<TICKER>/latest.{md,json,html}`, snapshots/historial y estado de ancla/CURRENT. Las URIs exactas las construyen `analysis_state.py` y `adaptive_current.py`; el mirror de consumidores es otra ubicación.
- `generated_at` fecha finanzas; `reviewed_at` puede avanzar sin full; ITV se calcula desde `generated_at` del ancla full; `last_full_report_at` refleja esa época y recovery conserva la ITV original autenticada. `as_of` técnico es hora de captura, no fecha de cada dato.
- Recibos congelados mantienen revisión, prompt, schema y política. Un input 39 no convierte un recibo 38 en 39; una corrección del validador no autoriza editar originales.
- Propiedad procede del registro de Mercado u override explícito; desconocido no equivale a owned=false.

## Límites abiertos

La [auditoría](audit_analysis_system_20261017.md) demuestra problemas en volumen intradía rotulado completo, unidades de expected move, agregados de opciones condicionados por gamma y timeout IBKR convertido en vacío válido. Reproduce además huecos en durabilidad de respuestas/bundles, frescura al reanudar y geometría entre compras. Distingue estos defectos de los riesgos de publicación parcial y visibilidad del último intento.

La ampliación metodológica reconstruye también límites de selección de candidatos, reacciones sin recorrido adverso completo, opciones sin inventario dealer, pesos no calibrados y contexto de mercado/eventos parcialmente integrado. Hay oportunidades de simplificación y mejor representación antes de añadir señales. Los datos publicados y los ejemplos ex ante no prueban ventaja predictiva; el plan de evaluación está propuesto, sin ejecutar.

«Validado» significa que pasó los controles implementados. No demuestra que todos los supuestos estén comprobados. Las mejoras siguen propuestas en el [backlog](pending_work_current.md): no se han aplicado cambios de código, políticas, modelos, prompts, originales o servicios.
