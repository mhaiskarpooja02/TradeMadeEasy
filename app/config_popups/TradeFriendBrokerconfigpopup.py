import os
import json
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox, ttk

CONFIG_PATH = os.path.join("config", "credentials.json")
INDICATOR_PATH = os.path.join("config", "indicator_helper.json")


class BrokerConfigPopup(tb.Toplevel):
    def __init__(self, parent, config_path=CONFIG_PATH, indicator_path=INDICATOR_PATH):
        super().__init__(parent)
        self.title("⚙️ Configurations")
        self.geometry("700x500")
        self.resizable(True, True)

        self.config_path = config_path
        self.indicator_path = indicator_path

        # Modal behavior
        self.grab_set()
        self.focus_force()

        # Load configs
        self.cfg = self._load_json(config_path)
        self.ind_cfg = self._load_json(indicator_path)

        # --- Notebook (Tabs) ---
        nb = tb.Notebook(self)
        nb.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # ============ Broker Config TAB ============
        broker_tab = tb.Frame(nb)
        nb.add(broker_tab, text="Broker Configurations")
        self._build_broker_tab(broker_tab)

        # ============ Indicator Config TAB ============
        ind_tab = tb.Frame(nb)
        nb.add(ind_tab, text="Indicator Configurations")
        self._build_indicator_tab(ind_tab)

        # --- Save Buttons ---
        frame_btn = tb.Frame(self)
        frame_btn.pack(pady=10)
        tb.Button(frame_btn, text="💾 Save All", bootstyle=SUCCESS, command=self.save_all).pack(padx=10)

    # ==========================================================
    # Load Helper
    # ==========================================================
    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {}

    # ==========================================================
    # --- Broker Tab Layout ---
    # ==========================================================
    def _build_broker_tab(self, parent):
        canvas = tb.Canvas(parent)
        scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tb.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # --- Dhan Section ---
        dhan_label = tb.Label(scroll_frame, text="📘 Dhan Configuration", font=("Segoe UI", 10, "bold"))
        dhan_label.pack(anchor="w", padx=10, pady=(10, 5))

        dhan_frame = tb.Frame(scroll_frame)
        dhan_frame.pack(fill=X, padx=10)
        self._add_entry_pair(dhan_frame, "Enable", "dhan", "enabled", "bool")
        self._add_entry_pair(dhan_frame, "Client ID", "dhan", "client_id")
        self._add_entry_pair(dhan_frame, "Access Token", "dhan", "access_token")
        self._add_entry_pair(dhan_frame, "Auto Order", "dhan", "auto_order", "bool")

        tb.Separator(scroll_frame, orient="horizontal").pack(fill=X, pady=10, padx=10)

        # --- Angel Section ---
        angel_label = tb.Label(scroll_frame, text="📗 AngelOne Configuration", font=("Segoe UI", 10, "bold"))
        angel_label.pack(anchor="w", padx=10, pady=(10, 5))

        angel_frame = tb.Frame(scroll_frame)
        angel_frame.pack(fill=X, padx=10)
        self._add_entry_pair(angel_frame, "Enable", "angel", "enabled", "bool")
        self._add_entry_pair(angel_frame, "API Key", "angel", "API_KEY")
        self._add_entry_pair(angel_frame, "Username", "angel", "USERNAME")
        self._add_entry_pair(angel_frame, "PIN", "angel", "PIN")
        self._add_entry_pair(angel_frame, "TOTP QR", "angel", "TOTP_QR")
        self._add_entry_pair(angel_frame, "Auto Order", "angel", "auto_order", "bool")

    # ==========================================================
    # --- Indicator Tab Layout ---
    # ==========================================================
    def _build_indicator_tab(self, parent):
        canvas = tb.Canvas(parent)
        scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tb.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.ind_entries = {}

        # Simple numeric entries
        simple_fields = [
            ("EMA Short", "ema_short"),
            ("EMA Long", "ema_long"),
            ("Candles Above", "candles_above"),
            ("Lookback Days", "lookback_days"),
            ("RSI Period", "rsi_period"),
            ("RSI Overbought", "rsi_overbought"),
            ("RSI Oversold", "rsi_oversold"),
            ("ATR Period", "atr_period"),
            ("ATR Multiplier", "atr_mult"),
            ("Volume Period", "vol_period"),
            ("Volume Multiplier", "full_confirm_vol_mult"),
        ]

        grid = tb.Frame(scroll_frame)
        grid.pack(fill=BOTH, expand=True, padx=15, pady=10)

        for i, (label, key) in enumerate(simple_fields):
            tb.Label(grid, text=label, width=20, anchor="w").grid(row=i, column=0, sticky="w", padx=5, pady=3)
            val = self.ind_cfg.get(key, "")
            var = tb.StringVar(value=val)
            entry = tb.Entry(grid, textvariable=var, width=20)
            entry.grid(row=i, column=1, sticky="ew", padx=5, pady=3)
            self.ind_entries[key] = var

        # Email section
        tb.Separator(scroll_frame, orient="horizontal").pack(fill=X, pady=10, padx=10)
        tb.Label(scroll_frame, text="📨 Email Settings", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)

        email_frame = tb.Frame(scroll_frame)
        email_frame.pack(fill=X, padx=15, pady=5)

        email_settings = self.ind_cfg.get("email_settings", {})
        self.email_enabled = tb.BooleanVar(value=email_settings.get("emailenabeled", False))
        tb.Checkbutton(email_frame, text="Email Enabled", variable=self.email_enabled, bootstyle="round-toggle").pack(anchor="w")

        tb.Label(email_frame, text="Receiver Emails (comma separated):").pack(anchor="w", pady=(10, 2))
        self.receiver_emails = tb.Text(email_frame, height=4, width=60)
        self.receiver_emails.pack(fill=X)
        self.receiver_emails.insert("1.0", ", ".join(email_settings.get("receiver_emails", [])))

        tb.Label(email_frame, text="Subject Template:").pack(anchor="w", pady=(10, 2))
        self.subject_template = tb.Entry(email_frame, width=60)
        self.subject_template.pack(fill=X)
        self.subject_template.insert(0, email_settings.get("subject_template", ""))

        tb.Label(email_frame, text="Body Template:").pack(anchor="w", pady=(10, 2))
        self.body_template = tb.Text(email_frame, height=4, width=60)
        self.body_template.pack(fill=X)
        self.body_template.insert("1.0", email_settings.get("body_template", ""))

    # ==========================================================
    # --- Add Broker Entry Helper (Side-by-Side) ---
    # ==========================================================
    def _add_entry_pair(self, parent, label, broker, key, var_type="str"):
        frame = tb.Frame(parent)
        frame.pack(fill=X, pady=3)

        tb.Label(frame, text=label, width=20, anchor="w").pack(side=LEFT, padx=5)
        if var_type == "str":
            val = self.cfg.get(broker, {}).get(key, "")
            var = tb.StringVar(value=val)
            tb.Entry(frame, textvariable=var, width=40).pack(side=LEFT, fill=X, expand=True)
        elif var_type == "bool":
            val = self.cfg.get(broker, {}).get(key, False)
            var = tb.BooleanVar(value=val)
            tb.Checkbutton(frame, variable=var, bootstyle="round-toggle").pack(side=LEFT, padx=10)
        else:
            raise ValueError("Unsupported type")

        if not hasattr(self, "entries"):
            self.entries = {}
        self.entries[(broker, key)] = var

    # ==========================================================
    # Save Logic
    # ==========================================================
    def save_all(self):
        try:
            # ---- Save Broker Config ----
            for (broker, key), var in self.entries.items():
                self.cfg.setdefault(broker, {})
                self.cfg[broker][key] = var.get()

            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.cfg, f, indent=4)

            # ---- Save Indicator Config ----
            for key, var in self.ind_entries.items():
                self.ind_cfg[key] = self._try_cast(var.get())

            self.ind_cfg["email_settings"] = {
                "emailenabeled": self.email_enabled.get(),
                "receiver_emails": [e.strip() for e in self.receiver_emails.get("1.0", "end").split(",") if e.strip()],
                "subject_template": self.subject_template.get(),
                "body_template": self.body_template.get("1.0", "end").strip()
            }

            with open(self.indicator_path, "w") as f:
                json.dump(self.ind_cfg, f, indent=4)

            messagebox.showinfo("✅ Saved", "All configurations saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configs:\n{e}")

    def _try_cast(self, val):
        try:
            if "." in val:
                return float(val)
            return int(val)
        except:
            return val
