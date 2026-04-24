"""Parser for the scenario XLSX files uploaded to the compute endpoints.

The expected layout is one sheet per macro-economic scenario, named
``MS01``, ``MS02``, ... Each sheet has the fixed columns ``Year``,
``Year_proj`` and ``Shif`` plus an arbitrary number of macro-variable
columns (e.g. ``gov_eur_10y_raw``, ``dji_index_Var_lag_fut``, ...).

The parser flattens every matching sheet into a single ``list[ExcelInput]``
that the compute endpoints can feed straight into the service layer.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from app.schemas.lgd import ExcelInput, MacroVar

logger = logging.getLogger(__name__)

SHEET_NAME_PATTERN = re.compile(r"^MS\d+$")
_FIXED_COLUMNS = ("Year", "Year_proj", "Shif")


class ExcelParsingError(ValueError):
    """Raised when the uploaded XLSX cannot be parsed as a scenario file."""


def parse_excel_bytes(data: bytes) -> list[ExcelInput]:
    """Parse raw XLSX bytes into a flat list of ``ExcelInput`` records."""
    return parse_excel_file(BytesIO(data))


def parse_excel_file(source: str | BinaryIO) -> list[ExcelInput]:
    """Parse an XLSX file (path or file-like) into ``ExcelInput`` records.

    All sheets whose name matches ``MS\\d+`` are concatenated, in sheet
    order. A sheet missing a fixed column aborts the whole parse — the
    file is structurally invalid and silently dropping rows would hide
    upstream bugs.
    """
    try:
        sheets = pd.read_excel(source, sheet_name=None, engine="openpyxl")
    except Exception as exc:
        raise ExcelParsingError(f"Failed to read XLSX file: {exc}") from exc

    scenario_sheets = sorted(
        (name for name in sheets if SHEET_NAME_PATTERN.match(name)),
        key=_scenario_sort_key,
    )
    if not scenario_sheets:
        raise ExcelParsingError(
            "No scenario sheets found: expected at least one sheet named 'MS01', 'MS02', ..."
        )

    rows: list[ExcelInput] = []
    for sheet_name in scenario_sheets:
        rows.extend(_parse_sheet(sheet_name, sheets[sheet_name]))

    if not rows:
        raise ExcelParsingError("Scenario sheets are present but contain no data rows.")

    logger.info(
        "Parsed %d records across %d scenario sheet(s): %s",
        len(rows),
        len(scenario_sheets),
        scenario_sheets,
    )
    return rows


def _parse_sheet(sheet_name: str, df: pd.DataFrame) -> list[ExcelInput]:
    if df.empty:
        return []

    missing = [c for c in _FIXED_COLUMNS if c not in df.columns]
    if missing:
        raise ExcelParsingError(
            f"Sheet '{sheet_name}' is missing required column(s): {missing}."
        )

    macro_columns = [c for c in df.columns if c not in _FIXED_COLUMNS]
    if not macro_columns:
        raise ExcelParsingError(
            f"Sheet '{sheet_name}' has no macro-variable columns."
        )

    records: list[ExcelInput] = []
    for row_idx, raw in enumerate(df.to_dict(orient="records"), start=2):
        try:
            records.append(_build_record(raw, macro_columns))
        except Exception as exc:
            raise ExcelParsingError(
                f"Invalid data in sheet '{sheet_name}' at row {row_idx}: {exc}"
            ) from exc
    return records


def _build_record(raw: dict, macro_columns: list[str]) -> ExcelInput:
    macro_vars = [
        MacroVar(name=str(col), value=float(raw[col]))
        for col in macro_columns
        if raw.get(col) is not None and not _is_nan(raw[col])
    ]
    if not macro_vars:
        raise ValueError("row has no non-empty macro variables")
    return ExcelInput(
        Year=int(raw["Year"]),
        Year_proj=int(raw["Year_proj"]),
        Shif=int(raw["Shif"]),
        macro_vars=macro_vars,
    )


def _is_nan(value: object) -> bool:
    return isinstance(value, float) and value != value  # NaN != NaN


def _scenario_sort_key(name: str) -> tuple[int, str]:
    """Sort MS01, MS02, ..., MS10 numerically instead of lexicographically."""
    match = re.match(r"^MS(\d+)$", name)
    return (int(match.group(1)) if match else 10**9, name)
