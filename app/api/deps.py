from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.lgd import LgdService
from app.services.lgd_forward_looking import LgdForwardLookingAdapter


def db_session() -> Generator[Session, None, None]:
    yield from get_db()


@lru_cache
def _default_adapter() -> LgdForwardLookingAdapter:
    return LgdForwardLookingAdapter()


def get_adapter() -> LgdForwardLookingAdapter:
    return _default_adapter()


def get_lgd_service() -> LgdService:
    return LgdService(adapter=_default_adapter())
