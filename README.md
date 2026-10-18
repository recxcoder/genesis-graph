# Genesis-Graph
 
> Built for **Graph Hacks: Context for AI Agents** hackathon by WeMakeDevs × FalkorDB.

---

## What is this?

Genesis-graph is an AI research agent built from scratch in pure Python — no LangChain, no frameworks.

This adds a **persistent knowledge graph** powered by FalkorDB. Every fact the agent discovers, every URL it reads, every judgment it makes — all stored as nodes and edges in a graph. On the next run, the agent pulls from that memory instead of re-fetching what it already knows.

The result: an agent that gets smarter with every query.

---

## Demo

**Run 1 — New session:**
```
Enter session ID (or press Enter for new): [Enter]
Enter prompt: What is FalkorDB?

🆕 New session: sess_a1b2c3
🔍 Search needed - gathering context...
🌐 Browsing top 3 URLs...
   📌 [0.94] FalkorDB is a graph database built on Redis...
   📌 [0.91] FalkorDB uses the Cypher query language...
✅ GOAL COMPLETED!
🆔 Session ID (save this): sess_a1b2c3
```

**Run 2 — Same session, related query:**
```
Enter session ID (or press Enter for new): sess_a1b2c3
Enter prompt: How does FalkorDB compare to Neo4j?

♻️  Resuming session: sess_a1b2c3
🧠 Found relevant facts in graph memory — skipping redundant search
✅ GOAL COMPLETED!
```

The agent reused prior knowledge. No redundant web requests. That's the graph memory working.

---

## Architecture

```
User Query (terminal)
       ↓
  Rule-based Router
  ┌────────────────────────────────┐
  │  Keywords? → force web search  │
  │  LLM decides? → YES/NO         │
  │  Graph memory enough? → skip   │
  └────────────────────────────────┘
       ↓                    ↓
  Web Search            LLM Knowledge
  (DuckDuckGo)          (direct answer)
       ↓
  Fetch top 3 URLs
       ↓
  Extract Facts (LLM)
       ↓
  Verify Facts (LLM-as-Judge)
       ↓
  Store in FalkorDB Graph
       ↓
  Build Answer (with graph context)
       ↓
  LLM-as-Judge evaluates → done?
       ↓
  Final Answer
```

---

## Graph Schema

Every research run writes to FalkorDB as a knowledge graph:

```
(Session) -[:CONTAINED]-> (Query)
(Query)   -[:FOUND]->      (WebPage)
(WebPage) -[:MENTIONS]->   (Fact)
(Fact)    -[:VERIFIED_BY]-> (Verdict)
(Fact)    -[:RELATED_TO]->  (Fact)
```

| Node | Properties |
|---|---|
| `Session` | id, topic, created_at |
| `Query` | id, text, timestamp |
| `WebPage` | url, title, fetched_at |
| `Fact` | id, text, confidence, verified |
| `Verdict` | id, score, reason |

---

## Hackathon Tracks

**Track 01 — Agents That Act on Connected Data**

The agent traverses the graph using multi-hop Cypher queries:
```cypher
MATCH (s:Session)-[:CONTAINED]->(q:Query)
      -[:FOUND]->(w:WebPage)
      -[:MENTIONS]->(f:Fact)
WHERE toLower($topic) CONTAINS toLower(q.text)
  AND f.verified = true
RETURN f.text, f.confidence
ORDER BY f.confidence DESC
```
Every answer is traceable back through the graph to its source.

**Track 02 — Agent Memory & Coordination**

Session IDs persist across runs. Pass a prior session ID and the agent:
- Skips URLs it already read
- Pulls verified facts into context before every LLM call
- Never re-searches what it already knows
- Builds knowledge cumulatively across sessions

---

## Tech Stack

| Layer | Tool |
|---|---|
| LLM | Groq API (`openai/gpt-oss-120b`) |
| Graph DB | FalkorDB Cloud (AWS ap-south-1) |
| Agent | Pure Python — no LangChain |
| Web Search | DuckDuckGo (`duckduckgo-search`) |
| URL Fetcher | `httpx` + `BeautifulSoup4` |
| Fact Verification | LLM-as-Judge (Groq) |

---

## Project Structure

```
genesis-graph/
├── .env.example
├── requirements.txt
└── app/
    ├── agent/
    │   ├── planner.py           # main agent loop
    │   └── context_builder.py   # graph → LLM context injection
    ├── graph/
    │   ├── client.py            # FalkorDB connection
    │   ├── writer.py            # write nodes and edges
    │   └── reader.py            # Cypher queries + multi-hop
    └── tools/
        ├── web_search.py        # DuckDuckGo search
        ├── url_browser.py       # fetch + clean HTML
        ├── llm_judge.py         # goal completion evaluator
        └── fact_extractor.py    # extract + verify + store facts
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/recxcoder/genesis-graph
cd genesis-graph
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables


In `.env`:

```
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b

FALKORDB_HOST=your-host.falkordb.cloud
FALKORDB_PORT=your_port
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=your_password
```

Get your Groq API key at [console.groq.com](https://console.groq.com)  
Get your FalkorDB instance at [app.falkordb.cloud](https://app.falkordb.cloud)

### 4. Run the agent

```bash
python -m app.agent.planner
```

---

## How session memory works

```bash
# First run — creates new session
python -m app.agent.planner
> Enter session ID (or press Enter for new): [Enter]
> Enter prompt: What is Redis?
> 🆕 New session: sess_abc123
> ...
> 🆔 Session ID (save this): sess_abc123

# Second run — resumes with memory
python -m app.agent.planner
> Enter session ID (or press Enter for new): sess_abc123
> Enter prompt: How does Redis compare to Memcached?
> ♻️  Resuming session: sess_abc123
> 🧠 Using graph memory as context
```

---

## What makes this different from RAG

| RAG (vector similarity) | Genesis Graph (knowledge graph) |
|---|---|
| Finds similar chunks | Finds connected facts |
| No relationship tracking | Tracks source → fact → verdict |
| Stateless between runs | Persistent across sessions |
| Can't trace reasoning | Full reasoning path in graph |
| Re-fetches same content | Deduplicates at URL level |

---

## About

Built by **Shivam Vishwakarma** ([@recxcoder](https://github.com/recxcoder))  
2nd year B.Tech CSE · India  

> Genesis Agent is built from scratch in pure Python — no frameworks, no magic.  
> Just the fundamentals, one layer at a time.

---

## License

MIT
