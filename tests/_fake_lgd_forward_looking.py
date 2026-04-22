"""A deterministic in-process stand-in for the ``lgd_forward_looking`` library.

Installed into ``sys.modules`` by ``conftest.py`` so tests don't depend on
the real package being pip-installed. All three methods round-trip a
``pandas.DataFrame``.
"""

from __future__ import annotations

import pandas as pd

_REQUIRED_COLUMNS = {
    "Year",
    "Year_proj",
    "Shif",
    "gov_eur_10y_raw",
    "dji_index_Var_lag_fut",
}


def _check(df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("input must be a pandas DataFrame")
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")


def compute_lgd_fully_unsecured(df: pd.DataFrame) -> pd.DataFrame:
    _check(df)
    out = df.copy()
    out["lgd"] = 0.6
    out["recovery_rate"] = 1.0 - out["lgd"]
    return out


def compute_lgd_partially_unsecured(df: pd.DataFrame) -> pd.DataFrame:
    _check(df)
    out = df.copy()
    out["lgd"] = 0.3
    out["recovery_rate"] = 1.0 - out["lgd"]
    return out


def compute_torsion_factors(df: pd.DataFrame) -> pd.DataFrame:
    _check(df)
    out = df.copy()
    out["torsion_factor"] = out["Shif"].astype(float) * 0.1
    return out
