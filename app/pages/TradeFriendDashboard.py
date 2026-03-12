import threading
import tkinter.messagebox as messagebox
from tkinter import ttk, StringVar
from datetime import datetime, time

from core.TradeFriendDataProvider import TradeFriendDataProvider
from core.TradeFriendScheduler import TradeFriendScheduler
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from utils.TradeFriendManager import TradeFriendManager
from Servieces.TradeFriendTradeViewService import TradeFriendTradeViewService
from datetime import datetime, time as dtime, timedelta
from utils.logger import get_logger
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from Servieces.TradeFriendMarketTimeService import TradeFriendMarketTimeService as MTS

logger = get_logger(__name__)

class TradeFriendDashboard(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        # ---------------- Repos / Services ----------------
        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.trade_history_repo = TradeFriendTradeHistoryRepo()
        self.settings_repo = TradeFriendSettingsRepo()
        self.swing_plan_repo = TradeFriendSwingPlanRepo()

        self.manager = TradeFriendManager()
        self.provider = TradeFriendDataProvider()

        self.trade_mode = self.settings_repo.get_trade_mode()
        self.ltp_cache = {}

        # 🕒 5-MIN TRIGGER STATE
        self._last_trigger_minute = None
        self._refresh_check_ms = 20 * 1000

        # 🔍 Search state  ✅ MUST BE BEFORE UI BUILD
        self.watchlist_search_var = StringVar()
        self.trades_search_var = StringVar()

        # 🧠 Cached data for filtering
        self._watchlist_rows_cache = []
        self._active_trades_cache = []

        # # ✅ BACKGROUND SCHEDULER
        # self.scheduler = TradeFriendScheduler(
        #     manager=self.manager,
        #     trade_mode=self.trade_mode
        # )
        # self.scheduler.start()

        # 🎨 BUILD UI (uses search vars)
        self._build_ui()
        self.refresh_data()

        # ⏱️ START AUTO REFRESH LOOP
        self._start_refresh_timer()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        # ---------- Loading ----------
        self.loading_var = StringVar(value="")
        loading_frame = ttk.Frame(self)
        loading_frame.pack(fill="x", padx=6)

        ttk.Label(
            loading_frame,
            textvariable=self.loading_var,
            foreground="blue"
        ).pack(side="left", padx=6)

        self.progress = ttk.Progressbar(
            loading_frame, mode="indeterminate", length=200
        )
        self.progress.pack(side="left", padx=6)

        # ---------- Refresh Status ----------
        self.refresh_status = StringVar(value="⏳ Waiting for market...")
        ttk.Label(
            self,
            textvariable=self.refresh_status,
            foreground="gray"
        ).pack(anchor="w", padx=8)

        # ---------- KPI ----------
        self.kpi_frame = ttk.Frame(self)
        self.kpi_frame.pack(fill="x", padx=8, pady=6)

        self.kpi_labels = {}
        for key in [
            "capital", "swing_used", "swing_available",
            "active", "profit", "loss", "pnl"
        ]:
            lbl = ttk.Label(
                self.kpi_frame,
                text="--",
                background="white",
                anchor="center",
                font=("Segoe UI", 11, "bold"),
                padding=8
            )
            lbl.pack(side="left", expand=True, fill="x", padx=4)
            self.kpi_labels[key] = lbl

        # ---------- Controls ----------
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)

        self.manual_mode = StringVar(value="FULL")

        ttk.Combobox(
            bar,
            textvariable=self.manual_mode,
            values=["DAILYSCAN", "DECISION", "MORNING", "FULL"],
            width=12,
            state="readonly"
        ).pack(side="left", padx=5)

        ttk.Button(
            bar,
            text="🛠️ Run Manual",
            command=self.run_manual_wrapper
        ).pack(side="left", padx=5)

        ttk.Button(
            bar,
            text="🔄 Refresh",
            command=self.refresh_data
        ).pack(side="right", padx=5)

        self.mode_btn = ttk.Button(bar, command=self.toggle_trade_mode)
        self.mode_btn.pack(side="right", padx=5)
        self._update_trade_mode_btn()

        # ---------- Tabs ----------
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.watchlist_tab = ttk.Frame(notebook)
        
        self.history_tab = ttk.Frame(notebook)

        notebook.add(self.watchlist_tab, text="📋 Watchlist")
       
        notebook.add(self.history_tab, text="📜 History")

        self._build_watchlist()
       
        self._build_history()


    # =====================================================
    # TABLES
    # =====================================================

    def _build_watchlist(self):
        """
        Watchlist tab now represents Swing Trade Plans
        (PLANNED / HOLD)
        """

        search_bar = ttk.Frame(self.watchlist_tab)
        search_bar.pack(fill="x", padx=6, pady=4)

        ttk.Label(search_bar, text="🔍 Search:").pack(side="left")

        search_entry = ttk.Entry(
            search_bar,
            textvariable=self.watchlist_search_var,
            width=30
        )
        search_entry.pack(side="left", padx=5)
        search_entry.bind("<KeyRelease>", self._filter_watchlist)

        cols = (
            "symbol",
            "strategy",
            "direction",
            "entry",
            "sl",
            "target",
            "status",
            "created_on"
        )

        self.watchlist_table = ttk.Treeview(
            self.watchlist_tab,
            columns=cols,
            show="headings"
        )

        headings = {
            "symbol": "SYMBOL",
            "strategy": "STRATEGY",
            "direction": "SIDE",
            "entry": "ENTRY",
            "sl": "SL",
            "target": "TARGET",
            "status": "STATUS",
            "created_on": "CREATED"
        }

        for c in cols:
            self.watchlist_table.heading(c, text=headings[c])
            self.watchlist_table.column(c, width=110, anchor="center")

        self.watchlist_table.pack(
            fill="both",
            expand=True,
            padx=6,
            pady=6
        )


    def _build_history(self):
        cols = (
            "symbol", "entry", "exit_price", "qty",
            "pnl", "r", "exit_reason", "closed_on"
        )
        self.history_table = ttk.Treeview(
            self.history_tab, columns=cols, show="headings"
        )
        for c in cols:
            self.history_table.heading(c, text=c.upper())
            self.history_table.column(c, width=110, anchor="center")
        self.history_table.pack(fill="both", expand=True, padx=6, pady=6)

    # =====================================================
    # DATA LOADING
    # =====================================================

    def refresh_data(self):
        self._start_loading("Refreshing dashboard...")
        threading.Thread(
            target=self._load_data_bg, daemon=True
        ).start()

    def _load_data_bg(self):
        try:
            # 🔁 DATA SOURCES
            plan_trades = self.swing_plan_repo.fetch_active_plans()
            active = self.trade_repo.fetch_active_trades()
            history = self.trade_history_repo.fetch_recent_closed()

            # ---------------- KPI (ACTIVE ONLY) ----------------
            total_pnl = 0.0
            win = 0
            loss = 0

            for row in active:
                try:
                    t = dict(row)

                    symbol = t.get("symbol")
                    entry = t.get("entry")
                    qty = t.get("qty")

                    if not symbol or entry is None or qty is None:
                        continue

                    ltp = self._get_ltp_cached(symbol)
                    if ltp is None:
                        continue

                    pnl = (ltp - entry) * qty
                    total_pnl += pnl

                    if pnl > 0:
                        win += 1
                    elif pnl < 0:
                        loss += 1

                except Exception as e:
                    print(f"❌ KPI calc error | {t.get('symbol')} | {e}")

            active_count = len(active)

            # ---------------- UI THREAD ----------------
            # 🟣 WATCHLIST TAB → NOW SHOWS SWING PLANS
            self.after(0, lambda: self._update_watchlist(plan_trades))

           

            # 🔵 HISTORY
            self.after(0, lambda: self._update_history(history))

            # 📊 KPIs
            self.after(
                0,
                lambda: self._update_kpis(
                    total_pnl=total_pnl,
                    active=active_count,
                    win=win,
                    loss=loss
                )
            )

        finally:
            self.after(0, self._stop_loading)

    # =====================================================
    # UI UPDATES
    # =====================================================

    def _update_watchlist(self, rows):
        """
        Update Watchlist tab with Swing Trade Plans. 
        Responsibilities:
        - Cache raw DB rows (for search / re-filter)
        - Delegate pure UI rendering to _render_watchlist()
        """ 
        # 🧠 Cache for search/filter
        self._watchlist_rows_cache = rows or [] 
        # 🎨 Render UI
        self._render_watchlist(self._watchlist_rows_cache)


    def _render_watchlist(self, rows):
       """
       Pure UI renderer for Watchlist table.
       No DB calls. No filtering logic.
       """

       # 🔐 Safety
       if not hasattr(self, "watchlist_table"):
           return

       self.watchlist_table.delete(*self.watchlist_table.get_children())

       for r in rows:
           try:
               plan = dict(r)

               self.watchlist_table.insert(
                   "",
                   "end",
                   values=(
                       plan.get("symbol"),
                       plan.get("strategy"),
                       plan.get("direction"),
                       round(plan.get("entry", 0), 2),
                       round(plan.get("sl", 0), 2),
                       round(plan.get("target1", 0), 2),
                       plan.get("status"),
                       plan.get("created_on")
                   )
               )

           except Exception as e:
               logger.error(
                   f"❌ Watchlist row render failed | "
                   f"symbol={r.get('symbol') if isinstance(r, dict) else 'N/A'} | "
                   f"error={e}"
               )

    def _update_history(self, trades):
        self.history_table.delete(*self.history_table.get_children())
        for t in trades:
            self.history_table.insert(
                "", "end",
                values=TradeFriendTradeViewService.history_trade_row(t)
            )

    # =====================================================
    # Filter active symbol from Watchlist and trade
    # =====================================================

    def _filter_watchlist(self, event=None):
        query = self.watchlist_search_var.get().lower().strip()

        if not query:
            self._render_watchlist(self._watchlist_rows_cache)
            return

        filtered = [
            r for r in self._watchlist_rows_cache
            if query in str(dict(r).get("symbol", "")).lower()
            or query in str(dict(r).get("strategy", "")).lower()
            or query in str(dict(r).get("status", "")).lower()
        ]

        self._render_watchlist(filtered)


    # =====================================================
    # KPI
    # =====================================================

    def _update_kpis(self, total_pnl, active, win, loss):
        s = self.settings_repo.fetch()

        total = s["total_capital"] or 0
        max_swing = s["max_swing_capital"] or 0
        free = s["available_swing_capital"] or 0
        used = round(max_swing - free, 2)

        self.kpi_labels["capital"].config(text=f"💰 Total: {total}",foreground="black")
        self.kpi_labels["swing_used"].config(text=f"🔒 Used: {used}",foreground="black")
        self.kpi_labels["swing_available"].config(text=f"🟢 Free: {free}",foreground="black")
        self.kpi_labels["active"].config(text=f"📊 Active: {active}",foreground="black")
        self.kpi_labels["profit"].config(text=f"🟢 Wins: {win}",foreground="green")
        self.kpi_labels["loss"].config(text=f"🔴 Loss: {loss}",foreground="red")
        self.kpi_labels["pnl"].config(
            text=f"💵 PnL: {round(total_pnl, 2)}",
            foreground="green" if total_pnl >= 0 else "red"
        )

    # =====================================================
    # HELPERS
    # ====================================================

    # ============================================================
    # LTP ACCESS (Dashboard-owned cache + provider fetch)
    # - Cache-first with TTL
    # - MarketTimeService is the authority
    # - Provider is used only when allowed
    # - Safe fallback to last known price
    # ============================================================

    def _get_ltp_from_cache(self, symbol: str, ttl_seconds: int):
        """
        Return cached LTP if present and within TTL, else None.
        """
        cached = self.ltp_cache.get(symbol)
        if not cached:
            return None

        price, ts = cached
        if not ts:
            return None

        age = (MTS.now() - ts).total_seconds()
        if age <= ttl_seconds:
            return price

        return None


    def _fetch_ltp_from_provider(self, symbol: str):
        """
        One-shot LTP fetch from provider.
        No cache. No TTL. Cooldown-safe.
        """
        try:
            return self.provider.get_ltp_byLtp(symbol)
        except Exception:
            return None


    def _get_ltp_cached(self, symbol: str, ttl_seconds: int = 20):
        """
        Centralized LTP access for UI:
        - Cache-first (TTL)
        - Market-time governed
        - Provider fetch when allowed
        - Fallback to last cached value
        """

        # --------------------------------------------------
        # 1️⃣ Cache first
        # --------------------------------------------------
        cached_price = self._get_ltp_from_cache(symbol, ttl_seconds)
        if cached_price is not None:
            return cached_price

        # --------------------------------------------------
        # 3️⃣ Fetch fresh LTP
        # --------------------------------------------------
        ltp = self._fetch_ltp_from_provider(symbol)
        if ltp is not None:
            self.ltp_cache[symbol] = (ltp, MTS.now())
            return ltp

        # --------------------------------------------------
        # 4️⃣ Final fallback
        # --------------------------------------------------
        return self.ltp_cache.get(symbol, (None, None))[0]

    

    def toggle_trade_mode(self):
        self.trade_mode = "LIVE" if self.trade_mode == "PAPER" else "PAPER"
        self.settings_repo.set_trade_mode(self.trade_mode)
        self._update_trade_mode_btn()
        messagebox.showinfo("Trade Mode", f"Mode set to {self.trade_mode}")

    def _update_trade_mode_btn(self):
        self.mode_btn.config(
            text="🟢 LIVE" if self.trade_mode == "LIVE" else "📝 PAPER"
        )

    # =====================================================
    # ACTIONS
    # =====================================================

    def run_daily_scan(self):
        self._run_bg(lambda: self.manager.tf_daily_scan(self.trade_mode))

    def run_morning_confirm(self):
        self._run_bg(lambda: self.manager.tf_morning_confirm(
            capital=100000, mode=self.trade_mode))

    def run_monitor(self):
        self._run_bg(lambda: self.manager.tf_monitor())

    def _run_bg(self, task):
        threading.Thread(
            target=lambda: (task(), self.after(0, self.refresh_data)),
            daemon=True
        ).start()

    def run_decision_runner(self):
        """
        Run DecisionRunner in background thread from UI
        """
        self._run_bg(lambda: self.manager.tf_decision_runner())
    
    # =====================================================
    # LOADING
    # =====================================================

    def _start_loading(self, msg):
        self.loading_var.set(msg)
        self.progress.start(10)
    def _stop_loading(self):
        self.progress.stop()
        self.loading_var.set("")

     # =====================================================
    # TIME HELPERS
    # =====================================================

    def _now(self):
        return datetime.now()

    def is_trigger_engine_time(self):
        now = self._now().time()
        return dtime(9, 16) <= now <= dtime(15, 25)

    def _five_minute_key(self):
        now = self._now()
        minute_bucket = (now.minute // 5) * 5
        return now.replace(minute=minute_bucket, second=0, microsecond=0)
    
    # =====================================================
    # AUTO REFRESH LOOP
    # =====================================================

    def _start_refresh_timer(self):
        self.after(self._refresh_check_ms, self._refresh_timer_tick)

    def _refresh_timer_tick(self):
        now = self._now()

        if not self.is_trigger_engine_time():
            self.refresh_status.set("🚫 Market closed — auto refresh paused")
            self.after(self._refresh_check_ms, self._refresh_timer_tick)
            return

        minute_key = self._five_minute_key()

        if self._last_trigger_minute != minute_key:
            self._last_trigger_minute = minute_key

            self.refresh_status.set(
                f"🔄 Refreshing… ({minute_key.strftime('%H:%M')})"
            )

            threading.Thread(
                target=self._load_data_bg,
                daemon=True
            ).start()
        else:
            self._update_refresh_label()

        self.after(self._refresh_check_ms, self._refresh_timer_tick)

    def _update_refresh_label(self):
        last = self._last_trigger_minute
        if not last:
            return

        next_refresh = last + timedelta(minutes=5)
        self.refresh_status.set(
            f"🕒 Last: {last.strftime('%H:%M')}  |  "
            f"⏭ Next: {next_refresh.strftime('%H:%M')}"
        )

    # =====================================================
    # DATA REFRESH (ACTIVE ONLY)
    # =====================================================

    def _refresh_active_trades_only(self):
        try:
            active = self.trade_repo.fetch_active_trades()

            total_pnl = 0.0
            win = 0
            loss = 0

            for row in active:
                t = dict(row)
                symbol = t.get("symbol")
                entry = t.get("entry")
                qty = t.get("qty")

                if not symbol or entry is None or qty is None:
                    continue

                ltp = self._get_ltp_cached(symbol)
                if ltp is None:
                    continue

                pnl = (ltp - entry) * qty
                total_pnl += pnl

                if pnl > 0:
                    win += 1
                elif pnl < 0:
                    loss += 1

            self.after(0, lambda: self._update_active_trades(active))
            self.after(
                0,
                lambda: self._update_kpis(
                    total_pnl=total_pnl,
                    active=len(active),
                    win=win,
                    loss=loss
                )
            )
            self.after(0, self._update_refresh_label)

        except Exception as e:
            logger.error(f"❌ Active refresh failed: {e}")

    # ---------------- Wrapper to pass selected flow ----------------
    def run_manual_wrapper(self):
        """
        Gets the selected flow from combobox and calls run_manual.
        """
        flow = self.manual_mode.get()
        self.run_manual(flow=flow, force=True)

    def run_manual(self, flow: str, force: bool = False):
        """
        Run manual automation based on the selected flow.
    
        flow options:
            - DAILYSCAN
            - DECISION
            - MORNING
            - FULL
        """
        logger.info(
            f"🛠 Manual run requested | flow={flow} | "
            f"trade_mode={self.trade_mode} | force={force}"
        )
    
        def task():
            if flow == "DAILYSCAN":
                self.manager.tf_daily_scan(self.trade_mode)
    
            elif flow == "DECISION":
                self.manager.tf_decision_runner()
    
            elif flow == "MORNING":
                self.manager.tf_morning_confirm(
                    capital=100000,   # or pull from settings
                    mode=self.trade_mode
                )
    
            elif flow == "FULL":
                # ✅ EXACT automated sequence
                # self.manager.tf_daily_scan(self.trade_mode)
                self.manager.tf_decision_runner()
                self.manager.tf_morning_confirm(
                    capital=100000,
                    mode=self.trade_mode
                )
    
            else:
                logger.warning(f"Unknown manual flow: {flow}")
    
        self._run_bg(task)


