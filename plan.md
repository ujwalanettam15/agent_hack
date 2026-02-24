# LifePilot — Build Plan

## Status Tracker

| Component | Status | Notes |
|-----------|--------|-------|
| Vapi Assistant | DONE | ID stored in VAPI_ASSISTANT_ID env var |
| Vapi Tools (5x) | DONE | Standalone tools created, linked via `toolIds`, URLs pointed to Render |
| Vapi MCP + API Key | DONE | Configured in `.claude.json` |
| FastAPI Backend | DONE | Built + tested locally, 15 files, all endpoints verified |
| Render Deployment | IN PROGRESS | URL: `https://agenthackathon.onrender.com`, root dir needs `backend` |
| GitHub Repo | DONE | `https://github.com/neelb1/agenthackathon` |
| Vapi URLs Updated | DONE | Assistant + all 5 tools pointed to Render URL |
| Neo4j AuraDB | TODO | Free tier, no credit card |
| Tavily Integration | DONE (code) | Service written, needs API key in Render env vars |
| Hume AI Integration | TODO | Free tier, WebSocket API |
| React Dashboard | TODO | 3-panel layout |
| Demo Script | TODO | Pre-record + live backup |

---

## Architecture (6 Layers)

```
Layer 1: MONITORING (eyes)     — Yutori Scouts + Tavily Search
Layer 2: TASK ENGINE (brain)   — FastAPI on Render
Layer 3: VOICE AGENT (mouth)   — Vapi + Deepgram + Groq + ElevenLabs
Layer 4: KNOWLEDGE GRAPH (mem) — Neo4j AuraDB + Graphiti
Layer 5: EMOTION (intuition)   — Hume AI WebSocket
Layer 6: DASHBOARD (face)      — React + Neovis.js + SSE
```

---

## Phase 1: Backend (FastAPI on Render)

**Goal**: Get the server that Vapi talks to running. This unblocks everything else.

### File Structure

```
backend/
  main.py              # FastAPI app, CORS, startup
  routers/
    vapi_webhook.py    # POST /api/vapi/webhook — receives Vapi events
    vapi_tools.py      # POST /api/vapi/tool-call — handles all 5 tool calls
    tasks.py           # GET/POST /api/tasks — task CRUD + trigger calls
    sse.py             # GET /api/events — SSE stream for dashboard
  services/
    neo4j_service.py   # Neo4j driver, Cypher queries, graph updates
    tavily_service.py  # Tavily search + extract wrappers
    vapi_service.py    # Outbound call triggering via Vapi API
    task_store.py      # In-memory task store (swap to DB later)
  models/
    schemas.py         # Pydantic models for all request/response types
  config.py            # Env vars: VAPI_API_KEY, NEO4J_URI, TAVILY_API_KEY, etc.
  requirements.txt
  render.yaml
```

### Key Endpoints

#### `POST /api/vapi/webhook`
Receives ALL Vapi server messages: `end-of-call-report`, `status-update`, `transcript`, `conversation-update`, `speech-update`.

```python
@router.post("/api/vapi/webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    msg_type = body.get("message", {}).get("type")

    if msg_type == "end-of-call-report":
        # Extract structured analysis, save to task store + Neo4j
        pass
    elif msg_type == "transcript":
        # Push to SSE for live dashboard
        pass
    elif msg_type == "status-update":
        # Track call state (ringing, in-progress, ended)
        pass

    # CRITICAL: Always return 200, even on errors
    return {"status": "ok"}
```

#### `POST /api/vapi/tool-call`
Single endpoint that routes all 5 tool calls. Vapi sends the tool name + args, we switch on `function.name`.

