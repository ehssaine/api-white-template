from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LgdComputation(Base):
    """Parent record for a single library call.

    The ``result_json`` column stores the ``lgd_forward_looking`` library's
    output DataFrame (converted to records) verbatim, so the response of
    ``GET /history/{id}`` can be replayed exactly.
    """

    __tablename__ = "lgd_computations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_lgd: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("ix_lgd_computations_method_created_at", "method", "created_at"),
    )
