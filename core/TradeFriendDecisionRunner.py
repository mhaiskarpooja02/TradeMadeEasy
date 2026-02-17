# core/TradeFriendDecisionRunner.py

from datetime import datetime, date
import time

from const.TradeFriendPlanStatus import PlanStatus, TradeStatus
from core.TradeFriendDecisionEngine import TradeFriendDecisionEngine
from Servieces.TradeFriendInitialScanReportService import TradeFriendDailyScanReportService
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from reports.TradeFriendMorningconfirmreport import MorningConfirmReport
from reports.TradeFriendMorningconfirmpdfbuilder import MorningConfirmPdfBuilder
from config.TradeFriendConfig import REQUEST_DELAY_SEC

from utils.logger import get_decision_runner_logger, get_logger
logger = get_decision_runner_logger()


class TradeFriendDecisionRunner:
    """
    Phase-1C: Decision Runner (FINAL)
    --------------------------------
    - Evaluates PLANNED + HOLD plans
    - APPROVED → READY trade
    - HOLD → retry until expiry
    - REJECTED → terminal (strategy-aware)
    - EXPIRED → auto-clean
    """

    def __init__(self, ltp_provider=None):
        self.swing_plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.settings_repo = TradeFriendSettingsRepo()
        self.ltp_provider = ltp_provider

        s = self.settings_repo.fetch()
        self.trade_mode = self.settings_repo.get_trade_mode()
        self.capital = s["available_swing_capital"] or 0

        self.report = MorningConfirmReport(
            mode=self.trade_mode,
            capital=self.capital
        )

    # ==================================================
    # EXPIRY CHECK
    # ==================================================
    def _is_expired(self, plan: dict) -> bool:
        expiry = plan.get("expiry_date")
        if not expiry:
            return False
        try:
            return date.today() > date.fromisoformat(expiry)
        except Exception:
            return False

    # ==================================================
    # PROTECTION WINDOW (MORNING CONFIRM)
    # ==================================================
    def _is_under_protection(self, plan: dict, days: int = 3) -> bool:
        created = plan.get("created_on")
        if not created:
            return False
        try:
            created_date = datetime.fromisoformat(created).date()
            return (date.today() - created_date).days < days
        except Exception:
            return False

    # ==================================================
    # MAIN ENTRY
    # ==================================================
    def run(self):
        logger.info("─" * 80)
        logger.info(
            f"🗓️ DecisionRunner started | date={date.today().isoformat()} | "
            f"time={datetime.now().strftime('%H:%M:%S')}"
        )
        logger.info("🧠 DecisionRunner started for swing plans")

        # Expire old plans first
        self.swing_plan_repo.expire_old_plans()

        # Fetch active plans (PLANNED + HOLD)
        plans = self.swing_plan_repo.fetch_active_plans()
        if not plans:
            logger.info("No PLANNED / HOLD plans found")
            return

        engine = TradeFriendDecisionEngine(self.trade_repo)

        for plan_row in plans:
            plan = dict(plan_row)
            symbol = plan.get("symbol")

            try:
                result = engine.evaluate(plan)
                decision = result.get("decision")

                # ==========================================
                # APPROVED
                # ==========================================
                if decision == PlanStatus.APPROVED:
                    trade = result["trade"]
                    trade["side"] = plan.get("direction", "BUY")
                
                    # 🔒 1️⃣ Block if active trade exists (OPEN / PARTIAL)
                    if self.trade_repo.has_open_trade(symbol):
                        logger.info(
                            f"⛔ ACTIVE trade already exists. Skipping READY for {symbol}"
                        )
                        continue
                    
                    # 🔁 2️⃣ Check if READY already exists
                    existing_ready = self.trade_repo.fetch_ready_by_symbol(symbol)
                
                    if existing_ready:
                        old_entry = existing_ready["planned_entry"]
                        new_entry = trade["entry"]
                
                        if trade["side"] == "BUY":
                            better = new_entry < old_entry
                        else:
                            better = new_entry > old_entry
                
                        if better:
                            self.trade_repo.update_ready_trade(
                                existing_ready["id"],
                                {
                                    **trade,
                                    "planned_entry": plan["entry"]
                                }
                            )
                            logger.info(
                                f"🔁 READY UPDATED (Better Entry) | {symbol}"
                            )
                        else:
                            logger.info(
                                f"⏭️ READY IGNORED (Worse Entry) | {symbol}"
                            )
                
                        continue
                    
                    # 🆕 3️⃣ No READY → Insert new
                    self.trade_repo.save_trade({
                        **trade,
                        "initial_qty": trade["qty"],
                        "remaining_qty": trade["qty"],
                        "filled_qty": 0,
                        "status": TradeStatus.READY,
                        "swing_plan_id": plan["id"],
                        "planned_entry": plan["entry"],
                    })
                
                    logger.info(
                        f"✅ READY CREATED | {symbol}"
                    )
                
                    self.swing_plan_repo.mark_decision(
                        plan["id"], PlanStatus.APPROVED
                    )
                
                # ==========================================
                # HOLD
                # ==========================================
                elif decision == PlanStatus.HOLD:
                    if self._is_expired(plan):
                        self.swing_plan_repo.mark_decision(
                            plan["id"], PlanStatus.EXPIRED
                        )

                        self.report.add(
                            symbol=symbol,
                            ltp=None,
                            entry=plan["entry"],
                            sl=plan["sl"],
                            target=plan.get("target1") or plan.get("target"),
                            decision=MorningConfirmReport.DECISION_REJECTED,
                            reason="Expired while on HOLD"
                        )

                        logger.info(
                            "DECISION=EXPIRED | "
                            f"symbol={symbol} | "
                            f"swing_plan_id={plan['id']}"
                        )
                    else:
                        self.swing_plan_repo.mark_decision(
                            plan["id"], PlanStatus.HOLD
                        )

                        self.report.add(
                            symbol=symbol,
                            ltp=None,
                            entry=plan["entry"],
                            sl=plan["sl"],
                            target=plan.get("target1") or plan.get("target"),
                            decision=MorningConfirmReport.DECISION_SKIPPED,
                            reason=f"HOLD: {result.get('reason')}"
                        )

                        logger.info(
                            "DECISION=HOLD | "
                            f"symbol={symbol} | "
                            f"reason={result.get('reason')} | "
                            f"swing_plan_id={plan['id']}"
                        )

                # ==========================================
                # REJECTED (STRATEGY-AWARE)
                # ==========================================
                else:
                    strategy = plan.get("strategy", "")
                    protected = self._is_under_protection(plan)

                    if strategy == "Upper Band Expansion" or protected:
                        self.swing_plan_repo.mark_decision(
                            plan["id"], PlanStatus.HOLD
                        )

                        self.report.add(
                            symbol=symbol,
                            ltp=None,
                            entry=plan["entry"],
                            sl=plan["sl"],
                            target=plan.get("target1") or plan.get("target"),
                            decision=MorningConfirmReport.DECISION_SKIPPED,
                            reason=f"HOLD (Protected): {result.get('reason')}"
                        )

                        logger.info(
                            "DECISION=HOLD(PROTECTED) | "
                            f"symbol={symbol} | "
                            f"strategy={strategy} | "
                            f"reason={result.get('reason')} | "
                            f"swing_plan_id={plan['id']}"
                        )
                    else:
                        self.swing_plan_repo.mark_decision(
                            plan["id"], PlanStatus.REJECTED
                        )

                        self.report.add(
                            symbol=symbol,
                            ltp=None,
                            entry=plan["entry"],
                            sl=plan["sl"],
                            target=plan.get("target1") or plan.get("target"),
                            decision=MorningConfirmReport.DECISION_REJECTED,
                            reason=result.get("reason")
                        )

                        logger.info(
                            "DECISION=REJECTED | "
                            f"symbol={symbol} | "
                            f"reason={result.get('reason')} | "
                            f"swing_plan_id={plan['id']}"
                        )

            # ==========================================
            # SYSTEM FAILURE → HOLD
            # ==========================================
            except Exception as e:
                logger.exception(f"Decision failed for {symbol}")

                if self._is_expired(plan):
                    status = PlanStatus.EXPIRED
                    reason = "Expired due to system error"
                else:
                    status = PlanStatus.HOLD
                    reason = f"SYSTEM_ERROR: {e}"

                self.swing_plan_repo.mark_decision(plan["id"], status)

                self.report.add(
                    symbol=symbol,
                    ltp=None,
                    entry=plan.get("entry"),
                    sl=plan.get("sl"),
                    target=plan.get("target1") or plan.get("target"),
                    decision=MorningConfirmReport.DECISION_SKIPPED,
                    reason=reason
                )

                logger.error(
                    "DECISION=SYSTEM_ERROR | "
                    f"symbol={symbol} | "
                    f"status={status} | "
                    f"swing_plan_id={plan['id']}",
                    exc_info=True
                )

            time.sleep(REQUEST_DELAY_SEC)

        self._generate_reports()

        logger.info(
            "🧾 DecisionRunner completed | "
            f"approved={len(self.report.approved())} | "
            f"rejected={len(self.report.rejected())} | "
            f"hold={len(self.report.skipped())}"
        )
        logger.info("─" * 80)

    # ==================================================
    # REPORT OUTPUT
    # ==================================================
    def _generate_reports(self, scan_date=None):

        scan_date = scan_date or date.today().isoformat()
        
        if self.report.is_empty():
            logger.info("No report data generated")
            return
    
        pdf = MorningConfirmPdfBuilder()
        attachments = []
    
        if self.report.has_approved():
            path = pdf.build(
                title="✅ Approved Trades",
                rows=self.report.approved(),
                filename_suffix=f"approved_{scan_date}",
                mode=self.trade_mode,
                capital=self.capital
            )
            if path:
                attachments.append(path)
    
        if self.report.has_rejected():
            path = pdf.build(
                title="❌ Rejected Trades",
                rows=self.report.rejected(),
                filename_suffix=f"rejected_{scan_date}",
                mode=self.trade_mode,
                capital=self.capital
            )
            if path:
                attachments.append(path)
    
        if self.report.has_skipped():
            path = pdf.build(
                title="⏸ Hold Trades",
                rows=self.report.skipped(),
                filename_suffix=f"hold_{scan_date}",
                mode=self.trade_mode,
                capital=self.capital
            )
            if path:
                attachments.append(path)
    
        if not attachments:
            logger.info("No PDFs generated to send")
            return
    
        # 📧 reuse existing infra
        TradeFriendDailyScanReportService.send_email(
            scan_date=scan_date,
            scan_results= self.report.summary(),
            attachments=attachments
        )