```python
@router.post("/api/vapi/tool-call")
async def vapi_tool_call(request: Request):
    body = await request.json()
    message = body.get("message", {})
    tool_calls = message.get("toolCallList", [])

    results = []
    for tool_call in tool_calls:
        name = tool_call["function"]["name"]
        args = json.loads(tool_call["function"]["arguments"])
        tool_call_id = tool_call["id"]

        if name == "search_task_context":
            result = await handle_search_task_context(args["task_id"])
        elif name == "tavily_search":
            result = await handle_tavily_search(args["query"])
        elif name == "extract_entities":
            result = await handle_extract_entities(args)
        elif name == "update_neo4j":
            result = await handle_update_neo4j(args)
        elif name == "end_task":
            result = await handle_end_task(args)

        results.append({
            "toolCallId": tool_call_id,  # MUST match exactly
            "result": str(result)         # MUST be single-line string
        })

    return {"results": results}
```

**Critical Vapi gotchas** (from docs):
- Always return HTTP 200, even for errors
- `toolCallId` must match the incoming ID exactly
- Result must be a single-line string (no line breaks)
- Increase `maxTokens` beyond default 100 for complex tool responses

#### `POST /api/tasks`
Creates a task and optionally triggers a Vapi outbound call.

```python
# Trigger outbound call via Vapi API
POST https://api.vapi.ai/call
{
    "phoneNumberId": "your-vapi-phone-number-id",
    "assistantId": "683ebace-9e80-430e-b1a4-4d41a635114a",
    "customer": { "number": "+1234567890" },
    "assistantOverrides": {
        "variableValues": {
            "taskId": "task_001",
            "customerName": "Neel",
            "targetCompany": "Comcast",
            "objective": "negotiate_rate",
            "currentRate": "85",
            "targetRate": "65"
        }
    }
}
```

#### `GET /api/events`
Server-Sent Events stream. Dashboard connects here for real-time updates.

```python
@router.get("/api/events")
async def sse_stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            event = await event_queue.get()
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Render Deployment

**Type**: Web Service (NOT static site)
**Build Command**: `pip install -r requirements.txt`
**Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

```yaml
# render.yaml
services:
  - type: web
    name: lifepilot-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: VAPI_API_KEY
        sync: false
      - key: VAPI_PUBLIC_KEY
        sync: false
      - key: NEO4J_URI
        sync: false
      - key: NEO4J_USER
        sync: false
      - key: NEO4J_PASSWORD
        sync: false
      - key: TAVILY_API_KEY
        sync: false
      - key: HUME_API_KEY
        sync: false
```

```
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
neo4j==5.25.0
tavily-python==0.5.0
httpx==0.27.0
python-dotenv==1.0.1
sse-starlette==2.1.0
pydantic==2.9.0
```

---

## Phase 2: Neo4j Knowledge Graph

**Goal**: Live graph that grows during calls. THE demo wow-factor.

### Setup
1. Go to https://neo4j.com/cloud/aura-free/ — create AuraDB Free instance
2. Save URI, username, password as env vars
3. Takes < 3 minutes, no credit card

### Schema (Cypher)

```cypher
// Core entities
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT task_id IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT call_id IF NOT EXISTS FOR (c:Call) REQUIRE c.id IS UNIQUE;

// Example graph for demo
MERGE (user:Person {name: "Neel"})
MERGE (comcast:Service {name: "Comcast", type: "internet", monthlyRate: 85})
MERGE (planet:Service {name: "Planet Fitness", type: "gym", monthlyRate: 25})
MERGE (user)-[:SUBSCRIBES_TO {since: "2023-01-15"}]->(comcast)
MERGE (user)-[:SUBSCRIBES_TO {since: "2022-06-01"}]->(planet)
```

### Python Driver Usage

```python
from neo4j import GraphDatabase

