from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter
from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderRepo import TradeFriendOrderRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from utils.logger import get_brokerorder_logger
import uuid

logger = get_brokerorder_logger()

class TradeFriendBrokerReconciliationService:

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):
    

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

       # -----------------------------------------
       # Recon Cycle ID
       # -----------------------------------------
       cycle_id = uuid.uuid4().hex[:8]

       logger.info(f"[ReconCycle={cycle_id}] 🔄 RECON STARTED")

       open_orders = self.order_repo.fetch_open_orders()
       logger.info(
           f"[ReconCycle={cycle_id}] 📦 Open orders fetched: {len(open_orders)}"
       )

       for order in open_orders:

           logger.info(
               f"[ReconCycle={cycle_id}] ➡ Processing "
               f"OrderID={order['id']} | "
               f"Status={order['status']} | "
               f"Broker={order['broker']} | "
               f"BrokerOrderID={order['broker_order_id']}"
               f"broker_unique_id={order['broker_unique_id']}"
           )

           if order["status"] in ("COMPLETE", "CANCELLED", "REJECTED"):
               logger.info(
                   f"[ReconCycle={cycle_id}] ⏭ Skipping final state order "
                   f"| OrderID={order['id']}"
               )
               continue

           broker = order["broker"]
           adapter = self.adapters.get(broker)

           if not adapter:
               logger.warning(
                   f"[ReconCycle={cycle_id}] ⚠ No adapter found "
                   f"| Broker={broker}"
               )
               continue

           logger.debug(
               f"[ReconCycle={cycle_id}] 🔌 Adapter resolved "
               f"| Broker={broker} | "
               f"AdapterClass={adapter.__class__.__name__}"
           )

           try:
               # -----------------------------------------
               # Fetch broker execution status
               # -----------------------------------------
               logger.info(
                   f"[ReconCycle={cycle_id}] 📡 Calling "
                   f"adapter.get_order_status "
                   f"| BrokerOrderID={order['broker_order_id']}"
                    f"| broker_unique_id={order['broker_unique_id']}"
               )

               details = adapter.get_order_status(broker_order_id=order["broker_order_id"],broker_unique_id=order["broker_unique_id"])
               logger.info(
                   f"[ReconCycle={cycle_id}] 📥 Adapter response received "
                   f"| OrderID={order['id']} | Response={details}"
               )

               # -----------------------------------------
               # Parse broker response
               # -----------------------------------------
               final_status = details["status"]
               filled_qty = int(details.get("filled_qty", 0))
               avg_price = float(details.get("avg_price", 0))
               rejection_reason = details.get("rejection_reason")

               logger.debug(
                   f"[ReconCycle={cycle_id}] 📊 Parsed broker data "
                   f"| status={final_status} "
                   f"| filled_qty={filled_qty} "
                   f"| avg_price={avg_price} "
                   f"| rejection_reason={rejection_reason}"
               )

               # -----------------------------------------
               # Skip if no change
               # -----------------------------------------
               if (
                   order["status"] == final_status
                   and order["filled_qty"] == filled_qty
                   and float(order.get("avg_price", 0)) == avg_price
               ):
                   logger.debug(
                       f"[ReconCycle={cycle_id}] 🟰 No change detected "
                       f"| OrderID={order['id']}"
                   )
                   self.order_repo.touch_reconciled(order["id"])
                   continue

               logger.info(
                   f"[ReconCycle={cycle_id}] 🔁 Status Change "
                   f"| OrderID={order['id']} "
                   f"| {order['status']} → {final_status}"
               )

               # =========================================
               # HANDLE REJECTED
               # =========================================
               if final_status == "REJECTED":

                   logger.warning(
                       f"[ReconCycle={cycle_id}] ❌ Order Rejected "
                       f"| OrderID={order['id']} "
                       f"| Reason={rejection_reason}"
                   )

                   self.order_repo.mark_rejected(
                       order_id=order["id"],
                       reason=rejection_reason
                   )

                   if order["side"] == "ENTRY":
                       self.trade_repo.invalidate_trade(
                           trade_id=order["trade_id"],
                           reason=rejection_reason or "Entry Rejected",
                           status="REJECTED"
                       )

                   self.order_repo.touch_reconciled(order["id"])
                   continue

               # =========================================
               # HANDLE CANCELLED
               # =========================================
               if final_status == "CANCELLED":

                   logger.info(
                       f"[ReconCycle={cycle_id}] 🚫 Order Cancelled "
                       f"| OrderID={order['id']}"
                   )

                   self.order_repo.update_status(
                       order_id=order["id"],
                       status="CANCELLED"
                   )

                   self.order_repo.touch_reconciled(order["id"])
                   continue

               # =========================================
               # UPDATE ORDER TABLE
               # =========================================
               logger.debug(
                   f"[ReconCycle={cycle_id}] 📝 Updating order table "
                   f"| OrderID={order['id']}"
               )

               self.order_repo.update_fill_details(
                   order_id=order["id"],
                   filled_qty=filled_qty,
                   avg_price=avg_price,
                   status=final_status
               )

               # =========================================
               # UPDATE BROKER EXECUTION TABLE
               # =========================================
               logger.debug(
                   f"[ReconCycle={cycle_id}] 🏦 Updating broker execution table "
                   f"| BrokerOrderID={order['broker_order_id']}"
               )

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

                   logger.info(
                       f"[ReconCycle={cycle_id}] 🟢 ENTRY COMPLETE "
                       f"| TradeID={order['trade_id']} "
                       f"| qty={filled_qty} "
                       f"| avg={avg_price}"
                   )

                   locked_capital = round(avg_price * filled_qty, 2)

                   logger.info(
                       f"[ReconCycle={cycle_id}] 💰 Deducting capital "
                       f"| Amount={locked_capital}"
                   )

                   self.trade_repo.settings_repo.adjust_available_swing_capital(
                       -locked_capital
                   )

                   self.trade_repo.update_entry_fill(
                       trade_id=order["trade_id"],
                       fill_qty=filled_qty,
                       fill_price=avg_price
                   )

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
                       logger.warning(
                           f"[ReconCycle={cycle_id}] ⚠ Exit trade not found "
                           f"| TradeID={order['trade_id']}"
                       )
                       self.order_repo.touch_reconciled(order["id"])
                       continue

                   remaining_qty = int(trade["remaining_qty"])

                   logger.info(
                       f"[ReconCycle={cycle_id}] 🔴 EXIT COMPLETE "
                       f"| TradeID={order['trade_id']} "
                       f"| exit_qty={filled_qty} "
                       f"| remaining_before={remaining_qty}"
                   )

                   if filled_qty < remaining_qty:

                       logger.info(
                           f"[ReconCycle={cycle_id}] 📉 Partial Exit detected"
                       )

                       self.trade_repo.mark_partial_exit(
                           trade_id=order["trade_id"],
                           exit_qty=filled_qty,
                           exit_price=avg_price,
                           reason="Broker Exit Fill"
                       )

                   else:

                       logger.info(
                           f"[ReconCycle={cycle_id}] 🏁 Full Exit detected"
                       )

                       self.trade_repo.close_and_archive(
                           trade_id=order["trade_id"],
                           exit_price=avg_price,
                           exit_reason="Broker Exit Fill"
                       )

               # -----------------------------------------
               # Final touch
               # -----------------------------------------
               self.order_repo.touch_reconciled(order["id"])

               logger.debug(
                   f"[ReconCycle={cycle_id}] ✅ Order reconciliation completed "
                   f"| OrderID={order['id']}"
               )

           except Exception as e:

               logger.error(
                   f"[ReconCycle={cycle_id}] ❌ Recon error "
                   f"| OrderID={order['id']} "
                   f"| Error={str(e)}"
               )

               self.order_repo.mark_recon_error(
                   order_id=order["id"],
                   error=str(e)
               )

       logger.info(f"[ReconCycle={cycle_id}] 🏁 RECON FINISHED")