# ui/TradeFriendSettingsPopup.py

import tkinter as tk
from tkinter import ttk, messagebox
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


class TradeFriendSettingsPopup(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Trade Settings")
        self.geometry("720x520")
        self.resizable(False, False)

        self.repo = TradeFriendSettingsRepo()
        self.inputs = {}
        self.fixed_mode = tk.BooleanVar()

        self._build_ui()
        self._load()

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.grid(sticky="nsew")

        # =====================
        # CAPITAL & RISK
        # =====================
        ttk.Label(main, text="Capital & Risk", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        cap = ttk.Frame(main)
        cap.grid(row=1, column=0, sticky="w")

        self._grid_field(cap, "Total Capital", "total_capital", 0)
        self._grid_field(cap, "Swing Capital", "max_swing_capital", 1)
        self._grid_field(cap, "Available Swing", "available_swing_capital", 2, readonly=True)
        self._grid_field(cap, "Per Trade Cap", "max_per_trade_capital", 3)
        self._grid_field(cap, "Max Open Trades", "max_open_trades", 4)

        ttk.Separator(main).grid(row=2, column=0, sticky="ew", pady=10)

        # =====================
        # PRICE → QTY (3 COL)
        # =====================
        ttk.Label(main, text="Price → Quantity", font=("Segoe UI", 11, "bold")).grid(
            row=3, column=0, sticky="w"
        )

        qty = ttk.Frame(main)
        qty.grid(row=4, column=0, sticky="w")

        slabs = [
            ("> 100", "qty_gt_100"),
            ("> 200", "qty_gt_200"),
            ("> 500", "qty_gt_500"),
            ("> 700", "qty_gt_700"),
            ("> 1000", "qty_gt_1000"),
            ("> 1500", "qty_gt_1500"),
            ("> 2000", "qty_gt_2000"),
        ]

        for i, (label, key) in enumerate(slabs):
            ttk.Label(qty, text=label, width=8).grid(row=i // 3, column=(i % 3) * 2)
            e = ttk.Entry(qty, width=6)
            e.grid(row=i // 3, column=(i % 3) * 2 + 1, padx=4)
            self.inputs[key] = e

        ttk.Separator(main).grid(row=5, column=0, sticky="ew", pady=10)

        # =====================
        # TARGET / SL
        # =====================
        tgt = ttk.Frame(main)
        tgt.grid(row=6, column=0, sticky="w")

        ttk.Checkbutton(
            tgt,
            text="Use FIXED Target / SL (%)",
            variable=self.fixed_mode,
            command=self._toggle_fixed
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        self._grid_field(tgt, "Target %", "fixed_target_percent", 1)
        self._grid_field(tgt, "SL %", "fixed_sl_percent", 2)

        # =====================
        # BUTTONS
        # =====================
        btns = ttk.Frame(main)
        btns.grid(row=7, column=0, sticky="e", pady=10)

        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=5)
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")

    # ------------------------------------
    def _grid_field(self, parent, label, key, row, readonly=False):
        ttk.Label(parent, text=label, width=18).grid(row=row, column=0, sticky="w")
        e = ttk.Entry(parent, width=10)
        e.grid(row=row, column=1, padx=6)
        if readonly:
            e.state(["readonly"])
        self.inputs[key] = e

    def _toggle_fixed(self):
        state = "normal" if self.fixed_mode.get() else "disabled"
        for k in ("fixed_target_percent", "fixed_sl_percent"):
            self.inputs[k].config(state=state)

    def _load(self):
        row = self.repo.fetch()
        if not row:
            return

        for k, e in self.inputs.items():
            if k in row.keys() and row[k] is not None:
                e.config(state="normal")
                e.delete(0, tk.END)
                e.insert(0, row[k])

        self.fixed_mode.set(row["target_sl_mode"] == "FIXED")
        self._toggle_fixed()

    def _save(self):
        try:
            data = {}
            for k, e in self.inputs.items():
                if "available" in k:
                    continue
                val = e.get().strip()
                if val:
                    data[k] = float(val) if val.replace(".", "", 1).isdigit() else val

            data["target_sl_mode"] = "FIXED" if self.fixed_mode.get() else "TRADITIONAL"

            if "max_swing_capital" in data:
                data["available_swing_capital"] = data["max_swing_capital"]

            self.repo.update(data)
            messagebox.showinfo("Saved", "Settings updated")
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e))
