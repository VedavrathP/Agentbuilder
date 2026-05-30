# Orchestra — AI Agent Orchestration Platform

A locally-runnable platform where you create AI agents, configure how they think and act, wire them into visual workflows on a drag-and-drop canvas, execute those workflows on a real LangGraph runtime, and chat with one of them live through Telegram. Every run is streamed to the UI in real time — tokens, tool calls, inter-agent handoffs, and token/cost.

---

## Table of contents

1. [Stack and why](#stack-and-why)
2. [Quickstart](#quickstart)
3. [Demo script](#demo-script)
4. [Repository layout](#repository-layout)
5. [How it works](#how-it-works)
6. [Extending the platform](#extending-the-platform)
7. [Testing](#testing)
8. [Spec coverage](#spec-coverage)

---

## Stack and why

The backend is **Python 3.11 + FastAPI 0.115** because the AI tooling ecosystem (LangGraph, LangChain, OpenAI) is Python-first, and FastAPI gives native async, OpenAPI docs, dependency injection, and SSE via `sse-starlette`. The runtime is **LangGraph 1.2** because it is the only option that can compile a user-defined visual graph from JSON, persist durable Postgres checkpoints with thread-based resumption, and stream per-event progress (tokens, tool calls, node transitions). CrewAI lacks conditional routing, AutoGen is chat-only, and a custom runtime would reinvent persistence and streaming for no benefit.

LLM calls go to **OpenAI** (`gpt-4o-mini`, `gpt-4o`) for reliable tool calling, well-documented pricing for the cost-tracking requirement, and fast streaming — switching providers is one config line per agent (see "Add an LLM provider" below). The external channel is **Telegram** via `python-telegram-bot 22.x` in polling mode, because a single token from `@BotFather` is enough to demo: no webhooks, no ngrok, no business verification (which both WhatsApp and Slack require).

Persistence is **Postgres 16** with `AsyncPostgresSaver` — one database for everything, app rows via SQLAlchemy 2.0 async and LangGraph checkpoint tables via psycopg3, same instance, same backups. **Redis 7** handles pub/sub plus a capped stream so the executor is decoupled from SSE subscribers, multiple browser tabs can watch the same run, and a late subscriber can replay recent history. The frontend is **Next.js 15 + Tailwind + shadcn/ui** (modern and polished out of the box, with shadcn components copy-pasted into the repo so there is no runtime dependency on a UI library) and **`@xyflow/react` 12 (React Flow)**, the de-facto library for node-graph editors. The whole thing boots with **`docker-compose`** — Postgres, Redis, backend, and frontend come up together with health-checked dependencies, satisfying the spec's "single setup command" requirement.

Out of scope, called out explicitly: multi-tenant auth (single-user local tool), cloud deployment (spec says "fully local"), voice channels, and fine-tuning.

---

## Quickstart

Prerequisites: Docker Desktop and an OpenAI API key.

```bash
# 1. Configure (one time)
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 2. Run everything
docker compose up --build
```

This boots Postgres 16 on **localhost:5433** (5432 is often taken on dev machines), Redis 7 on **localhost:6380**, the FastAPI + LangGraph backend on **localhost:8000**, and the Next.js frontend on **localhost:3000**. The Telegram supervisor runs inside the backend (no separate container) and reconciles `telegram_links` every 10 seconds. Open http://localhost:3000.

For faster local iteration without Docker: run `make install` to create the venv, `make db-up` to start Postgres and Redis only, `make migrate` to apply Alembic migrations, then `make backend-dev` and `make frontend-dev` in two terminals.

Verify the install:

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}

curl http://localhost:8000/api/workflows | jq '.[] | .name'
# "Research & Write"
# "Support Triage"
# "Draft & Critic (Loop)"
```

---

## Demo script

The platform ships with three seeded templates (the spec asks for at least two). The **Support Triage** workflow is what you'll connect to Telegram for the live demo.

**Demo A — "Research & Write" pipeline (sequential, with tool use).** Go to Workflows, click **Use template** on Research & Write, click **Run**, and enter `Research the latest news on LangGraph 1.2 release notes`. Watch the run page: the researcher node lights blue, you'll see `tool_call: web_search(...)` followed by streaming tokens, then the writer node activates and streams the final summary. Per-model and total cost appear in the right panel.

**Demo B — "Support Triage" via Telegram (the headline demo).** Create a bot in Telegram by chatting with `@BotFather`, sending `/newbot`, naming it (e.g. `OrchestraDemo`), and copying the token. In the Orchestra UI go to **Telegram**, pick the Support Triage workflow, paste the token, and click **Add bot**. Within ~10 seconds the supervisor will fetch the bot username and mark it `active`. Open the bot in Telegram and send `My invoice last month was $200 too high, please refund the difference`. The Telegram message is edited in place as tokens stream from the classifier and the billing agent. In the Orchestra UI go to **Dashboard → recent runs**, click the latest run, and you'll see the user message bubble, the classifier's JSON response, the billing agent's full streaming reply, the token & cost tally, and the event log on the right.

Try the other branch by sending `My app keeps crashing on login`: the classifier emits `intent=technical`, the JSON router routes to the tech agent, which streams its response. To verify persistence, stop everything with `docker compose down`, start again with `docker compose up`, and open the run again — full history is intact. Telegram threads keep the same `thread_id`, so the conversation continues where it left off.

**Demo C — "Draft & Critic" feedback loop (cyclic graph + guardrails).** Use the template, click **Run**, and enter `Write a short paragraph explaining why the sky is blue for a 10-year-old`. The writer node streams a first draft, the critic node emits a JSON verdict `{approved, feedback}`, and a `json_field` condition routes on `approved`: `false` loops control back to the writer with the critique, `true` advances to the finalizer, which publishes the approved text. Per-node iteration caps (`loop_max_iterations`) plus workflow-level `max_iterations` and `max_cost_usd` guardrails stop runaway revision loops — if a cap is hit the run ends with status `failed` and a `guardrail:` error instead of spinning forever.

A recorded version of this demo lives in `docs/demo.mp4` (drop your own here after recording).

---

## Repository layout

```
.
├── docker-compose.yml         # 4 services + healthchecks
├── Makefile                   # make install / db-up / migrate / backend-dev / test
├── .env.example
├── README.md                  # you are here
│
├── backend/
│   ├── pyproject.toml         # pinned versions (langgraph 1.2.1, langchain 1.3.1 ...)
│   ├── Dockerfile
│   ├── alembic/               # schema migrations
│   └── app/
│       ├── main.py            # FastAPI app + lifespan (checkpointer, seed, telegram supervisor, scheduler)
│       ├── config.py
│       ├── api/               # REST routers (agents, workflows, runs, telegram)
│       ├── db/                # models + session
│       ├── engine/            # LangGraph factory, agents, tools, routers, executor, orchestrator, usage, guardrails, memory
│       ├── channels/
│       │   └── telegram_bot.py
│       ├── events/bus.py      # Redis pub/sub + history stream
│       ├── scheduler.py       # APScheduler daemon (cron → workflow runs)
│       ├── templates/         # 3 pre-built workflow JSONs
│       ├── scripts/
│       └── tests/
│
└── frontend/
    ├── package.json
    ├── Dockerfile
    └── src/
        ├── app/               # dashboard, agents, workflows, runs, telegram pages
        ├── components/        # ui primitives + agent form + workflow editor + run monitor
        └── lib/               # api client, sse hook, types
```

---

## How it works

**Building a graph from JSON.** `backend/app/engine/factory.py` iterates `workflow.graph_json.nodes` and adds each agent node as a compiled `create_agent(...)` LangGraph. Condition nodes are *not* added as graph nodes — their preceding edge is converted into `builder.add_conditional_edges(source, router_fn, {target_id: target_id, ...})` using a router function from the `ROUTERS` registry. Terminal edges with `target == "__end__"` become `add_edge(source, END)`, and the entry node is wired to `START`. This means a user can draw an arbitrary directed graph in the React Flow canvas, save it, and it becomes a real LangGraph — no codegen, no eval.

**Streaming.** `backend/app/engine/executor.py` calls `graph.astream(..., stream_mode=["messages","updates"])` and translates LangGraph internals into a stable, frontend-friendly event schema:

```ts
type RunEvent =
  | { type: "run_start"; ... }
  | { type: "node_start"; node }
  | { type: "node_end"; node; error? }
  | { type: "token"; node; text }
  | { type: "tool_call"; node; name; args; tool_call_id }
  | { type: "tool_result"; node; name; content; tool_call_id }
  | { type: "agent_message"; node; role; content; token_usage }
  | { type: "usage"; input_tokens; output_tokens; cost_usd; per_model }
  | { type: "run_end"; status; error?; elapsed_ms };
```

The orchestrator (`engine/orchestrator.py`) runs the executor in a background task, publishes every event to Redis channel `run:{run_id}`, mirrors a short history in `run:{run_id}:history` (a capped Redis Stream so late subscribers replay), and persists `agent_message` and `tool_result` events to the `messages` table. The FastAPI SSE endpoint (`api/runs.py::stream_run`) just subscribes to that Redis channel and pipes JSON to the browser.

**Token & cost tracking.** `UsageMetadataCallbackHandler` is attached to **graph config** (NOT to the model — that would disable token streaming; this is a published LangGraph footgun, see https://github.com/langchain-ai/langgraph/issues/6394). `engine/usage.py` maps model names to USD prices and aggregates the per-model totals on `run_end`.

**Telegram channel.** `backend/app/channels/telegram_bot.py` runs a supervisor loop inside the FastAPI lifespan. Every 10 seconds it reads `TelegramLink` rows and starts/stops one `Application` per active link. Each bot's message handler maps `chat_id` to `thread_id = f"telegram:{workflow_id}:{chat_id}"` so each user gets a persistent conversation, calls the same executor used by the HTTP endpoint, edits a single Telegram message every ~800 ms with the accumulated buffered tokens (Telegram rate-limits `edit_message_text`; this is the documented mitigation), and persists messages to the same `messages` table so the UI shows Telegram conversations alongside web runs.

**Guardrails.** `engine/guardrails.py` collects limits from the workflow-level `guardrails` block and from every agent node (the strictest value wins), then the executor enforces them live: per-node visit caps and a total `max_iterations` count stop infinite loops, a rolling `max_cost_usd` check aborts a run once the accumulated OpenAI spend crosses the threshold, and `forbidden_topics` rejects matching input before any model call. A violation ends the run with status `failed` and a `guardrail:` error rather than throwing an unhandled exception.

**Memory & interaction rules.** `engine/memory.py` seeds each run according to the agent's `memory_strategy`: `thread` relies on the durable LangGraph checkpoint (full history per `thread_id`), `summary` fetches prior thread messages and condenses them into a system message once a threshold is crossed, and `none` runs stateless. An agent's `skills` and `interaction_rules` are folded into the system prompt in `engine/agents.py`, and workflow/entry-level interaction rules are injected as a leading system message.

**Scheduling.** `scheduler.py` runs an APScheduler `AsyncIOScheduler` started in the FastAPI lifespan. Any agent with a `schedule_cron` and a `default_workflow_id` registers a cron job; when it fires, the agent's `schedule_input` is fed to `start_run` with `trigger=schedule` on a stable `schedule:{agent_id}` thread. Creating, editing, or deleting an agent re-syncs the live job set, so schedules take effect without a restart.

---

## Extending the platform

**Add a new workflow template.** Drop a JSON file into `backend/app/templates/`. On next backend start the lifespan hook inserts/updates it. Schema:

```json
{
  "name": "Your name",
  "description": "...",
  "template_key": "snake_case_unique_key",
  "entry": "first_agent_id",
  "graph": {
    "nodes": [
      {"id": "agent1", "type": "agent", "position": {"x":0,"y":0},
       "data": {"system_prompt": "...", "model": "gpt-4o-mini", "temperature": 0.2, "tools": []}},
      {"id": "route", "type": "condition", "position": {"x":0,"y":0},
       "data": {"router": "keyword", "spec": {"branches": [...], "default": "..."}}}
    ],
    "edges": [
      {"id": "e1", "source": "agent1", "target": "route"},
      {"id": "e2", "source": "route", "target": "agent2"}
    ]
  }
}
```

**Add a new tool.** Create `backend/app/engine/tools/your_tool.py` with a `make_your_tool(config)` factory returning a `BaseTool` (use the `@tool` decorator), register it in `backend/app/engine/tools/__init__.py::TOOL_FACTORIES`, and add it to the dropdown in `frontend/src/components/workflow/properties-panel.tsx::TOOLS`.

**Add a new messaging channel.** Channels are just async functions that map external events to `start_run`. Create `backend/app/channels/my_channel.py`, implement a long-running async worker that calls `start_run(workflow=..., user_input=..., trigger=RunTrigger.api, thread_id=...)`, and start it from the FastAPI lifespan in `app/main.py`. Optionally add a `MyChannelLink` model + endpoint mirroring `TelegramLink` for dynamic configuration.

**Add an LLM provider.** Replace `ChatOpenAI` in `backend/app/engine/agents.py` with a provider switch based on `node_data["model"]`:

```python
if model_name.startswith("claude-"):
    llm = ChatAnthropic(model=model_name, ...)
elif model_name.startswith("ollama:"):
    llm = ChatOllama(model=model_name.split(":",1)[1], ...)
else:
    llm = ChatOpenAI(model=model_name, ...)
```

Add pricing to `engine/usage.py::PRICING_USD_PER_M_TOKENS`.

---

## Testing

```bash
make test-backend     # 28 tests, ~2s
make test-frontend    # next build (type checks all pages)
```

Backend tests cover the critical paths the spec demands. `test_api_agents` verifies the full agent CRUD roundtrip and workflow template instantiation against the FastAPI ASGI app. `test_factory` confirms that workflow JSON compiles into the right LangGraph shape, including condition-node elision into `add_conditional_edges`, pins the Support Triage template's JSON-routing contract, and asserts the Draft & Critic template wires a real cycle (writer → critic → route → writer/finalizer) with loop caps. `test_routers` exercises all three routers (keyword, regex, json_field), including extraction of JSON objects from prose. `test_executor` runs a minimal two-node graph with `GenericFakeChatModel` and asserts the event-emission shape without hitting OpenAI. `test_guardrails` proves limit extraction (strictest value wins) and live enforcement of per-node caps, total iterations, cost ceilings, and forbidden topics. `test_agents` proves an agent's skills and interaction rules reach the composed system prompt. `test_telegram_bridge` mocks `python-telegram-bot` and verifies the handler persists both user and assistant messages, edits the reply, and completes the run row. `test_usage` pins the cost-estimation math. The frontend's `npm run build` runs the TypeScript checker over every page and component, catching schema drift between `lib/types.ts` and the backend Pydantic schemas at build time.

---

## Spec coverage

Agent CRUD with name, role, prompt, model, tools, and channels is implemented in `backend/app/api/agents.py` and the agent detail page under `frontend/src/app/agents/[id]`, with channels surfaced through the `/telegram` link manager. The full agent-configuration surface is persisted on the `Agent` model and editable in the agent form: `schedule_cron` + `default_workflow_id` + `schedule_input` drive the APScheduler daemon, `memory_strategy` selects `thread`/`summary`/`none`, `skills` and `interaction_rules` are folded into the agent's system prompt, and `guardrails` (`max_iterations`, `max_cost_usd`, `forbidden_topics`, per-node `loop_max_iterations`) are enforced live by the executor. Each of these is a real, wired feature rather than a stored-only field.

The visual workflow builder with conditions and feedback loops is built on React Flow with custom Agent and Condition node types; cycles are allowed because the factory simply translates whatever directed graph the user draws. Three pre-built workflow templates ship in `backend/app/templates/` — `research_and_write.json` (sequential with the web_search tool), `support_triage.json` (deterministic JSON routing into one of two specialist agents), and `draft_and_critic.json` (a cyclic writer ↔ critic feedback loop with iteration and cost guardrails). The external channel requirement is satisfied by Telegram in polling mode with dynamic token registration.

Live monitoring (real-time logs, inter-agent messages, token and cost) is the SSE-driven `/runs/[id]` UI. Async agent communication is the default — all graph execution is async, and the handoff infrastructure for agent-to-agent transfer (`Command(goto=..., graph=Command.PARENT)`) is implemented in `engine/tools/handoff.py`. Persisted message history is exposed at `/api/runs/{id}/messages` and rendered in the run-monitor UI. The runtime is real (LangGraph 1.2 + OpenAI + DuckDuckGo + HTTP — not a mockup). Setup is one command (`docker compose up --build`). The 28 backend tests cover the critical paths. This README justifies the runtime choice and explains how to add new templates, tools, channels, and LLM providers.
