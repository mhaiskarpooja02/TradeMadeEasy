import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from datetime import datetime

from config.app_config import AppConfig
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

from app.config_popups.TradeFriendBrokerconfigpopup import BrokerConfigPopup
from app.pages.TradeFriendDashboard import TradeFriendDashboard
from app.pages.TradeFriendHome import TradeFriendHome
from app.pages.TradeFriendSettingsPopup import TradeFriendSettingsPopup
from app.config_popups.BrokerOrderConfigPopup import BrokerOrderConfigPopup

from Servieces.TradeFriendSystemHealthService import TradeFriendSystemHealthService
from core.TradeFriendAppEngine import TradeFriendAppEngine


# ==========================================================
# MAIN APPLICATION
# ==========================================================
class TradeMadeEasyApp(tb.Window):

    def __init__(self, health_service: TradeFriendSystemHealthService):
        super().__init__(title="TradeMadeEasy", themename="vapor")
        self.geometry("1200x700")

        # ------------------------------------------------------
        # HEALTH SERVICE
        # ------------------------------------------------------
        self.health_service = health_service
        self.health_service.register_callback(self._on_health_change)

        self.internet_alert_shown = False

        # ------------------------------------------------------
        # SETTINGS INITIALIZATION
        # ------------------------------------------------------
        self.settings_repo = TradeFriendSettingsRepo()
        self.trade_mode = self.settings_repo.get_trade_mode()

        # ------------------------------------------------------
        # HEADER
        # ------------------------------------------------------
        self.header_frame = tb.Frame(self)
        self.header_frame.pack(fill=X)

        tb.Label(
            self.header_frame,
            text="TradeMadeEasy",
            font=("Arial", 18, "bold")
        ).pack(side=LEFT, padx=10, pady=5)

        # 🌐 Internet Status Indicator
        self.internet_label = tb.Label(
            self.header_frame,
            text="🌐 ONLINE",
            bootstyle=SUCCESS
        )
        self.internet_label.pack(side=RIGHT, padx=5)

        # Theme
        self.style.theme_use("vapor")
        self.theme_var = tk.StringVar(value="vapor")

        self.theme_menu = tb.Combobox(
            self.header_frame,
            textvariable=self.theme_var,
            values=self.style.theme_names(),
            width=15
        )
        self.theme_menu.pack(side=RIGHT, padx=10)
        self.theme_menu.bind("<<ComboboxSelected>>", self.change_theme)

        # Trade Mode Button
        self.trade_mode_btn = tb.Button(
            self.header_frame,
            text=f"Mode: {self.trade_mode}",
            bootstyle=self._get_trade_mode_style(),
            command=self.toggle_trade_mode
        )
        self.trade_mode_btn.pack(side=RIGHT, padx=5)

        # ENV Indicator
        self.env_btn = tb.Button(
            self.header_frame,
            text=f"ENV: {AppConfig.ENV}",
            bootstyle=SUCCESS if AppConfig.is_dev() else DANGER,
            command=self.toggle_environment
        )
        self.env_btn.pack(side=RIGHT, padx=5)

        tb.Button(
            self.header_frame,
            text="💼 Trade Settings",
            bootstyle=INFO,
            command=self.open_trade_settings
        ).pack(side=RIGHT, padx=5)

        tb.Button(
            self.header_frame,
            text="🧾 Broker Config",
            bootstyle=INFO,
            command=self.open_brokerconfig
        ).pack(side=RIGHT, padx=5)

        tb.Button(
            self.header_frame,
            text="⚙️ Config",
            bootstyle=INFO,
            command=self.open_config
        ).pack(side=RIGHT, padx=5)

        # ------------------------------------------------------
        # BODY
        # ------------------------------------------------------
        self.body_frame = tb.Frame(self)
        self.body_frame.pack(fill=BOTH, expand=YES)

        self.nav_frame = tb.Frame(self.body_frame, width=180)
        self.nav_frame.pack(side=LEFT, fill=Y, padx=(0, 5), pady=5)

        self.pages_frame = tb.Frame(self.body_frame)
        self.pages_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=5, pady=5)

        self.pages = {}
        self.create_nav_buttons()

        self.show_page("Home", TradeFriendHome)

    # ==========================================================
    # HEALTH UPDATE HANDLER
    # ==========================================================
    def _on_health_change(self, health_service):
        self.after(0, lambda: self._update_health_ui(health_service))

    def _update_health_ui(self, health_service):

        if health_service.internet_ok:
            self.internet_label.config(text="🌐 ONLINE", bootstyle=SUCCESS)
            self.internet_alert_shown = False
        else:
            self.internet_label.config(text="❌ OFFLINE", bootstyle=DANGER)

            if not self.internet_alert_shown:
                messagebox.showwarning(
                    "Internet Lost",
                    "Internet connection lost.\nTrading is paused."
                )
                self.internet_alert_shown = True

    # ==========================================================
    # NAVIGATION
    # ==========================================================
    def create_nav_buttons(self):
        nav_buttons = [
            ("Home", TradeFriendHome),
            ("Watchlist Dashboard", TradeFriendDashboard)
        ]

        for name, page_class in nav_buttons:
            btn = tb.Button(
                self.nav_frame,
                text=name,
                bootstyle=SECONDARY,
                width=20,
                command=lambda n=name, cls=page_class: self.show_page(n, cls)
            )
            btn.pack(pady=5)

    def show_page(self, name, page_class=None):

        for page in self.pages.values():
            if page.winfo_exists():
                page.pack_forget()

        if name not in self.pages and page_class:
            self.pages[name] = page_class(self.pages_frame)

        page = self.pages.get(name)
        if page and page.winfo_exists():
            page.pack(fill=BOTH, expand=YES)

    # ==========================================================
    # ENVIRONMENT CONTROL
    # ==========================================================
    def toggle_environment(self):

        new_env = "PROD" if AppConfig.is_dev() else "DEV"
        AppConfig.set_env(new_env)

        self.env_btn.config(
            text=f"ENV: {new_env}",
            bootstyle=SUCCESS if new_env == "DEV" else DANGER
        )

        messagebox.showinfo("Environment", f"Environment switched to {new_env}")

    # ==========================================================
    # TRADE MODE CONTROL
    # ==========================================================
    def toggle_trade_mode(self):

        new_mode = "LIVE" if self.trade_mode == "PAPER" else "PAPER"

        if new_mode == "LIVE":

            if not self.health_service.is_system_ready():
                messagebox.showerror(
                    "Cannot Enable LIVE",
                    "System is not ready.\nCheck internet or broker connection."
                )
                return

            confirm = messagebox.askyesno(
                "Confirm LIVE Mode",
                "You are switching to LIVE trading.\n\n"
                "Real orders will be placed in the market.\n"
                "Do you want to continue?"
            )
            if not confirm:
                return

        self.settings_repo.update({"trade_mode": new_mode})
        self.trade_mode = new_mode

        self.trade_mode_btn.configure(
            text=f"Mode: {self.trade_mode}",
            bootstyle=self._get_trade_mode_style()
        )

        messagebox.showinfo("Trade Mode", f"Mode set to {self.trade_mode}")

    def _get_trade_mode_style(self):
        return DANGER if self.trade_mode == "LIVE" else WARNING

    # ==========================================================
    # THEME HANDLING
    # ==========================================================
    def change_theme(self, event=None):
        try:
            self.style.theme_use(self.theme_var.get())
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to apply theme: {e}")

    # ==========================================================
    # POPUPS
    # ==========================================================
    def open_trade_settings(self):
        TradeFriendSettingsPopup(self)

    def open_config(self):
        BrokerConfigPopup(self)

    def open_brokerconfig(self):
        BrokerOrderConfigPopup(self)


# ==========================================================
# APPLICATION ENTRY
# ==========================================================
if __name__ == "__main__":

    # ------------------------------------------------------
    # START SYSTEM HEALTH FIRST
    # ------------------------------------------------------
    health_service = TradeFriendSystemHealthService(check_interval=10)
    health_service.start()

    # ------------------------------------------------------
    # START ENGINE WITH HEALTH
    # ------------------------------------------------------
    engine = TradeFriendAppEngine(health_service)
    threading.Thread(target=engine.start, daemon=True).start()

    # ------------------------------------------------------
    # START UI
    # ------------------------------------------------------
    app = TradeMadeEasyApp(health_service)
    app.mainloop()