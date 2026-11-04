"""Login accounts and the dossier-archive registry. Not the chart of accounts."""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Owned, utc_now


class AppAccount(Base):
    """One Neon Auth user. The migration inserts an unclaimed first row."""

    __tablename__ = "app_account"
    __table_args__ = (
        UniqueConstraint("subject"),
        UniqueConstraint("email"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DossierArchive(Owned, Base):
    """Filename of a dossier zip that belongs to one account."""

    __tablename__ = "dossier_archive"
    __table_args__ = (UniqueConstraint("filename"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
