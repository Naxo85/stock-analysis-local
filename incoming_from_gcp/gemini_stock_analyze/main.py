import os
import json
import logging
import requests
import functions_framework

from datetime import datetime, timezone
from flask import jsonify

from google import genai
from google.genai import types

from google.cloud import storage


logging.basicConfig(level=logging.INFO)

SLIM_BASE_URL = os.environ.get(
    "SLIM_BASE_URL",
    "https://support-resistances-slim-714254943648.europe-southwest1.run.app"
)

GCS_BUCKET = os.environ.get(
    "GCS_BUCKET",
    "stock-analysis-reports-naxo85"
)

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-2.5-pro"
)

REQUEST_TIMEOUT = int(
    os.environ.get("REQUEST_TIMEOUT", "45")
)

VERTEX_PROJECT = os.environ.get(
    "VERTEX_PROJECT",
    "recipe-generator-429817"
)

VERTEX_LOCATION = os.environ.get(
    "VERTEX_LOCATION",
    "us-central1"
)

client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT,
    location=VERTEX_LOCATION
)

storage_client = storage.Client()


SYSTEM_PROMPT = r"""
Siempre recibirás un JSON técnico con formato definido. Tómalo como fuente de verdad principal para precio, as_of, soportes/resistencias, ATR, RSI, medias, volumen, gamma regime, call/put walls, OI/PCR, max pain, expected move y demás campos técnicos/opciones.

Cómo analizar

Analiza, aunque luego no lo enseñes: narrativa vigente, último earnings y evolución desde entonces, earnings previos si aportan contexto, catalizadores activos, contexto sectorial/macro/tecnológico, técnico y opciones.

Técnico y opciones deciden compra, invalidación y venta, pero no se muestran enteros.

Chequeo obligatorio

Antes de cerrar, identifica qué empuja la tesis de fondo y qué empuja el precio ahora. No asumas que coinciden.

Revisa narrativas competitivas, short sellers, downgrades/resets, shocks regulatorios, sentimiento/flujo y noticias de terceros.

Si ha habido un movimiento relevante reciente y la salida no explica por qué se ha movido, el análisis está incompleto.

Cómo puntuar la nota /10

La nota /10 depende sobre todo de la calidad real de la narrativa vigente, descontando falta de validación si el mercado aún no acompaña. Debe reflejar calidad de tesis, momento de entrada y validación en mercado/resultados.

Narrativa viva ≠ narrativa fuerte. “Viva” significa que la tesis no está rota. “Fuerte” exige impulso real, catalizadores potentes, evidencia reciente, capacidad de atraer flujo e historia diferencial.

Distingue entre: narrativa rota/deteriorada, viva pero floja, viva pero correcta, buena y fuerte.

Reglas clave

Una narrativa fuerte no justifica nota alta si hay fricción clara en precio, fuerza relativa o validación bursátil.
Si el ticker sigue débil, bajo niveles relevantes, con mala fuerza relativa o depende del próximo earnings para revalidarse, la nota queda por debajo de lo que sugeriría la narrativa sola.
No uses 6–7 como zona por defecto. Abre hueco entre tickers.
Macro/geopolítica/risk-off casi no penaliza.
Si el riesgo reciente cuestiona negocio, ventaja competitiva, calidad contable o sostenibilidad del growth, la nota debe caer claramente más.

Jerarquía: riesgo al núcleo de tesis > riesgo competitivo/ejecución > compresión de múltiplo / short attack / miedo narrativo > macro/geopolítica/risk-off.

Guía: 8.5–10 excepcional; 7.0–8.4 buena; 5.5–6.9 buen momento/interesante; 5.0–5.4 correcto y vigilable; 4.0–4.9 viva pero floja; <4 débil o deteriorada.

Regla práctica: 5 ya significa buen momento. 6–7 solo para casos claramente atractivos. 8+ solo para casos especiales. No comprimas por defecto entre 6.4 y 6.8.

Modo obligatorio

LONG_ONLY siempre. No propongas cortos ni estructuras bajistas netas. Si el sesgo es flojo/bajista, espera mejor punto o baja convicción. La salida/objetivo siempre debe estar por encima de la entrada.

Regla importante sobre entrada y salida

El usuario solo entra una vez y sale una vez.

La Entrada debe ser la mejor zona principal de compra, no una zona “aceptable”, “de compromiso” o solo cercana al precio actual. Debe combinar soporte real, defensa de opciones, estructura técnica, narrativa viva y asimetría razonable hasta la salida.

La Entrada se fija primero como rango objetivo absoluto usando JSON, narrativa, opciones y estructura. El precio actual no debe desplazarla automáticamente hacia abajo para parecer prudente.

El precio actual solo clasifica la situación: por encima, dentro o por debajo de la Entrada objetiva.

Si una zona era buena entrada con el precio más arriba y luego el precio cae hacia ella o entra en ella sin nueva información negativa, sigue siendo válida o incluso mejor. No bajes la Entrada principal solo porque el precio actual haya bajado.

Solo puedes mover la Entrada principal más abajo si hay razón nueva: pérdida del soporte que la justificaba, deterioro de narrativa, cambio relevante en opciones/gamma/OI, noticia negativa, ruptura técnica clara o cambio de riesgo competitivo, contable o de ejecución.

No confundas “zona donde el precio puede rebotar” con “mejor entrada principal”. Si la mejor asimetría está más abajo, no uses el precio actual como entrada solo porque esté cerca de un pivote/pinning. Pero tampoco bajes la entrada por sistema cuando el precio ya ha llegado a la zona objetiva.

“No perseguir” solo aplica por encima de la Entrada objetiva o cerca de resistencias/salida, no dentro de la zona que era la mejor compra.

Incluye una Entrada ambiciosa: zona más baja para caída fuerte, washout o barrido de mercado/sector. No sustituye a la principal.

La Salida / objetivo principal debe ser un único objetivo, el más fuerte y realista.

Regla sobre stops

Hay dos tipos:
- Stop estructural: si se compra en la Entrada principal. Debe basarse en invalidación real de estructura, soporte o defensa de opciones. Puede quedar lejos.
- Stop de gestión: obligatorio si el usuario ya está dentro, pide stop cercano o la consulta trata una posición abierta. Debe estar más cerca que el estructural. No invalida toda la tesis; protege capital/ganancias. Debe apoyarse en pivote, mínimo relevante, gamma/pinning o soporte corto. Si no existe stop limpio y cercano, dilo.

Si el usuario ya está dentro o pide stop cercano, muestra ambos. Si ya está dentro, el stop de gestión es el principal práctico y el estructural queda como referencia amplia.

Catalizadores

Busca y filtra bien los catalizadores. La narrativa desde el último earnings debe integrarse aquí en bullets cortos.

Cada bullet debe llevar fecha visible, catalizador resumido, una única nota neta con signo y explicación corta.
Formato válido: (+5) a (+10) o (-5) a (-10).
Prohibido usar X, +X, -X, /, rangos, placeholders, TBD o signos dobles. Si el impacto es mixto, asigna una sola nota neta y explícalo debajo.
La fecha debe ser la fuente/noticia más reciente que sustenta ese punto.

Precisión factual: no presentes como “nuevo” una continuidad o relectura. Si el impacto económico no está claro, dilo y baja la nota. Prioriza catalizadores directos.

Cobertura: incluye catalizadores que apoyan la tesis y los que pesan sobre la acción. Si un catalizador negativo, competitivo o de mercado explica el movimiento reciente, debe aparecer aunque la tesis siga viva.

Escala: usa -10 a +10. No muestres catalizadores con |nota| < 5. Si no hay suficientes con |nota| ≥ 5, muestra pocos bullets o ninguno.

Próximo evento clave

No asumas que el próximo earnings es automáticamente el evento clave. Solo debe aparecer si es el principal punto de inflexión. Si hay un evento más relevante, usa ese. Si no hay catalizador dominante único, dilo.

Plantilla de salida

Usa este formato:

{Ticker}: 1 línea de negocio
Precio de referencia: $X
JSON: fresco / no fresco

0) Resumen ejecutivo
Valoración: X / 10
Narrativa actual: 2–3 líneas máximo

1) Narrativa y catalizadores activos
AAAA-MM-DD · Catalizador · (+7)
Explicación corta

2) Próximo evento clave
AAAA-MM-DD · Evento
Explicación corta

3) Plan
Entrada: rango principal absoluto (X% a Y% vs precio actual)
Estado actual: por encima / dentro / por debajo de la zona
Motivo: explicación corta

Entrada ambiciosa: rango inferior (X% a Y% vs precio actual)
Motivo: explicación corta

Stop de gestión: nivel (X% vs precio actual)
Motivo: nivel cercano para proteger capital

Stop estructural: nivel (X% vs precio actual)
Motivo: invalidación real del plan

Salida / objetivo principal: objetivo (X% vs precio actual)
Motivo: primera zona fuerte de oferta / resistencia real

4) Conclusión sencilla
1–2 líneas máximo.

Formato y estilo

Deja línea en blanco entre bloques.
Precio / JSON / Negocio en líneas separadas.
Usa negrita en secciones y niveles clave.
Usa cursiva en motivos.
Catalizadores: bullet de dos líneas.
Plan: cada elemento en bloque separado.
Poco texto. Nada de párrafos largos. Formulaciones secas.

Idea central

La pregunta principal no es “cómo está el gráfico”, sino: qué narrativa sigue viva, qué mueve el precio ahora, cuál es la mejor zona real para comprar una sola vez y qué evento importa de verdad.

Instrucción operativa adicional para API:

Usa Google Search grounding para buscar información reciente necesaria para narrativa, catalizadores, earnings, analistas, riesgos y próximo evento clave.

No cambies el formato ni las reglas anteriores.

Si no encuentras datos recientes suficientes, dilo explícitamente.
""".strip()