class Neo4jService:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def update_service_rate(self, service_name, old_rate, new_rate, confirmation):
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "MATCH (s:Service {name: $name}) "
                    "SET s.monthlyRate = $new_rate, s.previousRate = $old_rate "
                    "CREATE (n:Negotiation {confirmation: $conf, date: datetime(), "
                    "  oldRate: $old_rate, newRate: $new_rate, savings: $old_rate - $new_rate}) "
                    "MERGE (s)<-[:NEGOTIATED]-(n) "
                    "RETURN s, n",
                    name=service_name, old_rate=old_rate,
                    new_rate=new_rate, conf=confirmation
                )
            )

    def cancel_service(self, user_name, service_name, confirmation):
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "MATCH (p:Person {name: $user})-[r:SUBSCRIBES_TO]->(s:Service {name: $service}) "
                    "SET r.cancelledAt = datetime(), r.confirmation = $conf, r.status = 'cancelled' "
                    "RETURN p, s",
                    user=user_name, service=service_name, conf=confirmation
                )
            )

    def add_entity(self, entity_type, value, context, call_id):
        """Called by extract_entities tool during live calls"""
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "MERGE (e:Entity {value: $value, type: $type}) "
                    "SET e.context = $context, e.extractedAt = datetime() "
                    "WITH e "
                    "MATCH (c:Call {id: $call_id}) "
                    "MERGE (c)-[:EXTRACTED]->(e) "
                    "RETURN e",
                    value=value, type=entity_type, context=context, call_id=call_id
                )
            )
```

### Visualization (Neovis.js)
- Connects directly to Neo4j via Bolt protocol
- Force-directed graph in browser
- SSE event from backend triggers `neoViz.reload()`
- ~50 lines of code for the real-time pipeline

---

## Phase 3: Tavily Integration

**Goal**: Pre-call research + mid-call web search during Vapi tool calls.

### Setup
1. Sign up at https://tavily.com — get API key
2. 1,000 free credits

### Usage in Tool Calls

```python
from tavily import TavilyClient

tavily = TavilyClient(api_key=TAVILY_API_KEY)

async def handle_tavily_search(query: str) -> str:
    """Called when Vapi agent triggers tavily_search tool"""
    response = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=3,
        include_answer=True,
        topic="general"
    )

    # Return concise answer for voice (single-line, no breaks!)
    answer = response.get("answer", "")
    if not answer:
        top = response["results"][0]
        answer = f"{top['title']}: {top['content'][:200]}"

    return answer.replace("\n", " ")  # Critical: no line breaks for Vapi
```

### Pre-Call Research (Task Engine)

```python
async def research_before_call(task):
    """Runs before triggering Vapi outbound call"""
    queries = {
        "cancel_service": f"{task.company} cancellation policy 2025",
        "negotiate_rate": f"{task.company} competitor rates {task.service_type} 2025",
    }
    query = queries.get(task.action, f"{task.company} customer service tips")

    research = tavily.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
    task.research_context = research.get("answer", "")
    task.research_sources = [r["url"] for r in research["results"][:3]]
    return task
```

---

## Phase 4: Hume AI Emotion Analysis

**Goal**: Real-time emotion detection during calls. Shows sentiment shifting on dashboard.

### Setup
1. Sign up at https://platform.hume.ai — get API key
2. Free tier available

### Architecture
- Hume streams alongside the Vapi call via WebSocket
- Analyzes customer service rep's voice across 48 emotion dimensions
- Key emotions to track: `frustration`, `anger`, `satisfaction`, `amusement`, `determination`
- Push emotion data to SSE for dashboard visualization

### Integration Point
- Vapi sends `speech-update` events to webhook
- Extract audio segments, forward to Hume streaming API
- OR use Hume's post-call analysis on the recording (simpler for hackathon)

**Hackathon shortcut**: Instead of real-time Hume streaming (complex), analyze Vapi's transcript text through Hume's Expression Language API. Simpler, still gives emotion indicators for the dashboard.

---

## Phase 5: React Dashboard

**Goal**: 3-panel layout that wows judges with live visualization.

### Layout

```
+------------------+---------------------+------------------+
|   TASK QUEUE     |    LIVE CALL VIEW   |  KNOWLEDGE GRAPH |
|                  |                     |                  |
| [!] Comcast bill |  Transcript:        |    [Neel]        |
|   +$30 detected  |  "Hi, I'm calling   |     / \          |
|                  |   on behalf of..."   |  [Comcast]  [PF] |
| [*] Planet Fit   |                     |    |             |
|   cancel pending |  Emotion: --------  |  [$85/mo]        |
|                  |  cooperative ====|  |    |             |
| Savings: $360/yr |                     |  [$65/mo] NEW!   |
+------------------+---------------------+------------------+
```

### Tech
- React + Vite (fast setup)
- Neovis.js for graph panel (connects to Neo4j Bolt directly)
- EventSource for SSE connection to backend (`/api/events`)
- Tailwind CSS for quick styling

### Key Components
```
frontend/
  src/
    App.tsx
    components/
      TaskQueue.tsx       # Left panel — list of tasks + status
      LiveCallView.tsx    # Center — transcript + emotion bars
      KnowledgeGraph.tsx  # Right — Neovis.js force graph
      TriggerCallButton.tsx  # "Handle It" button
    hooks/
      useSSE.ts           # EventSource hook for real-time updates
    types/
      index.ts            # Task, CallEvent, Entity types
