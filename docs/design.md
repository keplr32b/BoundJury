# BoundJury - Design

## Thesis

BoundJury is a GenLayer project for the agentic economy:

Seal plain-English **bounds** for an agent. Anyone submits public HTTPS evidence of an action. Validators fetch the pages and reach comparative consensus on a closed verdict — IN_BOUND, OUT_OF_BOUND, or INCONCLUSIVE. Only OUT_OF_BOUND sets `is_out_of_bound(action_id)`. Integrator contracts refuse privileged actions while the flag is set.

BoundJury does not forcibly stop arbitrary agent runtimes. It exposes a consensus-backed bound flag as an integration surface.

## Category

**Projects** (full application path: Intelligent Contract + consumer demo + documentation + live Studionet receipts; UI/demo site as part of the product).

Not a thin one-shot IC demo.

## Track fit

- Agentic commerce: did this action stay inside what the user allowed?
- Aligns with mandate / delegation judgment without requiring a specific wallet bridge in the core contract
- GenLayer-native: live HTTPS fetch + comparative consensus on closed labels

## Adversarial model

| False outcome | Who is hurt |
|---------------|-------------|
| False OUT_OF_BOUND | Agent/integrators freeze without real breach |
| False IN_BOUND | Breach continues while flag stays clear |
| Forced INCONCLUSIVE | Delay without unjustified freeze |

Mitigations: host allowlist, empty/failed fetch cannot produce OUT_OF_BOUND, dual-source optional (1–2 URLs), challenge window, comparative equivalence on verdict only, INCONCLUSIVE on challenge preserves an existing OUT_OF_BOUND.

## Lifecycle

```text
OWNER: allow_host → register_agent(agent_id, bounds_text, optional watch_url)
ANYONE: submit_evidence(action_id, agent_id, urls_csv)
ANYONE: adjudicate(action_id)
        → IN_BOUND | OUT_OF_BOUND | INCONCLUSIVE
        → only OUT_OF_BOUND sets flag + opens challenge window
ANYONE (while open): challenge(action_id, url)
        → IN_BOUND: lift flag
        → OUT_OF_BOUND: keep flag, finalize window
        → INCONCLUSIVE: keep flag (window stays coherent)
AFTER WINDOW: finalize_out(action_id)
OWNER: owner_clear_out(action_id)  // ops recovery only
INTEGRATOR: if is_out_of_bound(action_id): revert

## Verdicts

- IN_BOUND | OUT_OF_BOUND | INCONCLUSIVE
- Only OUT_OF_BOUND sets is_out_of_bound
- Note is non-binding for equivalence
- Empty or failed fetch must not yield OUT_OF_BOUND

## Challenge rule

On an already OUT_OF_BOUND action:

- IN_BOUND → lift flag, close window
- OUT_OF_BOUND → keep flag, finalize window
- INCONCLUSIVE → keep flag; do not treat as clear
- owner_clear_out → ops lift only

## Consensus

- Validators independently web.render evidence URLs
- LLM returns strict JSON with verdict + short note
- Equivalence: identical verdict (and sources_count); note may differ

## Integration

bj = gl.get_contract_at(boundjury_addr)
if bj.view().is_out_of_bound(action_id):
    raise  # refuse privileged act

Demo consumer: ExampleBoundAgent - act() / withdraw() gated on the flag.

## Core API

| Method | Who |
|--------|-----|
| `allow_host` / `register_agent` | Owner |
| `submit_evidence` (1–2 HTTPS URLs) | Anyone |
| `adjudicate` | Anyone |
| `challenge` | Anyone while challenge window open |
| `finalize_out` | Anyone after challenge window |
| `recheck` | Anyone if `watch_url` set |
| `owner_clear_out` | Owner (ops recovery only) |
| `is_out_of_bound` / `read_case` / `is_host_allowed` / `get_owner` | Views |

## Non-goals

- Forcing non-integrating agents or runtimes to halt
- Full MetaMask / x402 bridge inside the core contract (integrators may use the flag)
- Multi-sig council as the core path (challenge is evidence + consensus)
- Unlimited evidence URLs or a global agent radar
- Mainnet production SLA without audit and real integrators

## Limits

- Studionet development network, not a production SLA
- Owner controls host allowlist, agent registration, and ops clear
- Challenge window uses transaction-pinned time (demo window 300 seconds)
- One or two evidence URLs per adjudication cycle
- LLM judgment is point-in-time under closed verdict labels
- Soft enforce: integrators must call `is_out_of_bound` themselves

## Success criteria

1. Real allowlisted HTTPS evidence on Studionet
2. `IN_BOUND` path with a public docs-style page
3. `OUT_OF_BOUND` path with evidence that violates example bounds
4. Challenge returning `INCONCLUSIVE` preserves the out-flag
5. Challenge returning `IN_BOUND` lifts the out-flag
6. `ExampleBoundAgent` blocks `act` / `withdraw` when out of bound
7. Repo includes design, E2E receipts, and honest limits
8. Demo site / UI path suitable for **Projects** category review