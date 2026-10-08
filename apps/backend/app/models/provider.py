from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProviderSetting(Base):
    """Runtime provider configuration, persisted so API keys and provider
    selection can be supplied from the UI without touching environment files.

    Resolution order used by the provider registry:
        1. ProviderSetting row (this table)
        2. environment variable / .env via Settings
        3. built-in default
    """

    __tablename__ = "provider_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")