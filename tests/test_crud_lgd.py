from app.crud import lgd as lgd_crud
from app.schemas.lgd import ExcelInput, LgdMethod
from app.services.lgd import LgdCalculator


def _make_results(n: int = 3):
    calc = LgdCalculator()
    rows = [
        ExcelInput(
            Year=2020 + i,
            Year_proj=2021 + i,
            Shif=i,
            gov_eur_10y_raw=2.0 + i * 0.1,
            dji_index_Var_lag_fut=0.01 * i,
        )
        for i in range(n)
    ]
    return calc.compute_batch(rows, LgdMethod.FULLY_UNSECURED)


def test_create_and_get_computation(db) -> None:
    results = _make_results(3)
    created = lgd_crud.create_computation(
        db, method=LgdMethod.FULLY_UNSECURED, results=results
    )
    assert created.id is not None
    assert created.count == 3
    assert len(created.items) == 3

    fetched = lgd_crud.get_computation(db, created.id)
    assert fetched is not None
    assert fetched.method == LgdMethod.FULLY_UNSECURED.value


def test_get_computation_missing_returns_none(db) -> None:
    assert lgd_crud.get_computation(db, 99999) is None


def test_list_computations_orders_by_created_desc_and_filters(db) -> None:
    a = lgd_crud.create_computation(
        db, method=LgdMethod.FULLY_UNSECURED, results=_make_results(1)
    )
    b = lgd_crud.create_computation(
        db, method=LgdMethod.PARTIALLY_UNSECURED, results=_make_results(2)
    )

    all_items = lgd_crud.list_computations(db)
    assert {c.id for c in all_items} == {a.id, b.id}

    only_partial = lgd_crud.list_computations(db, method=LgdMethod.PARTIALLY_UNSECURED)
    assert [c.id for c in only_partial] == [b.id]


def test_pagination(db) -> None:
    for _ in range(5):
        lgd_crud.create_computation(
            db, method=LgdMethod.FULLY_UNSECURED, results=_make_results(1)
        )
    page = lgd_crud.list_computations(db, limit=2, offset=0)
    assert len(page) == 2
