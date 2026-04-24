"""Adapter over the ``lgd_forward_looking`` library.

The library exposes three methods that all operate on ``pandas.DataFrame``:

* ``compute_lgd_fully_unsecured(df) -> DataFrame``
* ``compute_lgd_partially_unsecured(df) -> DataFrame``
* ``compute_torsion_factors(df) -> DataFrame``

This adapter is a thin boundary so the rest of the codebase does not depend
on the library directly: tests can substitute a fake module, and the import
is deferred until the first call so missing installations surface as a
clean 503 rather than an import-time crash.
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Protocol, runtime_checkable

import pandas as pd

logger = logging.getLogger(__name__)


@runtime_checkable
class LgdForwardLookingModule(Protocol):
    def compute_lgd_fully_unsecured(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def compute_lgd_partially_unsecured(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def compute_torsion_factors(self, df: pd.DataFrame) -> pd.DataFrame: ...


class LgdForwardLookingError(RuntimeError):
    """Raised when the underlying library fails or is misconfigured."""


class LgdForwardLookingAdapter:
    """Thin wrapper enforcing the DataFrame in / DataFrame out contract."""

    _MODULE_NAME = "lgd_forward_looking"

    def __init__(self, module: ModuleType | LgdForwardLookingModule | None = None) -> None:
        self._module = module

    def _resolve(self) -> LgdForwardLookingModule:
        if self._module is None:
            try:
                self._module = importlib.import_module(self._MODULE_NAME)
            except ImportError as exc:  # pragma: no cover - exercised via fake in tests
                raise LgdForwardLookingError(
                    f"Library '{self._MODULE_NAME}' is not installed."
                ) from exc
        return self._module  # type: ignore[return-value]

    def compute_fully_unsecured(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._invoke("compute_lgd_fully_unsecured", df)

    def compute_partially_unsecured(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._invoke("compute_lgd_partially_unsecured", df)

    def compute_torsion_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._invoke("compute_torsion_factors", df)

    def _invoke(self, method_name: str, df: pd.DataFrame) -> pd.DataFrame:
        module = self._resolve()
        method = getattr(module, method_name, None)
        if method is None or not callable(method):
            raise LgdForwardLookingError(
                f"'{self._MODULE_NAME}.{method_name}' is not available."
            )
        try:
            result = method(df)
        except Exception as exc:
            logger.exception("lgd_forward_looking.%s failed", method_name)
            raise LgdForwardLookingError(
                f"'{self._MODULE_NAME}.{method_name}' raised: {exc}"
            ) from exc
        if not isinstance(result, pd.DataFrame):
            raise LgdForwardLookingError(
                f"'{self._MODULE_NAME}.{method_name}' must return a pandas DataFrame, "
                f"got {type(result).__name__}."
            )
        return result
