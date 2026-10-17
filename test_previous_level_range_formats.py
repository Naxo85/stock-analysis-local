import pytest

from src.common.analysis_validator import validate_markdown


@pytest.mark.parametrize(
    "previous_range",
    (
        "144.5-145.5",
        "$144.5-$145.5",
        "$144.5-145.5",
        "144,5-145,5",
        "144.5\u2013145.5",
        "144.5 \u2014 145.5",
        "144.5 a 145.5",
    ),
)
def test_accepts_reprioritized_previous_range_formats(previous_range: str) -> None:
    result = validate_markdown(
        f"""
Valoraci\u00f3n: 8.3 / 10
Entrada: $149-$150
Motivo: Se reprioriza: la Entrada anterior exacta de {previous_range} sigue vigente, pero $149-$150 es una zona distinta, mas fuerte y mas cercana.
Entrada ambiciosa: Sin zona verificable
""",
        authoritative_context="entrada_anterior: 144.5-145.5",
    )

    assert result.ok, result.errors
