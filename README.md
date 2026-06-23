# ScriptOracle — A2A Research Network on CAP

A three-agent paid research network built on the CROO Agent Protocol (CAP), where a human or another agent pays once to receive a fully sourced, independently verified research brief — with every intermediate transaction between agents settling on-chain.

## What It Does

ScriptOracle accepts a research query and orchestrates two specialist subagents via A2A orders:

1. **ScriptOracle Orchestrator** — receives the human's query, hires the Research and Verifier subagents on-chain, merges their outputs, and delivers a complete research brief
2. **ScriptOracle Research** — performs live AI-powered research and returns a structured JSON with summary, key points, and citations
3. **ScriptOracle Verifier** — cross-checks the research output, assigns a trust score (0–100), and flags unverified claims

Every sub-order follows the full CAP lifecycle: `negotiate_order → accept_negotiation → pay_order → deliver_order → settlement`. Each user query produces three on-chain transaction chains — a complete demonstration of A2A commerce depth.

## Architecture

```
Human Requester
      │
      │ H2A order (2.00 USDC)
      ▼
┌─────────────────────┐
│   ORCHESTRATOR      │
│  ScriptOracle Orch  │
└─────────┬───────────┘
          │
    ┌─────┴──────┐
    │            │
    │ A2A order  │ A2A order
    │ (0.60 USDC)│ (0.40 USDC)
    ▼            ▼
┌────────┐  ┌──────────┐
│RESEARCH│  │ VERIFIER │
│ Agent  │  │  Agent   │
└────────┘  └──────────┘
```

## Tracks Entered

- **Research & Intelligence Agents**
- **Data & Verification Agents**

## Agent Store Listings

| Agent | Service | Price |
|---|---|---|
| ScriptOracle Orchestrator | Deep Research Brief | $2.00 USDC |
| ScriptOracle Research | Web Research + Summary | $0.60 USDC |
| ScriptOracle Verifier | Claim Verification | $0.40 USDC |

## Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/ikemeanthony40-collab/scriptoracle.git
cd scriptoracle
```

### 2. Install dependencies

```bash
pip install croo-sdk google-genai python-dotenv
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```
CROO_API_URL=https://api.croo.network
CROO_WS_URL=wss://api.croo.network/ws

CROO_SDK_KEY_ORCHESTRATOR=your_orchestrator_sdk_key
CROO_SDK_KEY_RESEARCH=your_research_sdk_key
CROO_SDK_KEY_VERIFIER=your_verifier_sdk_key

ORCHESTRATOR_SERVICE_ID=your_orchestrator_service_id
RESEARCH_SERVICE_ID=your_research_service_id
VERIFIER_SERVICE_ID=your_verifier_service_id

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

### 4. Register agents on CROO

Register three agents at `agent.croo.network`:
- ScriptOracle Orchestrator (service: Deep Research Brief, $2.00, 1hr SLA)
- ScriptOracle Research (service: Web Research + Summary, $0.60, 20min SLA)
- ScriptOracle Verifier (service: Claim Verification, $0.40, 15min SLA)

### 5. Fund the Orchestrator wallet

Deposit at least 2 USDC on Base network to your Orchestrator agent's AA wallet address (visible in the CROO dashboard).

### 6. Run all three agents

Open three terminals:

```bash
# Terminal 1
python agents/research_agent.py

# Terminal 2
python agents/verifier_agent.py

# Terminal 3
python agents/orchestrator.py
```

## SDK Methods Used

| Method | Used by |
|---|---|
| `connect_websocket()` | All three agents |
| `accept_negotiation(negotiation_id)` | All three agents (provider role) |
| `negotiate_order(NegotiateOrderRequest)` | Orchestrator (requester role for subagents) |
| `pay_order(order_id)` | Orchestrator (requester role for subagents) |
| `get_order(order_id)` | All three agents |
| `deliver_order(order_id, DeliverOrderRequest)` | All three agents |
| `get_delivery(order_id)` | Orchestrator (fetches subagent results) |

## CAP Integration Notes

- 3 agents, 3 independent CAP service registrations on CROO Agent Store
- A2A composability: Orchestrator acts as requester to both Research and Verifier subagents
- Each research query produces 3 on-chain settlement transactions on Base
- Subagents are independently callable by any other builder on the Agent Store
- WebSocket event-driven architecture using NEGOTIATION_CREATED and ORDER_PAID events

## Sample Output

```json
{
  "query": "Latest developments in renewable energy in Africa",
  "summary": "Africa is experiencing rapid growth in solar and wind energy...",
  "key_points": [
    "Nigeria added 200MW of solar capacity in 2025",
    "Kenya leads East Africa in geothermal energy production"
  ],
  "citations": ["https://irena.org/africa", "https://iea.org/regions/africa"],
  "trust_score": 82,
  "verified_claims": ["Kenya leads East Africa in geothermal energy"],
  "unverified_claims": ["Nigeria added 200MW of solar capacity in 2025"],
  "overall_assessment": "Research is generally reliable with minor unverified statistics.",
  "generated_at": "2026-06-23T06:15:00Z"
}
```

## License

MIT
