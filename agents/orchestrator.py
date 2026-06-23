"""
ScriptOracle — Orchestrator Agent
Receives human research queries, hires Research + Verifier subagents via A2A,
merges their outputs, and delivers a complete research brief.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from croo import AgentClient, Config, DeliverOrderRequest, DeliverableType, EventType
from croo import NegotiateOrderRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCHESTRATOR] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

CROO_API_URL         = os.environ.get("CROO_API_URL", "https://api.croo.network")
CROO_WS_URL          = os.environ.get("CROO_WS_URL",  "wss://api.croo.network/ws")
SDK_KEY              = os.environ["CROO_SDK_KEY_ORCHESTRATOR"]
RESEARCH_SERVICE_ID  = os.environ["RESEARCH_SERVICE_ID"]
VERIFIER_SERVICE_ID  = os.environ["VERIFIER_SERVICE_ID"]


async def call_subagent(
    client: AgentClient,
    service_id: str,
    requirements: str,
    label: str,
) -> dict:
    """Place an A2A order to a subagent and wait for delivery."""

    logger.info("[%s] Negotiating with service_id=%s", label, service_id)

    # Step 1 — negotiate
    neg_req = NegotiateOrderRequest(
        service_id=service_id,
        requirements=requirements,
    )
    neg_result = await client.negotiate_order(neg_req)
    order_id = neg_result.order.order_id
    logger.info("[%s] Negotiation accepted → order_id=%s", label, order_id)

    # Step 2 — pay
    pay_result = await client.pay_order(order_id)
    logger.info("[%s] Payment sent → status=%s", label, pay_result.order.status)

    # Step 3 — poll for completion
    logger.info("[%s] Waiting for delivery...", label)
    for attempt in range(60):
        await asyncio.sleep(5)
        order = await client.get_order(order_id)
        status = order.status
        logger.info("[%s] Poll %d — status=%s", label, attempt + 1, status)
        if status in ("completed", "COMPLETED", "delivered", "DELIVERED"):
            break
        if status in ("failed", "FAILED", "rejected", "REJECTED", "cancelled", "CANCELLED"):
            raise RuntimeError(f"{label} subagent order failed with status: {status}")

    # Step 4 — retrieve delivery
    delivery = await client.get_delivery(order_id)
    raw = delivery.deliverable_text or "{}"
    logger.info("[%s] Delivery received — %d chars", label, len(raw))

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_output": raw}


async def main():
    config = Config(base_url=CROO_API_URL, ws_url=CROO_WS_URL)
    client = AgentClient(config=config, sdk_key=SDK_KEY)

    logger.info("Connecting WebSocket...")
    stream = await client.connect_websocket()
    logger.info("Orchestrator Agent online — waiting for orders.")

    active_orders: set[str] = set()

    def on_negotiation(event):
        logger.info("Negotiation received: %s", event.negotiation_id)
        asyncio.create_task(_accept(client, event.negotiation_id))

    def on_order_paid(event):
        order_id = event.order_id
        if order_id in active_orders:
            return
        active_orders.add(order_id)
        logger.info("Order paid — starting orchestration: %s", order_id)
        asyncio.create_task(_process_order(client, order_id, active_orders))

    stream.on(EventType.NEGOTIATION_CREATED, on_negotiation)
    stream.on(EventType.ORDER_PAID, on_order_paid)

    try:
        while True:
            await asyncio.sleep(1)
            if stream.err():
                logger.error("WebSocket error: %s", stream.err())
                break
    except asyncio.CancelledError:
        pass
    finally:
        await stream.close()
        await client.close()
        logger.info("Orchestrator shut down.")


async def _accept(client: AgentClient, negotiation_id: str):
    try:
        result = await client.accept_negotiation(negotiation_id)
        logger.info("Accepted negotiation → order_id=%s", result.order.order_id)
    except Exception as e:
        logger.error("Failed to accept negotiation %s: %s", negotiation_id, e)


async def _process_order(client: AgentClient, order_id: str, active_orders: set):
    try:
        # Get the human's query
        order = await client.get_order(order_id)
        query = order.requirements or "General research request"
        logger.info("Human query: %s", query)

        # Step 1 — hire Research Agent
        research_result = await call_subagent(
            client=client,
            service_id=RESEARCH_SERVICE_ID,
            requirements=query,
            label="RESEARCH",
        )
        logger.info("Research result received — summary length=%d",
                    len(research_result.get("summary", "")))

        # Step 2 — hire Verifier Agent with research output as input
        verification_result = await call_subagent(
            client=client,
            service_id=VERIFIER_SERVICE_ID,
            requirements=json.dumps(research_result),
            label="VERIFIER",
        )
        logger.info("Verification result received — trust_score=%s",
                    verification_result.get("trust_score"))

        # Step 3 — merge into final brief
        final_brief = {
            "query": query,
            "summary": research_result.get("summary", ""),
            "key_points": research_result.get("key_points", []),
            "citations": research_result.get("citations", []),
            "trust_score": verification_result.get("trust_score", 0),
            "verified_claims": verification_result.get("verified_claims", []),
            "unverified_claims": verification_result.get("unverified_claims", []),
            "overall_assessment": verification_result.get("overall_assessment", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "Final brief ready — trust_score=%s verified=%d unverified=%d",
            final_brief["trust_score"],
            len(final_brief["verified_claims"]),
            len(final_brief["unverified_claims"]),
        )

        # Step 4 — deliver to human requester
        deliver_req = DeliverOrderRequest(
            deliverable_type=DeliverableType.TEXT,
            deliverable_text=json.dumps(final_brief, indent=2),
        )
        deliver_result = await client.deliver_order(order_id, deliver_req)
        logger.info("Final brief delivered — tx_hash=%s", deliver_result.tx_hash)

    except Exception as e:
        logger.error("Orchestration failed for order %s: %s", order_id, e)
        try:
            await client.reject_order(order_id, str(e))
        except Exception as re:
            logger.error("Failed to reject order %s: %s", order_id, re)
    finally:
        active_orders.discard(order_id)


if __name__ == "__main__":
    asyncio.run(main())