@functions_framework.http
def analyze_stock(request):

    try:
        symbol = _get_symbol(request)

        if not symbol:
            return jsonify(
                error="Missing 'symbol'"
            ), 400

        save = _bool_param(
            request,
            "save",
            default=True
        )

        slim = _fetch_slim(symbol)

        analysis_md, grounding = _generate_analysis(
            symbol=symbol,
            slim=slim
        )

        now = datetime.now(timezone.utc)

        result = _build_result(
            symbol=symbol,
            slim=slim,
            analysis_md=analysis_md,
            grounding=grounding,
            now=now
        )

        saved_paths = {}

        if save:
            saved_paths = _save_to_gcs(
                symbol=symbol,
                result=result,
                analysis_md=analysis_md,
                now=now
            )

        return jsonify({
            **result,
            "saved": bool(saved_paths),
            "saved_paths": saved_paths
        }), 200

    except requests.HTTPError as e:

        body = getattr(
            e.response,
            "text",
            None
        )

        logging.exception(
            "slim_endpoint_http_error"
        )

        return jsonify(
            error="slim_endpoint_http_error",
            details=str(e),
            body=body
        ), 502

    except Exception as e:

        logging.exception(
            "internal_error"
        )

        return jsonify(
            error="internal_error",
            details=str(e)
        ), 500


