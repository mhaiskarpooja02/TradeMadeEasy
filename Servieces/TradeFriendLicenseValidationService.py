# Servieces/license_validation_service.py

from datetime import datetime
from Servieces.TradeFriendLicenseGeneratorService import LicenseGeneratorService
from db.LicenseDB import LicenseDB
from utils.logger import get_logger

logger = get_logger(__name__)


class LicenseValidationService:
    """
    Validates and activates license key
    """

    def __init__(self):
        self.repo = LicenseDB()

    def validate_and_activate(self, entered_key: str):
        # --------------------------------------------------
        # Normalize (allow XXXXXXXX-YYYY or XXXXXXXXYYYY)
        # --------------------------------------------------
        key = entered_key.strip().upper().replace("-", "")

        if len(key) != 12:
            raise RuntimeError("Invalid license key format")

        signature = key[:8]
        expiry_hex = key[8:]

        # --------------------------------------------------
        # Load activation context
        # --------------------------------------------------
        license_row = self.repo.get_latest_license()
        if not license_row:
            raise RuntimeError("No activation record found")

        machine_id = license_row["machine_id"]

        # --------------------------------------------------
        # Decode expiry
        # --------------------------------------------------
        try:
            expiry_date = LicenseGeneratorService.hex_to_expiry_date(expiry_hex)
        except ValueError:
            raise RuntimeError("Invalid expiry encoding")

        # --------------------------------------------------
        # Expiry check
        # --------------------------------------------------
        if datetime.now().date() > expiry_date:
            raise RuntimeError("License expired")

        # --------------------------------------------------
        # Signature validation
        # --------------------------------------------------
        expected_signature = LicenseGeneratorService.generate_signature(
            machine_id,
            expiry_hex
        )
        
        logger.info(f"⏸ expected_signature {expected_signature}")
        if signature != expected_signature:
            raise RuntimeError("Invalid license key")

        # --------------------------------------------------
        # Persist success
        # --------------------------------------------------
        self.repo.update_license_key(key)
        self.repo.mark_verified(expiry_date.strftime("%Y-%m-%d"))

        logger.info("✅ License validated and activated")
