"""LGD (Loss Given Default) computation service.

The LGD is modelled as:

    logit(LGD) = b0 + b_gov * gov_eur_10y_raw
                    + b_dji * dji_index_Var_lag_fut
                    + b_shift * Shif

so that the output is guaranteed to lie in (0, 1). For the partially
unsecured exposure, a collateral share is netted against a fixed
haircut:

    LGD_partial = (1 - c) * LGD_unsecured + c * haircut

All coefficients are externalised through ``Settings`` so they can be
recalibrated without a code change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.lgd import ExcelInput, LgdItemResult, LgdMethod


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclass(frozen=True)
class LgdCoefficients:
    intercept: float
    beta_gov_10y: float
    beta_dji_var: float
    beta_shift: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "LgdCoefficients":
        return cls(
            intercept=settings.lgd_unsecured_intercept,
            beta_gov_10y=settings.lgd_unsecured_beta_gov_10y,
            beta_dji_var=settings.lgd_unsecured_beta_dji_var,
            beta_shift=settings.lgd_unsecured_beta_shift,
        )


class LgdCalculator:
    """Deterministic, side-effect-free LGD calculator."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._coeffs = LgdCoefficients.from_settings(self._settings)

    def compute_fully_unsecured(self, row: ExcelInput) -> LgdItemResult:
        lgd = self._unsecured_lgd(row)
        return self._build_result(row, lgd)

    def compute_partially_unsecured(self, row: ExcelInput) -> LgdItemResult:
        collateral_ratio = _clamp_unit(self._settings.lgd_partial_collateral_ratio)
        haircut = _clamp_unit(self._settings.lgd_partial_collateral_haircut)

        unsecured = self._unsecured_lgd(row)
        lgd = (1.0 - collateral_ratio) * unsecured + collateral_ratio * haircut
        return self._build_result(row, _clamp_unit(lgd))

    def compute_batch(
        self, rows: list[ExcelInput], method: LgdMethod
    ) -> list[LgdItemResult]:
        if method is LgdMethod.FULLY_UNSECURED:
            return [self.compute_fully_unsecured(r) for r in rows]
        if method is LgdMethod.PARTIALLY_UNSECURED:
            return [self.compute_partially_unsecured(r) for r in rows]
        raise ValueError(f"Unsupported LGD method: {method}")

    def _unsecured_lgd(self, row: ExcelInput) -> float:
        c = self._coeffs
        linear = (
            c.intercept
            + c.beta_gov_10y * row.gov_eur_10y_raw
            + c.beta_dji_var * row.dji_index_Var_lag_fut
            + c.beta_shift * row.Shif
        )
        return _clamp_unit(_sigmoid(linear))

    @staticmethod
    def _build_result(row: ExcelInput, lgd: float) -> LgdItemResult:
        return LgdItemResult(
            Year=row.Year,
            Year_proj=row.Year_proj,
            Shif=row.Shif,
            gov_eur_10y_raw=row.gov_eur_10y_raw,
            dji_index_Var_lag_fut=row.dji_index_Var_lag_fut,
            lgd=lgd,
            recovery_rate=1.0 - lgd,
        )


def average_lgd(results: list[LgdItemResult]) -> float:
    if not results:
        return 0.0
    return sum(r.lgd for r in results) / len(results)
