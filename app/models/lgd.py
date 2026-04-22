from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LgdComputation(Base):
    __tablename__ = "lgd_computations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_lgd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    items: Mapped[list["LgdComputationItem"]] = relationship(
        back_populates="computation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_lgd_computations_method_created_at", "method", "created_at"),
    )


class LgdComputationItem(Base):
    __tablename__ = "lgd_computation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    computation_id: Mapped[int] = mapped_column(
        ForeignKey("lgd_computations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    year_proj: Mapped[int] = mapped_column(Integer, nullable=False)
    shif: Mapped[int] = mapped_column(Integer, nullable=False)
    gov_eur_10y_raw: Mapped[float] = mapped_column(Float, nullable=False)
    dji_index_var_lag_fut: Mapped[float] = mapped_column(Float, nullable=False)

    lgd: Mapped[float] = mapped_column(Float, nullable=False)
    recovery_rate: Mapped[float] = mapped_column(Float, nullable=False)

    computation: Mapped["LgdComputation"] = relationship(back_populates="items")
