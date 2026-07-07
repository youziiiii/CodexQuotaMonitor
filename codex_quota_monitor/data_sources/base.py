from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from codex_quota_monitor.core.models import UsageSnapshot


class UsageProvider(ABC):
    @abstractmethod
    def fetch(self, now: datetime | None = None) -> UsageSnapshot:
        raise NotImplementedError


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderUnsupportedError(RuntimeError):
    pass
