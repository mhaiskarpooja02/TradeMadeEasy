# app/config_popups/LicenseKeyPopup.py

import os
import sys
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messageTradeFriendBox

from Servieces.TradeFriendLicenseValidationService import LicenseValidationService


class LicenseKeyPopup(tb.Toplevel):
    """
    Activation Step 2:
    - Enter license key
    - Validate
    - Restart app on success
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.validator = LicenseValidationService()

        self.title("Enter License Key")
        self.geometry("420x200")
        self.resizable(False, False)

        tb.Label(
            self,
            text="Enter your license key",
            font=("Arial", 12, "bold")
        ).pack(pady=15)

        self.key_var = tb.StringVar()

        tb.Entry(
            self,
            textvariable=self.key_var,
            width=25,
            font=("Arial", 12)
        ).pack(pady=5)

        tb.Button(
            self,
            text="Activate",
            bootstyle=SUCCESS,
            command=self._submit
        ).pack(pady=15)

        self.grab_set()

    def _submit(self):
        key = self.key_var.get().strip().upper()

        try:
            self.validator.validate_and_activate(key)

            messagebox.showinfo(
                "License Activated",
                "License activated successfully.\n\nThe application will restart."
            )

            self._restart_app()

        except Exception as e:
            messagebox.showerror("Activation Failed", str(e))

    def _restart_app(self):
        python = sys.executable
        os.execv(python, [python] + sys.argv)