```

---

## Phase 6: Wire Everything Together

### Data Flow (Demo Moment)

```
1. Dashboard shows: "Comcast bill increased $55 → $85"
2. User clicks "Handle It"
3. POST /api/tasks/task_001/trigger
   → Backend researches via Tavily (competitor rates, cancellation policies)
   → Backend POSTs to api.vapi.ai/call with assistantOverrides
4. Vapi dials the phone number
   → Phone rings on speaker in front of judges
5. Agent speaks: "Hi, I'm Alex from LifePilot..."
6. During call:
   → Vapi POSTs tool calls to /api/vapi/tool-call
   → search_task_context returns task details
   → tavily_search finds leverage
   → extract_entities logs confirmation #, new rate
   → update_neo4j writes to graph
   → SSE pushes events to dashboard
7. Dashboard updates in real-time:
   → Transcript streams in center panel
   → Graph grows in right panel (new nodes appear)
   → Emotion indicators shift
8. Agent: "Thank you, I have confirmation #847293"
   → end_task called with status=completed
9. Dashboard shows: "Saved $20/month — $240/year"
```

---

## Build Order (Priority-Sorted)

### Sprint 1: Core Backend (MUST HAVE) — COMPLETE
1. [x] Create `backend/` directory structure
2. [x] Write `main.py` — FastAPI app with CORS, health check
3. [x] Write `routers/vapi_tools.py` — tool-call router (all 5 tools)
4. [x] Write `routers/vapi_webhook.py` — webhook receiver
5. [x] Write `services/task_store.py` — in-memory task store
6. [x] Write `config.py` — env vars loader
7. [x] Write `requirements.txt` + `render.yaml`
8. [x] Deploy to Render — `https://agenthackathon.onrender.com`
9. [x] Update Vapi tools + assistant with real Render URL
10. [ ] Test: make a real outbound call (needs Vapi phone number)

### Sprint 2: Neo4j + Tavily (HIGH VALUE)
11. [ ] Set up Neo4j AuraDB Free
12. [x] Write `services/neo4j_service.py` — done, graceful when not configured
13. [x] Seed graph with demo data — built into neo4j_service.seed_demo_data()
14. [x] Write `services/tavily_service.py` — done, graceful when no key
15. [x] Wire tavily_search tool handler to real Tavily API — wired in vapi_tools.py
16. [x] Wire update_neo4j tool handler to real Neo4j writes — wired in vapi_tools.py
17. [ ] Test: agent searches web + updates graph during call (needs API keys in Render)

### Sprint 3: Dashboard (DEMO WOW)
18. [ ] Scaffold React + Vite frontend
19. [ ] Build TaskQueue component
20. [ ] Build LiveCallView with transcript streaming
21. [ ] Build KnowledgeGraph with Neovis.js
22. [ ] Add SSE hook connecting to backend `/api/events`
23. [ ] Add "Handle It" button → POST /api/tasks/:id/trigger
24. [ ] Style with Tailwind

