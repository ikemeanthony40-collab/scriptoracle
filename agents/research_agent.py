"""
ScriptOracle — Research Agent
Accepts a research query, performs research via Gemini AI,
and returns a structured JSON with summary, key_points, and citations.
"""

import asyncio
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from google import genai
from croo import AgentClient, Config, DeliverOrderRequest, DeliverableType, EventType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RESEARCH] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

CROO_API_URL  = os.environ.get("CROO_API_URL", "https://api.croo.network")
CROO_WS_URL   = os.environ.get("CROO_WS_URL",  "wss://api.croo.network/ws")
SDK_KEY       = os.environ["CROO_SDK_KEY_RESEARCH"]
GEMINI_KEY    = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL  = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

gemini_client = genai.Client(api_key=GEMINI_KEY)

def run_research(query: str) -> dict:
    prompt = f"""Research the following topic thoroughly.

Topic: {query}

Return ONLY a valid JSON object with these exact keys:
- "summary": a 2-3 sentence overview of the topic
- "key_points": a list of 4-6 specific findings or facts
- "citations": a list of relevant source URLs or references

Do not include markdown, code fences, or any text outside the JSON object."""

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    result_text = response.text.strip()

    try:
        cleaned = result_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        parsed = {
            "summary": result_text[:500],
            "key_points": [],
            "citations": [],
        }

    return parsed


async def main():
    config = Config(base_url=CROO_API_URL, ws_url=CROO_WS_URL)
    client = AgentClient(config=config, sdk_key=SDK_KEY)

    logger.info("Connecting WebSocket...")
    stream = await client.connect_websocket()
    logger.info("Research Agent online — waiting for orders.")

    active_orders: set[str] = set()

    def on_negotiation(event):
        logger.info("Negotiation received: %s", event.negotiation_id)
        asyncio.create_task(_accept(client, event.negotiation_id))

    def on_order_paid(event):
        order_id = event.order_id
        if order_id in active_orders:
            return
        active_orders.add(order_id)
        logger.info("Order paid — starting research: %s", order_id)
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
        logger.info("Research Agent shut down.")


async def _accept(client: AgentClient, negotiation_id: str):
    try:
        result = await client.accept_negotiation(negotiation_id)
        logger.info("Accepted negotiation → order_id=%s", result.order.order_id)
    except Exception as e:
        logger.error("Failed to accept negotiation %s: %s", negotiation_id, e)


async def _process_order(client: AgentClient, order_id: str, active_orders: set):
    try:
        order = await client.get_order(order_id)
        query = order.requirements or "General research request"
        logger.info("Research query: %s", query)

        result = run_research(query)
        logger.info("Research complete — %d key points", len(result.get("key_points", [])))

        deliver_req = DeliverOrderRequest(
            deliverable_type=DeliverableType.TEXT,
            deliverable_text=json.dumps(result),
        )
        deliver_result = await client.deliver_order(order_id, deliver_req)
        logger.info("Delivered order_id=%s tx_hash=%s", order_id, deliver_result.tx_hash)

    except Exception as e:
        logger.error("Error processing order %s: %s", order_id, e)
        try:
            await client.reject_order(order_id, str(e))
        except Exception as re:
            logger.error("Failed to reject order %s: %s", order_id, re)
    finally:
        active_orders.discard(order_id)


if __name__ == "__main__":
    asyncio.run(main())