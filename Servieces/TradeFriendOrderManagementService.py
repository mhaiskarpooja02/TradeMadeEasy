# Services/TradeFriendOrderManagementService.py

from db.TradeFriendOrderRepo import TradeFriendOrderRepo
from utils.logger import get_brokerorder_logger

from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

from models.tradefriend_order_models import TradeFriendOrderRequest
from core.tradefriend_broker_resolver import TradeFriendBrokerResolver

logger = get_brokerorder_logger()


class TradeFriendOrderManagementService:

    def __init__(self):

        self.broker_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.settings_repo = TradeFriendSettingsRepo()
        self.order_repo = TradeFriendOrderRepo()

        self.brokers = {
            "ANGEL": TradeFriendAngelOrderAdapter(),
            "DHAN": TradeFriendDhanOrderAdapter()
        }

        self.resolver = TradeFriendBrokerResolver(self.settings_repo)

    # =====================================================
    # ENTRY ORDER
    # =====================================================
    def place_entry_order(
        self,
        trade_id: int,
        symbol: str,
        qty: int,
        side: str,
        price: float
    ) -> list[dict]:

        executions = []

        trade = self.trade_repo.fetch_by_id(trade_id)
        if not trade:
            logger.error(f"Trade not found | trade_id={trade_id}")
            return executions

        if trade.get("status") not in ("PENDING", "ENTRY_IN_PROGRESS"):
            logger.warning(f"ENTRY BLOCKED | trade_id={trade_id}")
            return executions

        if self.broker_repo.fetch_active_positions(trade_id):
            logger.warning(f"Active position exists | trade_id={trade_id}")
            return executions

        order_mode = self.settings_repo.get_trade_mode()

        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="ENTRY_OMS",
            order_mode=order_mode,
            side=side,
            qty=qty,
            order_type="MARKET",
            request_payload={
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "price": price
            }
        )

        # ===========================
        # PAPER MODE
        # ===========================
        if order_mode == "PAPER":

            broker_trade_id = self.broker_repo.insert_broker_trade(
                trade_id=trade_id,
                broker="PAPER",
                order_mode="PAPER",
                symbol=symbol,
                leg_type="ENTRY",
                side=side,
                qty=qty,
                order_type="MARKET"
            )

            broker_order_id = f"PAPER-{broker_trade_id}"

            self.broker_repo.mark_order_success(
                broker_trade_id=broker_trade_id,
                broker_order_id=broker_order_id,
                response_payload={"simulated": True}
            )

            self.order_repo.insert_order(
                trade_id=trade_id,
                broker="PAPER",
                broker_order_id=broker_order_id,
                leg_type="ENTRY",
                order_mode="PAPER",
                side=side,
                qty=qty
            )

            self.audit_repo.log_result(audit_id, "SUCCESS", {})

            executions.append({
                "broker": "PAPER",
                "broker_trade_id": broker_trade_id,
                "broker_order_id": broker_order_id
            })

            return executions

        # ===========================
        # LIVE MODE
        # ===========================

        resolved_brokers = self.resolver.resolve_live_brokers(self.brokers)

        for broker_name in resolved_brokers:

            adapter = self.brokers.get(broker_name)

            broker_trade_id = self.broker_repo.insert_broker_trade(
                trade_id=trade_id,
                broker=broker_name,
                order_mode="LIVE",
                symbol=symbol,
                leg_type="ENTRY",
                side=side,
                qty=qty,
                order_type="MARKET"
            )

            try:

                order_request = TradeFriendOrderRequest(
                    trade_id=trade_id,
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    order_mode="LIVE"
                )

                result = adapter.place_order(order_request)

                # Broker ACCEPTED order
                if result.success and result.broker_order_id:

                    self.broker_repo.mark_order_success(
                        broker_trade_id=broker_trade_id,
                        broker_order_id=result.broker_order_id,
                        response_payload=result.raw_response
                    )

                    self.order_repo.insert_order(
                        trade_id=trade_id,
                        broker=broker_name,
                        broker_order_id=result.broker_order_id,
                        leg_type="ENTRY",
                        order_mode="LIVE",
                        side=side,
                        qty=qty
                    )

                    executions.append({
                        "broker": broker_name,
                        "broker_trade_id": broker_trade_id,
                        "broker_order_id": result.broker_order_id
                    })

                    self.audit_repo.log_result(audit_id, "SUCCESS", {})

                    return executions

                else:
                    self.broker_repo.mark_order_failed(
                        broker_trade_id,
                        result.error or "Rejected"
                    )

            except Exception as e:

                # Timeout / Unknown state
                self.broker_repo.mark_order_unknown(
                    broker_trade_id,
                    str(e)
                )

        self.audit_repo.log_result(audit_id, "FAILED", {"reason": "All brokers failed"})
        return executions