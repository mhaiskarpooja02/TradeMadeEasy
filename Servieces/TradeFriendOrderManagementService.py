# Services/TradeFriendOrderManagementService.py

from utils.logger import get_brokerorder_logger

from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

from models.tradefriend_order_models import TradeFriendOrderRequest
from models.tradefriend_execution_result import TradeFriendExecutionResult

from core.tradefriend_broker_resolver import TradeFriendBrokerResolver

logger = get_brokerorder_logger()


class TradeFriendOrderManagementService:
    """
    ENTERPRISE ENTRY OMS

    Responsibilities:
    - Execute ENTRY orders only
    - Maintain broker_trade table
    - Maintain order_audit table
    - Paper + Live symmetry
    - Idempotent safe execution
    - Failover between brokers
    - PnL agnostic
    """

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):

        logger.debug("🔧 OMS INITIALIZING")

        self.broker_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.settings_repo = TradeFriendSettingsRepo()

        # Broker adapters
        self.brokers = {
            "ANGEL": TradeFriendAngelOrderAdapter(),
            "DHAN": TradeFriendDhanOrderAdapter()
        }

        # Broker policy resolver
        self.resolver = TradeFriendBrokerResolver(self.settings_repo)

        logger.debug(f"Available brokers → {list(self.brokers.keys())}")

    # =====================================================
    # PUBLIC ENTRY METHOD
    # =====================================================
    def place_entry_order(
        self,
        trade_id: int,
        symbol: str,
        qty: int,
        side: str,
        price: float
    ) -> list[dict]:

        logger.info(
            f"🚀 ENTRY START | trade_id={trade_id} | symbol={symbol} | qty={qty} | side={side}"
        )

        executions: list[dict] = []

        # =====================================================
        # 1️⃣ STATE GUARD
        # =====================================================
        trade = self.trade_repo.fetch_by_id(trade_id)

        if not trade:
            logger.error(f"❌ Trade not found | trade_id={trade_id}")
            return executions

        if trade.get("status") not in ("PENDING", "ENTRY_IN_PROGRESS"):
            logger.warning(
                f"⏭ ENTRY BLOCKED | trade_id={trade_id} | status={trade.get('status')}"
            )
            return executions

        # =====================================================
        # 2️⃣ IDEMPOTENCY CHECK
        # =====================================================
        existing_positions = self.broker_repo.fetch_active_positions(trade_id)

        if existing_positions:
            logger.warning(
                f"⚠ ENTRY SKIPPED | trade_id={trade_id} already has active broker position"
            )
            return executions

        # =====================================================
        # 3️⃣ MODE RESOLUTION
        # =====================================================
        order_mode = self.settings_repo.get_trade_mode()
        logger.info(f"Order mode resolved → {order_mode}")

        # =====================================================
        # 4️⃣ AUDIT ATTEMPT
        # =====================================================
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

        # =====================================================
        # 5️⃣ PAPER MODE
        # =====================================================
        if order_mode == "PAPER":

            logger.info("📄 Executing PAPER ENTRY")

            broker_trade_id = self.broker_repo.insert_broker_trade(
                trade_id=trade_id,
                broker="PAPER",
                order_mode="PAPER",
                symbol=symbol,
                leg_type="ENTRY",
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

            try:

                broker_order_id = f"PAPER-{broker_trade_id}"

                self.broker_repo.mark_order_success(
                    broker_trade_id=broker_trade_id,
                    broker_order_id=broker_order_id,
                    response_payload={
                        "filled_qty": qty,
                        "avg_price": price
                    }
                )

                executions.append({
                    "broker": "PAPER",
                    "broker_trade_id": broker_trade_id,
                    "filled_qty": qty,
                    "avg_price": price,
                    "broker_order_id": broker_order_id
                })

                self.audit_repo.log_result(
                    audit_id=audit_id,
                    status="SUCCESS",
                    response_payload={"mode": "PAPER"}
                )

                logger.info(f"✅ PAPER SUCCESS | trade_id={trade_id}")

            except Exception as e:

                logger.exception("❌ PAPER ENTRY FAILED")

                self.broker_repo.mark_order_failed(
                    broker_trade_id=broker_trade_id,
                    error_message=str(e)
                )

                self.audit_repo.log_result(
                    audit_id=audit_id,
                    status="FAILED",
                    error_message=str(e)
                )

            return executions

        # =====================================================
        # 6️⃣ LIVE MODE
        # =====================================================
        logger.info("🌐 Executing LIVE ENTRY")

        order_request = TradeFriendOrderRequest(
            trade_id=trade_id,
            symbol=symbol,
            qty=qty,
            side=side,
            order_mode="LIVE"
        )

        success = False

        # Resolve brokers using policy layer
        resolved_brokers = self.resolver.resolve_live_brokers(self.brokers)

        logger.info(f"Resolved brokers → {resolved_brokers}")

        if not resolved_brokers:
            logger.error("❌ No enabled brokers available")

            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message="No enabled brokers available"
            )

            return executions

        for broker_name in resolved_brokers:

            adapter = self.brokers.get(broker_name)

            logger.info(
                f"🔎 Evaluating broker | trade_id={trade_id} | broker={broker_name}"
            )

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

                result: TradeFriendExecutionResult = adapter.place_order(order_request)

                if not result.success:

                    logger.warning(
                        f"⚠ Broker rejected order | broker={broker_name} | error={result.error}"
                    )

                    self.broker_repo.mark_order_failed(
                        broker_trade_id=broker_trade_id,
                        error_message=result.error
                    )

                    continue

                # SUCCESS
                self.broker_repo.mark_order_success(
                    broker_trade_id=broker_trade_id,
                    broker_order_id=result.broker_order_id,
                    response_payload=result.raw_response
                )

                executions.append({
                    "broker": broker_name,
                    "broker_trade_id": broker_trade_id,
                    "filled_qty": result.filled_qty,
                    "avg_price": result.avg_price,
                    "broker_order_id": result.broker_order_id
                })

                logger.info(
                    f"✅ LIVE SUCCESS | broker={broker_name} | trade_id={trade_id}"
                )

                success = True
                break  # Failover stops after first success

            except Exception as e:

                logger.exception(
                    f"❌ Broker execution crashed | broker={broker_name}"
                )

                self.broker_repo.mark_order_failed(
                    broker_trade_id=broker_trade_id,
                    error_message=str(e)
                )

                continue

        # =====================================================
        # 7️⃣ AUDIT RESULT
        # =====================================================
        if success:

            self.audit_repo.log_result(
                audit_id=audit_id,
                status="SUCCESS",
                response_payload={"executions": executions}
            )

        else:

            logger.error(f"❌ ALL BROKERS FAILED | trade_id={trade_id}")

            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message="All brokers failed"
            )

        return executions