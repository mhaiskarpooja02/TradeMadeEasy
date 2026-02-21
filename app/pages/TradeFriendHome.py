import threading
import tkinter as tk
from tkinter import ttk, StringVar
from datetime import datetime

from utils.logger import get_logger
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendTradeViewService import TradeFriendTradeViewService
from Servieces.TradeFriendMarketTimeService import TradeFriendMarketTimeService as MTS

from Servieces.TradeFriendPortfolioService import TradeFriendPortfolioService

logger = get_logger(__name__)


class TradeFriendHome(ttk.Frame):

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self, parent):
        super().__init__(parent)

        # ---------------- Repositories / Services ----------------
        self.trade_repo = TradeFriendTradeRepo()
        self.view_service = TradeFriendTradeViewService()
        self.market_time = MTS()
        self.portfolio_service = TradeFriendPortfolioService()

        # ---------------- Refresh Config ----------------
        self._refresh_interval_ms = 5 * 60 * 1000  # 5 minutes
        self._last_updated_var = StringVar(value="Last Updated: --")

        # ---------------- Cache ----------------
        self._gainers_cache = []
        self._losers_cache = []

        # ---------------- Build UI ----------------
        self._build_ui()

        # Initial Load
        self.after(200, self.refresh_data)
        # Start Auto Refresh
        self._start_refresh_timer()

    # =====================================================
    # UI BUILD
    # =====================================================
    def _build_ui(self):

        # Title
        title = ttk.Label(
            self,
            text="🏠 TradeFriend Home - Top Movers",
            font=("Segoe UI", 16, "bold")
        )
        title.pack(pady=(15, 5))

        # Last Updated
        self.last_updated_label = ttk.Label(
            self,
            textvariable=self._last_updated_var,
            font=("Segoe UI", 9)
        )
        self.last_updated_label.pack(pady=(0, 10))

        # Main Container
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=15, pady=10)

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        # ---------------- GAINERS ----------------
        gainers_frame = ttk.LabelFrame(container, text="🔼 Top Gainers")
        gainers_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        self.gainers_tree = self._create_tree(gainers_frame)
        self.gainers_tree.pack(fill="both", expand=True)

        # ---------------- LOSERS ----------------
        losers_frame = ttk.LabelFrame(container, text="🔻 Top Losers")
        losers_frame.grid(row=0, column=1, sticky="nsew", padx=5)

        self.losers_tree = self._create_tree(losers_frame)
        self.losers_tree.pack(fill="both", expand=True)

        # ---------------- Loader ----------------
        self.loader_frame = ttk.Frame(self)
        self.loader_frame.pack(pady=5)

        self.loader_label = ttk.Label(
            self.loader_frame,
            text="Loading market data...",
            font=("Segoe UI", 9)
        )

        self.loader = ttk.Progressbar(
            self.loader_frame,
            mode="indeterminate",
            length=200
        )

        # Initially hidden
        self.loader_frame.pack_forget()

    # =====================================================
    # TREE FACTORY
    # =====================================================
    def _create_tree(self, parent):

        columns = (
            "symbol",
            "entry",
            "ltp",
            "qty",
            "pnl",
            "pnl_percent"
        )

        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=15
        )

        headings = {
            "symbol": "SYMBOL",
            "entry": "ENTRY",
            "ltp": "LTP",
            "qty": "QTY",
            "pnl": "PnL",
            "pnl_percent": "PnL %"
        }

        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, anchor="center", width=90)

        tree.column("symbol", width=120)

         # ✅ COLOR TAGS
        tree.tag_configure("profit", foreground="green")
        tree.tag_configure("loss", foreground="red")


        return tree

    # =====================================================
    # REFRESH DATA
    # =====================================================
    def refresh_data(self):
        self._show_loader()
        threading.Thread(
            target=self._refresh_background,
            daemon=True
        ).start()

    def _refresh_background(self):
        try:
            gainers, losers = self.portfolio_service.get_top_movers()
            total_pnl = self.portfolio_service.get_total_portfolio_pnl()

            # Safely update UI from main thread
            self.after(
                0,
                self._update_ui,
                gainers,
                losers,
                total_pnl
            )

        except Exception as e:
            logger.exception(f"Home refresh failed: {e}")

    def _update_ui(self, gainers, losers, total_pnl):

        self._populate_tree(self.gainers_tree, gainers)
        self._populate_tree(self.losers_tree, losers)

        now = datetime.now().strftime("%H:%M:%S")
        self._last_updated_var.set(
            f"Last Updated: {now} | Total PnL: {total_pnl}"
        )

        self._hide_loader()
        logger.info("Home refreshed successfully")

    # =====================================================
    # POPULATE TREE
    # =====================================================
    def _populate_tree(self, tree, rows):

        # Clear
        for item in tree.get_children():
            tree.delete(item)

        for row in rows:
            pnl = round(row.get("pnl", 0), 2)

            pnl = row.get("pnl", 0)
            tag = ""
    
            if pnl > 0:
                tag = "profit"
            elif pnl < 0:
                tag = "loss"
    

            pnl_percent = round(row.get("pnl_percent", 0), 2)

            tree.insert(
                "",
                "end",
                values=(
                    row.get("symbol"),
                    row.get("entry"),
                    row.get("ltp"),
                    row.get("qty"),
                    pnl,
                    row.get("pnl_percent", 0)
                ),
                tags=(tag,)
            )

    # =====================================================
    # AUTO REFRESH LOOP (5 MIN)
    # =====================================================
    def _start_refresh_timer(self):
        interval = self._get_refresh_interval_ms()

        logger.info(f"Next Home refresh in {interval / 60000} minutes")

        self.after(interval, self._auto_refresh)

    def _auto_refresh(self):
        self.refresh_data()
        self._start_refresh_timer()

    # =====================================================
    # Loader helper method
    # =====================================================
    def _show_loader(self):
        self.loader_frame.pack(pady=5)
        self.loader_label.pack(side="left", padx=5)
        self.loader.pack(side="left", padx=5)
        self.loader.start(10)

    def _hide_loader(self):
        self.loader.stop()
        self.loader_frame.pack_forget()
    
    # =====================================================
    # Refresh time interval 
    # =====================================================
    def _get_refresh_interval_ms(self):

        # 🔵 Weekend or Non-Trading Day
        if not MTS.is_trading_day():
            return 6 * 60 * 60 * 1000  # 6 hours

        # 🟡 Trading day but market closed
        if not MTS.is_market_open():
            return 30 * 60 * 1000  # 30 minutes (optional tuning)

        # 🟢 Market open
        return 5 * 60 * 1000  # 5 minutes