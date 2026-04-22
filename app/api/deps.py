from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.lgd import LgdCalculator


def db_session() -> Generator[Session, None, None]:
    yield from get_db()


@lru_cache
def _default_calculator() -> LgdCalculator:
    return LgdCalculator()


def get_calculator() -> LgdCalculator:
    return _default_calculator()
