from app.crud import lgd as lgd_crud
from app.schemas.lgd import ExcelInput, LgdMethod


def _rows(n: int = 2) -> list[ExcelInput]:
    return [
        ExcelInput(
            Year=2020 + i,
            Year_proj=2021 + i,
            Shif=i,
            gov_eur_10y_raw=2.0 + i * 0.1,
            dji_index_Var_lag_fut=0.01 * i,
        )
        for i in range(n)
    ]


def test_create_with_lgd_column_populates_average(db) -> None:
    results = [{"lgd": 0.5, "recovery_rate": 0.5}, {"lgd": 0.7, "recovery_rate": 0.3}]
    created = lgd_crud.create_computation(
        db,
        method=LgdMethod.FULLY_UNSECURED,
        inputs=_rows(2),
        results=results,
    )
    assert created.id is not None
    assert created.count == 2
    assert created.average_lgd == 0.6
    assert created.result_json == results
    assert len(created.input_json) == 2


def test_create_without_lgd_column_leaves_average_none(db) -> None:
    results = [{"torsion_factor": 0.1}, {"torsion_factor": 0.2}]
    created = lgd_crud.create_computation(
        db,
        method=LgdMethod.TORSION_FACTORS,
        inputs=_rows(2),
        results=results,
    )
    assert created.average_lgd is None


def test_get_and_list(db) -> None:
    a = lgd_crud.create_computation(
        db,
        method=LgdMethod.FULLY_UNSECURED,
        inputs=_rows(1),
        results=[{"lgd": 0.4}],
    )
    b = lgd_crud.create_computation(
        db,
        method=LgdMethod.TORSION_FACTORS,
        inputs=_rows(1),
        results=[{"torsion_factor": 0.1}],
    )

    fetched = lgd_crud.get_computation(db, a.id)
    assert fetched is not None and fetched.id == a.id

    assert lgd_crud.get_computation(db, 99999) is None

    all_items = lgd_crud.list_computations(db)
    assert {c.id for c in all_items} == {a.id, b.id}

    only_torsion = lgd_crud.list_computations(db, method=LgdMethod.TORSION_FACTORS)
    assert [c.id for c in only_torsion] == [b.id]


def test_pagination(db) -> None:
    for _ in range(5):
        lgd_crud.create_computation(
            db,
            method=LgdMethod.FULLY_UNSECURED,
            inputs=_rows(1),
            results=[{"lgd": 0.5}],
        )
    page = lgd_crud.list_computations(db, limit=2, offset=0)
    assert len(page) == 2