def _get_symbol(request):

    symbol = (
        request.args.get("symbol") or ""
    ).strip().upper()

    if not symbol:

        payload = request.get_json(
            silent=True
        ) or {}

        symbol = (
            payload.get("symbol")
            or ((payload.get("tickers") or [None])[0])
            or ""
        )

        symbol = str(symbol).strip().upper()

    return symbol or None


def _bool_param(
    request,
    name: str,
    default: bool = False
):

    raw = request.args.get(name)

    if raw is None:
        return default

    return str(raw).strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "si",
        "sí"
    )


def _fetch_slim(symbol: str):

    url = SLIM_BASE_URL.rstrip("/")

    r = requests.get(
        url,
        params={
            "symbol": symbol
        },
        timeout=REQUEST_TIMEOUT
    )

    r.raise_for_status()

    return r.json()


def _generate_analysis(
    symbol: str,
    slim: dict
):

    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    user_prompt = (
        f"Analiza el ticker {symbol} usando este JSON técnico slim "
        f"como fuente de verdad principal para técnico/opciones.\n\n"

        f"Busca información reciente usando Google Search grounding para:\n"
        f"- narrativa vigente,\n"
        f"- earnings,\n"
        f"- catalizadores,\n"
        f"- noticias,\n"
        f"- analistas,\n"
        f"- riesgos,\n"
        f"- sentimiento reciente,\n"
        f"- y próximo evento clave.\n\n"

        f"JSON técnico slim:\n\n"

        f"{json.dumps(slim, ensure_ascii=False, indent=2)}"
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[grounding_tool],
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=3500,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=config
    )

    try:
        usage = getattr(response, "usage_metadata", None)
        logging.info("gemini_usage_metadata=%s", usage)
    except Exception:
        logging.exception("usage_metadata_log_failed")

    text = response.text or ""

    grounding = _extract_grounding(
        response
    )

    return text.strip(), grounding


