from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter
from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderRepo import TradeFriendOrderRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from utils.logger import get_brokerorder_logger


class TradeFriendBrokerReconciliationService:

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):
        self.logger = get_brokerorder_logger()

        self.order_repo = TradeFriendOrderRepo()
        self.broker_repo = TradeFriendBrokerTradeRepo()
        self.trade_repo = TradeFriendTradeRepo()

        self.adapters = {
            "ANGEL": TradeFriendAngelOrderAdapter(),
            "DHAN": TradeFriendDhanOrderAdapter()
        }

    # =====================================================
    def run(self):
        self.reconcile()

    # =====================================================
    # MAIN RECON ENGINE
    # =====================================================
    def reconcile(self):

        open_orders = self.order_repo.fetch_open_orders()
    
        for order in open_orders:
        
            if order["status"] in ("COMPLETE", "CANCELLED", "REJECTED"):
                continue
            
            broker = order["broker"]
            adapter = self.adapters.get(broker)
    
            if not adapter:
                self.logger.warning(
                    f"No adapter found for broker={broker}"
                )
                continue
            
            try:
                # -----------------------------------------
                # Fetch broker execution status
                # -----------------------------------------
                details = adapter.get_order_status(
                    order["broker_order_id"]
                )
    
                final_status = details["status"]
                filled_qty = int(details.get("filled_qty", 0))
                avg_price = float(details.get("avg_price", 0))
                rejection_reason = details.get("rejection_reason")
    
                # -----------------------------------------
                # Skip if no change
                # -----------------------------------------
                if (
                    order["status"] == final_status
                    and order["filled_qty"] == filled_qty
                    and float(order.get("avg_price", 0)) == avg_price
                ):
                    self.order_repo.touch_reconciled(order["id"])
                    continue
                
                self.logger.info(
                    f"🔁 Recon | Order={order['id']} | "
                    f"{order['status']} → {final_status}"
                )
    
                # =========================================
                # HANDLE REJECTED
                # =========================================
                if final_status == "REJECTED":
                
                    self.order_repo.mark_rejected(
                        order_id=order["id"],
                        reason=rejection_reason
                    )
    
                    # ENTRY rejection → invalidate trade
                    if order["side"] == "ENTRY":
                        self.trade_repo.invalidate_trade(
                            trade_id=order["trade_id"],
                            reason=rejection_reason or "Entry Rejected",
                            status="REJECTED"
                        )
    
                    continue
                
                # =========================================
                # HANDLE CANCELLED
                # =========================================
                if final_status == "CANCELLED":
                
                    self.order_repo.update_status(
                        order_id=order["id"],
                        status="CANCELLED"
                    )
    
                    continue
                
                # =========================================
                # UPDATE ORDER TABLE
                # =========================================
                self.order_repo.update_fill_details(
                    order_id=order["id"],
                    filled_qty=filled_qty,
                    avg_price=avg_price,
                    status=final_status
                )
    
                # =========================================
                # UPDATE BROKER EXECUTION TABLE
                # =========================================
                self.broker_repo.update_execution(
                    broker_order_id=order["broker_order_id"],
                    execution_status=final_status,
                    filled_qty=filled_qty,
                    avg_price=avg_price
                )
    
                # =========================================
                # TRADE LIFECYCLE SYNC
                # =========================================
    
                # -----------------------------------------
                # ENTRY COMPLETE
                # -----------------------------------------
                if (
                    order["side"] == "ENTRY"
                    and final_status == "COMPLETE"
                ):
    
                    self.logger.info(
                        f"🟢 ENTRY COMPLETE | "
                        f"trade_id={order['trade_id']} | "
                        f"qty={filled_qty} | avg={avg_price}"
                    )
    
                    # 1️⃣ Deduct capital only now
                    locked_capital = round(avg_price * filled_qty, 2)
                    self.trade_repo.settings_repo.adjust_available_swing_capital(
                        -locked_capital
                    )
    
                    # 2️⃣ Update entry fill
                    self.trade_repo.update_entry_fill(
                        trade_id=order["trade_id"],
                        fill_qty=filled_qty,
                        fill_price=avg_price
                    )
    
                    # 3️⃣ Promote READY → OPEN
                    self.trade_repo.promote_if_ready(
                        trade_id=order["trade_id"],
                        from_status="READY",
                        to_status="OPEN"
                    )
    
                # -----------------------------------------
                # EXIT COMPLETE
                # -----------------------------------------
                if (
                    order["side"] == "EXIT"
                    and final_status == "COMPLETE"
                ):
    
                    trade = self.trade_repo.fetch_by_id(
                        order["trade_id"]
                    )
    
                    if not trade:
                        self.logger.warning(
                            f"Exit trade not found | "
                            f"trade_id={order['trade_id']}"
                        )
                        continue
                    
                    remaining_qty = int(trade["remaining_qty"])
    
                    self.logger.info(
                        f"🔴 EXIT COMPLETE | "
                        f"trade_id={order['trade_id']} | "
                        f"exit_qty={filled_qty} | "
                        f"remaining_before={remaining_qty}"
                    )
    
                    # Partial Exit
                    if filled_qty < remaining_qty:
                    
                        self.trade_repo.mark_partial_exit(
                            trade_id=order["trade_id"],
                            exit_qty=filled_qty,
                            exit_price=avg_price,
                            reason="Broker Exit Fill"
                        )
    
                    # Full Exit
                    else:
                    
                        self.trade_repo.close_and_archive(
                            trade_id=order["trade_id"],
                            exit_price=avg_price,
                            exit_reason="Broker Exit Fill"
                        )
    
                # -----------------------------------------
                # Final touch
                # -----------------------------------------
                self.order_repo.touch_reconciled(order["id"])
    
            except Exception as e:
            
                self.logger.error(
                    f"❌ Recon error | Order={order['id']} | {str(e)}"
                )
    
                self.order_repo.mark_recon_error(
                    order_id=order["id"],
                    error=str(e)
                )
    