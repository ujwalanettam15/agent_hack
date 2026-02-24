Here's the full architecture top to bottom:

---

**LifePilot — System Architecture**

**Layer 1: Monitoring (the "eyes")**

Yutori Scouts run on a schedule — every few hours they crawl the web looking for things that affect your wallet. Bill increases, expiring promotions, subscription renewals, better deals available. They use Tavily Search to discover URLs and pull clean content, then Yutori's browsing agents handle anything interactive (logging into provider portals, checking account pages). When a Scout detects something actionable — say your Comcast bill jumped $30 — it fires a webhook to your backend.

**Layer 2: Task Engine (the "brain")**

FastAPI backend on Render. Receives webhooks from Scouts, creates a structured task (what to do, who to call, what leverage to use), and queues it. Before any call goes out, it hits Tavily again to research: competitor rates, cancellation policies, retention department scripts, anything that gives your agent an edge. All this context gets packed into the task object.

**Layer 3: Voice Agent (the "mouth")**

Vapi outbound call. Your backend POSTs to `api.vapi.ai/call` with the assistant ID and task-specific overrides (first message, system prompt with negotiation strategy, target phone number). The call hits the phone network, a real phone rings, and the agent starts talking. Stack: Deepgram Nova-3 for ears (~90ms), Groq Llama 3.3 70B for thinking (~200ms), ElevenLabs Flash v2.5 Josh voice for speaking (~75ms). During the call, the agent can make tool calls back to your backend — search for more info via Tavily, extract entities (confirmation numbers, prices, names), update the knowledge graph.

**Layer 4: Knowledge Graph (the "memory")**

Neo4j AuraDB with Graphiti framework. Every entity the agent encounters becomes a node: You → subscribes_to → Comcast, Comcast → charges → $85/month, Call_001 → resulted_in → Rate_Reduction. Bi-temporal tracking means the graph knows both when something was true and when the agent learned it. After every call, the backend writes the outcome to Neo4j. Over time this becomes a complete map of your entire service ecosystem — what you pay, who you talked to, what was promised, what expired.

**Layer 5: Emotion Analysis (the "intuition")**

Hume AI streams alongside the Vapi call. It analyzes the customer service rep's voice across 48 emotion dimensions in real-time. When the rep sounds frustrated or resistant, the agent can shift tactics (soften tone, offer to escalate). When the rep sounds accommodating, the agent pushes harder on the discount. This data also flows to the dashboard so you can watch sentiment shift live during the demo.

**Layer 6: Dashboard (the "face")**

React frontend (or Streamlit for speed). Three panels:

- **Left**: Task queue. Shows detected issues, pending calls, completed tasks with outcomes and savings.
- **Center**: Live call view. Real-time transcript streaming via Vapi websocket, Hume emotion indicators showing rep sentiment, current negotiation status.
- **Right**: Neo4j graph visualization via Neovis.js. Nodes and edges grow in real-time as the agent extracts entities. You literally watch the agent's brain building connections on screen.

---

**Data flow for the demo moment:**

Scout detects bill increase → Task created → You click "Handle It" (or teammate hits API endpoint) → Vapi makes outbound call → Phone rings on speaker in front of judges → Agent navigates phone tree → Negotiates with "rep" (your teammate) → Entities extracted in real-time → Graph grows on screen → Emotion analysis shows sentiment shifting → Agent secures discount → Task marked complete → Dashboard shows "$300/year saved"

---

**Sponsor integration map:**

- **Yutori** → Layer 1 (monitoring + browsing)
- **Tavily** → Layer 1 + Layer 2 (search + pre-call research)
- **OpenAI/Groq** → Layer 3 (LLM brain via Vapi)
- **Vapi** → Layer 3 (voice calling infrastructure)
- **Neo4j** → Layer 4 (knowledge graph)
- **Hume AI** → Layer 5 (emotion analysis)
- **Render** → All layers (deployment)

Seven sponsors, each one essential to the architecture, not just checked-as-a-box.