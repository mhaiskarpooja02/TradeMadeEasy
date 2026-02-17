import os
import ssl
import smtplib
import sqlite3
from datetime import datetime
from email.message import EmailMessage
from config.TradeFriendSettings import (

    EMAIL_Enabled,
    EMAIL_SUBJECT_TEMPLATE,
    EMAIL_BODY_TEMPLATE,
    RECEIVER_EMAILS,
    SENDER_EMAIL,
    SENDER_PASSWORD
)
from db.LicenseDB import LicenseDB
# --------------------------------------------------
# CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_swingalgo.db")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


class LicenseEmailService:
    """
    PURPOSE:
    - Read activation info from DB
    - Build license activation email
    - Send activation request to admin email
    """

    def __init__(self):
      self.repo = LicenseDB()
      self.sender_email = SENDER_EMAIL
      self.sender_password = SENDER_PASSWORD

    
    # --------------------------------------------------
    # EMAIL TEMPLATE
    # --------------------------------------------------
    def _build_activation_email(self, email: str, machine_id: str):
        subject = "TradeMadeEasy – New License Request"

        body = f"""
A new activation request has been generated.

User Email   : {email}
Machine ID   : {machine_id}
Requested At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please generate a license key for this machine.
"""

        return subject, body.strip()

    # --------------------------------------------------
    # SEND EMAIL
    # --------------------------------------------------
    def send_activation_request(self):
        license_row = self.repo.get_latest_license()

        if not license_row:
            raise RuntimeError("No license record found to send activation email")
    
        email=license_row["email"]
        machine_id=license_row["machine_id"],
        
        subject, body = self._build_activation_email(email, machine_id)

        msg = EmailMessage()
        msg["From"] = self.sender_email
        msg["To"] = self.sender_email
        msg["Subject"] = subject
        msg.set_content(body)

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)

        print(f"📧 License activation email sent to admin → {self.sender_email}")