### Sprint 4: Polish (NICE TO HAVE)
25. [ ] Hume AI emotion analysis (text-based shortcut)
26. [ ] Emotion bars in LiveCallView
27. [ ] Pre-record demo video (OBS)
28. [ ] Prepare backup slides
29. [ ] Buy Vapi phone number for live demo
30. [ ] Test full flow end-to-end 3x

---

## Environment Variables Needed

```env
# Vapi
VAPI_API_KEY=               # Get from dashboard.vapi.ai
VAPI_PUBLIC_KEY=            # Get from dashboard.vapi.ai
VAPI_ASSISTANT_ID=          # Your assistant ID from Vapi
VAPI_PHONE_NUMBER_ID=       # Get from Vapi dashboard after buying
VAPI_TOOL_IDS=              # Comma-separated tool IDs from Vapi

# Neo4j AuraDB
NEO4J_URI=                  # neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=

# Tavily
TAVILY_API_KEY=             # Get from tavily.com

# Hume AI
HUME_API_KEY=               # Get from platform.hume.ai
```

---

## Vapi IDs Reference

> **Note:** All Vapi IDs are stored in environment variables. See `.env.example` for the full list.
> Never commit real IDs to version control.

---

## Demo Script (3 minutes)

### 0:00-0:15 — Problem (shocking stat)
> "Americans waste 900 million hours on hold every year. We've all been there — dreading that call to cancel a gym membership or negotiate a cable bill."

### 0:15-0:30 — Empathy + Solution
> "What if you never had to make those calls again? LifePilot is an AI agent that watches your bills, detects problems, and makes the phone calls for you."

### 0:30-0:45 — Tech Stack Name-Drops
> "We use Yutori Scouts to monitor the web, Tavily for real-time research, Vapi for voice calling with Groq's Llama 3.3, Neo4j for a living knowledge graph, and Hume AI for emotion-aware negotiation."

### 0:45-2:15 — Live Demo
> "Let me show you. Here's our dashboard — it detected Neel's Comcast bill jumped from $55 to $85. Watch what happens when I click 'Handle It'..."
>
> *Phone rings on speaker. Agent negotiates. Graph grows on screen. Emotion bars shift.*
>
> "There it is — confirmation number captured, graph updated, $20 saved per month."

### 2:15-2:45 — Impact
> "That's $240 a year from one call. Across all your services — internet, gym, insurance, streaming — LifePilot could save the average household $1,200 a year without lifting a finger."

### 2:45-3:00 — Vision
> "The era of being put on hold is over. LifePilot — your AI life manager."

---

## Pitch Strategy: Multi-Prize Targeting

| Sponsor | Prize Track | Our Integration Depth |
|---------|-------------|----------------------|
| **Vapi** | Best Voice Agent | Core calling infra, all 5 tools, latency-optimized, outbound calls |
| **Neo4j** | Best Graph Use | Live knowledge graph, bi-temporal, grows during calls, Neovis.js viz |
| **Tavily** | Best Search Use | Pre-call research + mid-call web search, intent enrichment |
| **Render** | Best Deployment | Full backend deployed, render.yaml, env management |
| **Hume AI** | Best Emotion Use | Real-time sentiment tracking during negotiations |
| **Grand Prize** | Most Impressive | Only project combining monitoring + calling + live graph |
| **Most Viral** | Best Demo Video | Pre-recorded polished video of full demo flow |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Render cold start delays (30s on free tier) | Pre-warm with health check ping before demo |
| Vapi call fails during demo | Pre-record backup video, have slides ready |
| Neo4j AuraDB connection drops | Seed data beforehand, graph still shows pre-existing nodes |
| Tavily rate limit | Cache research results for demo scenario |
| Venue Wi-Fi unstable | Mobile hotspot as backup |
| Groq API latency spike | Vapi handles fallback; keep maxTokens at 300 |
