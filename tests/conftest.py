from __future__ import annotations

import sys
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from tests import _fake_lgd_forward_looking as _fake

# Install the fake library *before* anything in `app` imports it.
sys.modules.setdefault("lgd_forward_looking", _fake)

from app.api.deps import db_session, get_lgd_service  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.lgd import LgdService  # noqa: E402
from app.services.lgd_forward_looking import LgdForwardLookingAdapter  # noqa: E402


@pytest.fixture()
def fake_library():
    return _fake


@pytest.fixture()
def adapter(fake_library) -> LgdForwardLookingAdapter:
    return LgdForwardLookingAdapter(module=fake_library)


@pytest.fixture()
def service(adapter) -> LgdService:
    return LgdService(adapter=adapter)


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(bind=eng)
        eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@pytest.fixture()
def db(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory, service) -> Generator[TestClient, None, None]:
    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_session] = _override_db
    app.dependency_overrides[get_lgd_service] = lambda: service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_rows() -> list[dict]:
    return [
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
            "Shif": 2,
            "gov_eur_10y_raw": 4.10,
            "dji_index_Var_lag_fut": -0.03,
        },
    ]
