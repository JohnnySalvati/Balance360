from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, CheckConstraint
from balance360.models.base import Base


class AppConfig(Base):
    __tablename__ = "app_configs"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_config_singleton"),)

    id: Mapped[int] = mapped_column(
        Integer,primary_key=True, default=1
    )

