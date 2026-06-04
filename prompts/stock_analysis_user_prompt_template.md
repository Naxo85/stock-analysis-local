# Stock Analysis User Prompt Template

Source: incoming_from_gcp/gemini_stock_analyze/main.py, function _generate_analysis().

This is the local Codex equivalent of the original Gemini user_prompt block. Replace {symbol} with the ticker and {slim_json} with the formatted slim JSON.

`	ext
Analiza el ticker {symbol} usando este JSON técnico slim como fuente de verdad principal para técnico/opciones.

Busca información reciente usando Google Search grounding para:
- narrativa vigente,
- earnings,
- catalizadores,
- noticias,
- analistas,
- riesgos,
- sentimiento reciente,
- y próximo evento clave.

JSON técnico slim:

{slim_json}
`
