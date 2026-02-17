# Servieces/license_generator_service.py

import hashlib
import base64
from datetime import datetime, date, timedelta

EPOCH = date(1970, 1, 1)


class LicenseGeneratorService:
    """
    PURPOSE:
    - Generate deterministic license keys
    - Used by admin tool + app validation
    """

    _SECRET_SALT = "TRADEMADEEASY@2026"  # keep private

    @classmethod
    def generate_key(cls, machine_id: str, expiry_date: str) -> str:
        """
        Args:
            machine_id  : unique machine identifier
            expiry_date : YYYY-MM-DD

        Returns:
            8 character license key
        """

        cls._validate_inputs(machine_id, expiry_date)

        expiry_days = cls._expiry_to_days(expiry_date)
        expiry_hex = format(expiry_days, "X").rjust(4, "0")

        payload = f"{machine_id}|{expiry_hex}|{cls._SECRET_SALT}"
        digest = hashlib.sha256(payload.encode()).digest()

        signature = base64.b32encode(digest).decode("utf-8")[:4]

        return f"{signature}{expiry_hex}"

    @classmethod
    def generate_signature(cls, machine_id: str, expiry_hex: str) -> str:
        """
        Deterministic 4-char signature
        """
        payload = f"{machine_id}|{expiry_hex}|{cls._SECRET_SALT}"

        digest = hashlib.sha256(payload.encode()).digest()
        return base64.b32encode(digest).decode("utf-8")[:4]
    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    @staticmethod
    def _expiry_to_days(expiry_date: str) -> int:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
        return (expiry - EPOCH).days

    @staticmethod
    def days_to_expiry(days: int) -> date:
        return EPOCH + timedelta(days=days)

    @staticmethod
    def hex_to_expiry_date(expiry_hex: str) -> date:
        """
        Convert expiry hex (4 chars) → expiry date
        """
        try:
            days = int(expiry_hex, 16)
        except ValueError:
            raise ValueError("Invalid expiry hex in license key")

        return EPOCH + timedelta(days=days)

    @staticmethod
    def _validate_inputs(machine_id: str, expiry_date: str):
        if not machine_id or len(machine_id) < 8:
            raise ValueError("Invalid machine_id")

        datetime.strptime(expiry_date, "%Y-%m-%d")
