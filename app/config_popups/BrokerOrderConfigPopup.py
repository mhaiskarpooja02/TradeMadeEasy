# app/config_popups/BrokerOrderConfigPopup.py

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo


class BrokerOrderConfigPopup(tb.Toplevel):
    """
    Popup to manage tradefriend_order_config table
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Broker Order Configuration")
        self.geometry("500x550")
        self.resizable(False, False)

        self.repo = TradeFriendOrderConfigRepo()
        self.config_data = self.repo.get()

        self._build_ui()
        self._load_data()

    # ======================================================
    # UI BUILD
    # ======================================================
    def _build_ui(self):

        container = tb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=YES)

        tb.Label(
            container,
            text="Broker Order Configuration",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        # -----------------------------
        # ORDER MODE
        # -----------------------------
        tb.Label(container, text="Order Mode").pack(anchor=W)
        self.order_mode_var = tk.StringVar()
        self.order_mode_combo = tb.Combobox(
            container,
            textvariable=self.order_mode_var,
            values=["PAPER", "LIVE"],
            state="readonly"
        )
        self.order_mode_combo.pack(fill=X, pady=5)

        # -----------------------------
        # Allow Multi Broker
        # -----------------------------
        self.multi_broker_var = tk.IntVar()
        tb.Checkbutton(
            container,
            text="Allow Multiple Brokers",
            variable=self.multi_broker_var
        ).pack(anchor=W, pady=5)

        # -----------------------------
        # DHAN SECTION
        # -----------------------------
        tb.Label(container, text="--- DHAN ---", bootstyle=INFO).pack(anchor=W, pady=10)

        self.dhan_enabled_var = tk.IntVar()
        tb.Checkbutton(
            container,
            text="DHAN Enabled",
            variable=self.dhan_enabled_var
        ).pack(anchor=W)

        self.dhan_auto_var = tk.IntVar()
        tb.Checkbutton(
            container,
            text="DHAN Auto Order",
            variable=self.dhan_auto_var
        ).pack(anchor=W)

        tb.Label(container, text="DHAN Max Quantity").pack(anchor=W)
        self.dhan_qty_var = tk.StringVar()
        tb.Entry(container, textvariable=self.dhan_qty_var).pack(fill=X, pady=5)

        # -----------------------------
        # ANGEL SECTION
        # -----------------------------
        tb.Label(container, text="--- ANGEL ---", bootstyle=INFO).pack(anchor=W, pady=10)

        self.angel_enabled_var = tk.IntVar()
        tb.Checkbutton(
            container,
            text="ANGEL Enabled",
            variable=self.angel_enabled_var
        ).pack(anchor=W)

        self.angel_auto_var = tk.IntVar()
        tb.Checkbutton(
            container,
            text="ANGEL Auto Order",
            variable=self.angel_auto_var
        ).pack(anchor=W)

        tb.Label(container, text="ANGEL Max Quantity").pack(anchor=W)
        self.angel_qty_var = tk.StringVar()
        tb.Entry(container, textvariable=self.angel_qty_var).pack(fill=X, pady=5)

        # -----------------------------
        # SAVE BUTTON
        # -----------------------------
        tb.Button(
            container,
            text="💾 Save Configuration",
            bootstyle=SUCCESS,
            command=self._save_config
        ).pack(pady=20)

    # ======================================================
    # LOAD DATA
    # ======================================================
    def _load_data(self):

        if not self.config_data:
            return

        self.order_mode_var.set(self.config_data.get("order_mode", "PAPER"))
        self.multi_broker_var.set(self.config_data.get("allow_multi_broker", 0))

        self.dhan_enabled_var.set(self.config_data.get("dhan_enabled", 0))
        self.dhan_auto_var.set(self.config_data.get("dhan_auto_order", 0))
        self.dhan_qty_var.set(self.config_data.get("dhan_max_qty") or "")

        self.angel_enabled_var.set(self.config_data.get("angel_enabled", 0))
        self.angel_auto_var.set(self.config_data.get("angel_auto_order", 0))
        self.angel_qty_var.set(self.config_data.get("angel_max_qty") or "")

    # ======================================================
    # SAVE
    # ======================================================
    def _save_config(self):
        try:
            self.repo.update(
                order_mode=self.order_mode_var.get(),
                allow_multi_broker=self.multi_broker_var.get(),
                dhan_enabled=self.dhan_enabled_var.get(),
                dhan_auto_order=self.dhan_auto_var.get(),
                dhan_max_qty=int(self.dhan_qty_var.get()) if self.dhan_qty_var.get() else None,
                angel_enabled=self.angel_enabled_var.get(),
                angel_auto_order=self.angel_auto_var.get(),
                angel_max_qty=int(self.angel_qty_var.get()) if self.angel_qty_var.get() else None,
            )

            messagebox.showinfo("Success", "Configuration updated successfully")
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration:\n{e}")