"""Build XLSX bytes in-memory for tests, without touching the filesystem."""

from __future__ import annotations

from io import BytesIO

import pandas as pd


def build_xlsx(sheets: dict[str, pd.DataFrame] | dict[str, list[dict]]) -> bytes:
    """Serialize a ``{sheet_name: DataFrame | list[dict]}`` mapping to XLSX bytes."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, data in sheets.items():
            df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
            df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def default_scenario_sheets() -> dict[str, list[dict]]:
    """A realistic two-scenario fixture used by several tests."""
    return {
        "MS01": [
            {
                "Year": 2023,
                "Year_proj": 2024,
                "Shif": 1,
                "gov_eur_10y_raw": 3.25,
                "dji_index_Var_lag_fut": 0.015,
            },
            {
                "Year": 2023,
                "Year_proj": 2025,
                "Shif": 1,
                "gov_eur_10y_raw": 3.40,
                "dji_index_Var_lag_fut": 0.020,
            },
        ],
        "MS02": [
            {
                "Year": 2023,
                "Year_proj": 2024,
                "Shif": 2,
                "gov_eur_10y_raw": 4.10,
                "dji_index_Var_lag_fut": -0.03,
            },
        ],
    }