def _extract_grounding(response):

    try:
        candidate = response.candidates[0]

        gm = getattr(
            candidate,
            "grounding_metadata",
            None
        )

        if not gm:
            return {}

        chunks = []

        for ch in getattr(
            gm,
            "grounding_chunks",
            []
        ) or []:

            web = getattr(
                ch,
                "web",
                None
            )

            if web:
                chunks.append({
                    "title": getattr(
                        web,
                        "title",
                        None
                    ),
                    "uri": getattr(
                        web,
                        "uri",
                        None
                    ),
                })

        queries = list(
            getattr(
                gm,
                "web_search_queries",
                []
            ) or []
        )

        return {
            "web_search_queries": queries,
            "sources": chunks
        }

    except Exception:

        logging.exception(
            "grounding_extract_failed"
        )

        return {}


def _build_result(
    symbol: str,
    slim: dict,
    analysis_md: str,
    grounding: dict,
    now: datetime
):

    return {
        "symbol": symbol,
        "generated_at": now.isoformat(),
        "model": GEMINI_MODEL,
        "slim_as_of": slim.get("as_of"),
        "latest_price": slim.get("latest_price"),
        "analysis_markdown": analysis_md,
        "grounding": grounding,
        "slim_snapshot": slim,
    }


def _save_to_gcs(
    symbol: str,
    result: dict,
    analysis_md: str,
    now: datetime
):

    bucket = storage_client.bucket(
        GCS_BUCKET
    )

    date_part = now.strftime(
        "%Y-%m-%d"
    )

    time_part = now.strftime(
        "%H-%M-%S"
    )

    base = (
        f"{symbol}/{date_part}/{time_part}"
    )

    json_payload = json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    )

    paths = {
        "latest_json": f"{symbol}/latest.json",
        "latest_md": f"{symbol}/latest.md",
        "snapshot_json": f"{base}.json",
        "snapshot_md": f"{base}.md",
    }

    _upload_text(
        bucket,
        paths["latest_json"],
        json_payload,
        "application/json"
    )

    _upload_text(
        bucket,
        paths["snapshot_json"],
        json_payload,
        "application/json"
    )

    _upload_text(
        bucket,
        paths["latest_md"],
        analysis_md,
        "text/markdown; charset=utf-8"
    )

    _upload_text(
        bucket,
        paths["snapshot_md"],
        analysis_md,
        "text/markdown; charset=utf-8"
    )

    return paths


def _upload_text(
    bucket,
    path: str,
    content: str,
    content_type: str
):

    blob = bucket.blob(path)

    blob.upload_from_string(
        content,
        content_type=content_type
    )