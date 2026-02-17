import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messageTradeFriendBox
from datetime import datetime
import uuid
import platform
import hashlib

from Servieces.TradeFriendLicenseEmailService import LicenseEmailService
from config.TradeFriendSettings import SENDER_EMAIL
from db.LicenseDB import LicenseDB
from utils.logger import get_logger

logger = get_logger(__name__)


class EmailPopup(tb.Toplevel):
    """
    Activation Step 1:
    - Capture user email
    - Read machine id
    - Store in DB
    - Prepare admin activation email
    """

    ADMIN_EMAIL = SENDER_EMAIL   # configurable later

    def __init__(self, parent):
        super().__init__(parent)

        self.repo = LicenseDB()

        self.title("Activate TradeMadeEasy")
        self.geometry("420x200")
        self.resizable(False, False)

        tb.Label(
            self,
            text="Enter your email to activate",
            font=("Arial", 12, "bold")
        ).pack(pady=15)

        self.email_var = tb.StringVar()

        tb.Entry(
            self,
            textvariable=self.email_var,
            width=30,
            font=("Arial", 11)
        ).pack(pady=5)

        tb.Button(
            self,
            text="Continue",
            bootstyle=PRIMARY,
            command=self._submit
        ).pack(pady=15)

        self.grab_set()

    # --------------------------------------------------
    # Submit handler
    # --------------------------------------------------
    def _submit(self):
        email = self.email_var.get().strip().lower()

        if not self._is_valid_email(email):
            messagebox.showerror(
                "Invalid Email",
                "Please enter a valid email address."
            )
            return

        try:
            machine_id = self._get_machine_id()

            # 1️⃣ Store in DB
            self.repo.insert_email(email, machine_id)

            # 2️⃣ Prepare admin email
            email_payload = self._build_admin_email(
                email=email,
                machine_id=machine_id
            )

            # 3️⃣ Log (actual sending will be added later)
            logger.info("📨 Activation email prepared")
            logger.info(f"To      : {self.ADMIN_EMAIL}")
            logger.info(f"Subject : {email_payload['subject']}")
            logger.info(f"Body:\n{email_payload['body']}")



            service = LicenseEmailService()
            
            service.send_activation_request()

            messagebox.showinfo(
                "Activation Started",
                "Activation request sent.\nPlease check your email for the license key."
            )

            self.destroy()

        except Exception as e:
            logger.exception("Activation email step failed")
            messagebox.showerror(
                "Error",
                f"Failed to start activation:\n{e}"
            )

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _is_valid_email(self, email: str) -> bool:
        return "@" in email and "." in email and len(email) >= 6

    def _get_machine_id(self) -> str:
        """
        Stable, privacy-safe machine identifier
        """
        raw = f"{uuid.getnode()}-{platform.system()}-{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _build_admin_email(self, email: str, machine_id: str) -> dict:
        subject = "🔐 TradeMadeEasy – New License Activation Request"

        body = f"""
Hello Admin,

A new activation request has been generated.

------------------------------------
User Email   : {email}
Machine ID   : {machine_id}
Requested On : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
------------------------------------

Please generate a license key using the license utility
and share it with the user.

Regards,
TradeMadeEasy System
"""

        return {
            "subject": subject,
            "body": body
        }
