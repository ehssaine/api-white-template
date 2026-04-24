from __future__ import annotations

import pytest

from app.services.excel_parser import ExcelParsingError, parse_excel_bytes
from tests._xlsx_factory import build_xlsx, default_scenario_sheets


def test_parses_multiple_scenario_sheets_in_numeric_order() -> None:
    data = build_xlsx(default_scenario_sheets())
    rows = parse_excel_bytes(data)

    # 2 rows from MS01, 1 from MS02, in that order.
    assert len(rows) == 3
    assert rows[0].Shif == 1 and rows[0].Year_proj == 2024
    assert rows[1].Shif == 1 and rows[1].Year_proj == 2025
    assert rows[2].Shif == 2

    macro_names = {m.name for m in rows[0].macro_vars}
    assert macro_names == {"gov_eur_10y_raw", "dji_index_Var_lag_fut"}

    macros = {m.name: m.value for m in rows[0].macro_vars}
    assert macros["gov_eur_10y_raw"] == 3.25


def test_ignores_non_scenario_sheets() -> None:
    sheets = default_scenario_sheets()
    sheets["README"] = [{"note": "do not parse me"}]
    sheets["Summary"] = [{"x": 1}]
    rows = parse_excel_bytes(build_xlsx(sheets))
    assert len(rows) == 3  # same as the scenario-only fixture


def test_sorts_ms_sheets_numerically_not_lexicographically() -> None:
    sheets = {
        "MS10": [
            {"Year": 2023, "Year_proj": 2024, "Shif": 10, "macro_a": 1.0},
        ],
        "MS02": [
            {"Year": 2023, "Year_proj": 2024, "Shif": 2, "macro_a": 2.0},
        ],
        "MS01": [
            {"Year": 2023, "Year_proj": 2024, "Shif": 1, "macro_a": 3.0},
        ],
    }
    rows = parse_excel_bytes(build_xlsx(sheets))
    assert [r.Shif for r in rows] == [1, 2, 10]


def test_raises_when_no_scenario_sheet() -> None:
    data = build_xlsx({"Sheet1": [{"x": 1}]})
    with pytest.raises(ExcelParsingError, match="No scenario sheets"):
        parse_excel_bytes(data)


def test_raises_when_required_column_missing() -> None:
    data = build_xlsx(
        {
            "MS01": [
                {"Year": 2023, "Year_proj": 2024, "macro_a": 1.0},  # no Shif
            ]
        }
    )
    with pytest.raises(ExcelParsingError, match="missing required column"):
        parse_excel_bytes(data)


def test_raises_when_sheet_has_no_macro_columns() -> None:
    data = build_xlsx(
        {"MS01": [{"Year": 2023, "Year_proj": 2024, "Shif": 1}]}
    )
    with pytest.raises(ExcelParsingError, match="no macro-variable columns"):
        parse_excel_bytes(data)


def test_raises_when_scenario_sheets_are_empty() -> None:
    import pandas as pd

    data = build_xlsx(
        {"MS01": pd.DataFrame(columns=["Year", "Year_proj", "Shif", "macro_a"])}
    )
    with pytest.raises(ExcelParsingError, match="no data rows"):
        parse_excel_bytes(data)


def test_raises_on_invalid_row_data() -> None:
    data = build_xlsx(
        {
            "MS01": [
                {
                    "Year": "notanumber",
                    "Year_proj": 2024,
                    "Shif": 1,
                    "macro_a": 1.0,
                }
            ]
        }
    )
    with pytest.raises(ExcelParsingError, match="Invalid data in sheet 'MS01'"):
        parse_excel_bytes(data)


def test_raises_on_corrupt_file_bytes() -> None:
    with pytest.raises(ExcelParsingError, match="Failed to read XLSX"):
        parse_excel_bytes(b"not a real xlsx file")


def test_nan_macro_values_are_dropped_from_record() -> None:
    # Row 2 leaves dji_... blank; that column should NOT appear as a MacroVar
    # for that record (rather than be forwarded as NaN, which isn't valid).
    data = build_xlsx(
        {
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
                    "gov_eur_10y_raw": 3.50,
                    "dji_index_Var_lag_fut": None,
                },
            ]
        }
    )
    rows = parse_excel_bytes(data)
    assert {m.name for m in rows[1].macro_vars} == {"gov_eur_10y_raw"}
