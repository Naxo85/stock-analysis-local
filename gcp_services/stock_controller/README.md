# Stock Analysis System

## Documentacion viva

- `docs/market_sheet_audit_spec.md`: significado, calculo, colores y estado de
  auditoria de cada elemento visible de la hoja `Mercado`.
- `docs/benchmark_audit_2026-09-05.md`: adecuacion y limites de cada ETF usado
  como contexto de bloque.
- `config/market_sheet_layout.json`: estado visual declarativo y reconciliable.
- `stock_analysis.controller.reconcile_sheet`: plan y aplicacion explicita de
  tablas, posiciones, bandas de indice, fusiones y paletas declaradas.

Sistema de analisis bursatil, control de cartera y publicacion en Google Sheets.

Este repositorio contiene la reconstruccion limpia del sistema. El repositorio
`stock-analysis-local` permanece operativo como referencia `legacy` durante la
transicion, pero el codigo de este proyecto no importa sus modulos en runtime.

## Estado

Fase de paridad de mercado. Ya contiene contratos, calculos deterministas, el
publicador real de las siete columnas automaticas y el reconciliador estructural
de la hoja. La primera publicacion real se valido el 2026-09-05. El refresco de
`Mercado` se ejecuta en `stock-controller`, invocado por Cloud Scheduler; no
depende de Apps Script ni de que el ordenador local este encendido.

El plan acordado se encuentra en
[`docs/plan_reconstruccion_sistema.md`](docs/plan_reconstruccion_sistema.md).

La fotografia comprobable del sistema actual se mantiene en
[`docs/baseline/observed_state_2026-09-05.md`](docs/baseline/observed_state_2026-09-05.md).

## Componentes previstos

- `controller`: API, jobs, estado y publicacion en Google Sheets.
- `market_worker`: mercado, opciones, metricas y evidencias tecnicas.
- `analysis_agent`: ejecucion local de Codex e IBKR.
- `contracts`: contratos versionados entre componentes.
- `shared`: infraestructura comun estrictamente transversal.

## Desarrollo local

Requiere Python 3.12 o posterior.

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para comprobar que las fuentes observadas de `legacy` no han cambiado:

```powershell
& .\.venv\Scripts\python.exe scripts\verify_legacy_baseline.py
```

## Regla de migracion

Cada capacidad portada desde `legacy` debe:

1. identificar sus entradas, salidas y consumidores reales;
2. quedar cubierta por una prueba de caracterizacion;
3. copiar solo la logica necesaria;
4. revisarse y adaptarse al contrato definitivo;
5. demostrar paridad o documentar expresamente la diferencia.
