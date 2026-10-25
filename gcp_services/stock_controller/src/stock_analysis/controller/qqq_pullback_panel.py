"""Bounded C2:H7 presentation. Never resize rows/columns or touch the tables."""
from __future__ import annotations

from datetime import date

from stock_analysis.controller.sheet_layout import _rgb

TITLE = "QQQ · RETROCESO ACTUAL"
BASIS = "Cierres diarios · reinicio tras rebote del 5%"


def _date(value):
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def _price(value):
    return f"{value:.2f}".replace(".", ",") + " $"


def build_pullback_requests(layout: dict, data: dict) -> list[dict]:
    if layout.get("schema_version", 1) < 3 or layout["general_panel"]["column"] != "A":
        return []
    sheet_id = layout["sheet"]["sheet_id"]

    def region(r0, r1, c0=2, c1=8):
        return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1,
                "startColumnIndex": c0, "endColumnIndex": c1}

    ok = data.get("status") == "ok"
    active = ok and data["phase"] == "open"
    tint = "#FFF3DF" if active else "#F3F6F8"
    ink = "#8B560E" if active else "#34424E"
    note = (
        "QQQ: distancia al máximo relativo de cierre del tramo actual.\n"
        "Se alcanza el umbral con una caída de al menos el 5%.\n"
        "El episodio termina al rebotar un 5% desde su mínimo de cierre; "
        "desde ese momento se sigue el máximo del nuevo tramo.\n"
        "La cotización intradía no cambia este indicador.\n"
        "Fuente: Tradier QQQ · " + (
            "último cierre: " + _date(data["close_date"]) if ok else data.get("reason", "Dato no disponible")
        )
    )
    # Retire the former card, within its own bounds only. The value is now one
    # compact line. Source/date/method stay in its note rather than visible rows.
    requests = [{"unmergeCells": {"range": region(1, 7)}},
                {"mergeCells": {"range": region(1, 2, 2, 5), "mergeType": "MERGE_ALL"}}]
    requests.append({"repeatCell": {"range": region(1, 7), "cell": {
        "userEnteredFormat": {"backgroundColorStyle": {"rgbColor": _rgb("#FFFFFF")},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "CLIP",
            "textFormat": {"fontFamily": "Arial", "fontSize": 10, "bold": False,
                "foregroundColorStyle": {"rgbColor": _rgb("#52606D")}}}},
        "fields": "userEnteredValue,note,textFormatRuns,userEnteredFormat.backgroundColorStyle,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy,userEnteredFormat.textFormat"}})

    def cell(row, col, value, *, size=10, bold=False, background="#F7F9FA", color="#52606D", numeric=False):
        fmt = {"textFormat": {"fontFamily": "Arial", "fontSize": size, "bold": bold,
                    "foregroundColorStyle": {"rgbColor": _rgb(color)}},
               "backgroundColorStyle": {"rgbColor": _rgb(background)},
               "numberFormat": {"type": "PERCENT", "pattern": '"Caída QQQ: "0.00%;"Caída QQQ: "-0.00%;"Caída QQQ: "0.00%;"Caída QQQ: "@'}}
        return {"updateCells": {"start": {"sheetId": sheet_id, "rowIndex": row, "columnIndex": col},
            "rows": [{"values": [{"userEnteredValue": {"numberValue" if numeric else "stringValue": value},
                                    "note": note, "userEnteredFormat": fmt}]}],
            "fields": "userEnteredValue,note,userEnteredFormat.textFormat,userEnteredFormat.backgroundColorStyle,userEnteredFormat.numberFormat"}}

    requests.extend([
        cell(1, 2, data["drawdown"] if ok else "N/D", size=10, bold=True, background=tint, color=ink, numeric=ok),
    ])
    return requests
