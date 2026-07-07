from __future__ import annotations

import os

SERVICE_NAME = "CodexQuotaMonitor"


class CredentialStore:
    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self.service_name = service_name

    def set_secret(self, name: str, value: str) -> None:
        if not value:
            return
        try:
            import keyring

            keyring.set_password(self.service_name, name, value)
        except Exception:
            os.environ[f"{self.service_name.upper()}_{name.upper()}"] = value

    def get_secret(self, name: str) -> str | None:
        try:
            import keyring

            value = keyring.get_password(self.service_name, name)
            if value:
                return value
        except Exception:
            pass
        return os.environ.get(f"{self.service_name.upper()}_{name.upper()}")

    def delete_secret(self, name: str) -> None:
        try:
            import keyring

            keyring.delete_password(self.service_name, name)
        except Exception:
            os.environ.pop(f"{self.service_name.upper()}_{name.upper()}", None)
