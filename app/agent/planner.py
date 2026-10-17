import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

from app.graph.writer import (
    create_session,
    create_query_node,
    create_webpage,
    create_fact,
    store_verdict
)
from app.graph.reader import (
    already_visited,
    get_known_facts,
    get_prior_queries,
)
from app.agent.context_builder import build_context
from app.tools.web_search import search_web, search_web_raw
from app.tools.url_browser import fetch_url
from app.tools.llm_judge import llm_judge
from app.tools.fact_extractor import extract_verify_store


load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

MAX_ITERATIONS = 3

# LLM HELPER

def llm(messages: list) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1000,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


# ROUTER

SEARCH_KEYWORDS = [
    "latest", "today", "current", "recent",
    "this week", "this month", "this year", "news",
    "price", "prices", "cost", "ticket",
    "timing", "opening hours", "availability", "near",
    "nearby", "where can i buy", "restaurant", "hotel",
    "flight", "weather", "stock",
]

def needs_search(goal: str, session_id: str) -> bool:
    goal_lower = goal.lower()

    # Rule-based check first
    if any(keyword in goal_lower for keyword in SEARCH_KEYWORDS):
        print("\n⏱️  Time-sensitive query detected - forcing web search")
        return True

    # Check graph memory — if we already know enough, skip search
    known = get_known_facts(session_id, limit=5)
    prior = get_prior_queries(session_id)

    if known and any(word in goal_lower for word in prior):
        print("\n🧠 Found relevant facts in graph memory - skipping search")
        return False

    # LLM fallback decision
    decision = llm([
        {
            "role": "system",
            "content": """You decide whether web search is required.
Respond ONLY with YES or NO.

Answer YES if:
- the answer could change over time
- current or live information is needed
- local businesses or locations are involved
- prices, timings, availability, or schedules are requested
- searching the web would significantly improve accuracy

Answer NO only if the answer is stable general knowledge."""
        },
        {
            "role": "user",
            "content": f"Does this question require web search?\n\nQuestion: {goal}"
        }
    ])
    return "YES" in decision.upper()


# FACT EXTRACTOR + VERIFIER

def extract_and_store_factsextract_verify_store(session_id, url, content):
    """Extract facts from page content, verify each, store in graph."""

    raw = llm([{
        "role": "user",
        "content": f"""Extract 3 to 5 key factual claims from this content.
Return ONLY a Python list of strings. No explanation. No markdown.
Example: ["Fact one.", "Fact two.", "Fact three."]

Content:
{content[:2000]}"""
    }])

    try:
        import json
        raw = raw.replace("```json", "").replace("```", "").strip()
        facts = json.loads(raw)
        if not isinstance(facts, list):
            return
    except Exception:
        return

    for fact_text in facts:
        # Store fact in graph
        fact_id = create_fact(session_id, url, fact_text)

        # Verify with LLM-as-Judge
        verdict_raw = llm([{
            "role": "user",
            "content": f"""You are a fact-checking judge. Evaluate this claim.

CLAIM: {fact_text}
SOURCE: {url}

Respond ONLY with valid JSON:
{{"score": <0.0 to 1.0>, "reason": "<one sentence>"}}"""
        }])

        try:
            import json as j
            verdict_raw = verdict_raw.replace("```json", "").replace("```", "").strip()
            verdict = j.loads(verdict_raw)
            score   = float(verdict.get("score", 0.5))
            reason  = verdict.get("reason", "")
        except Exception:
            score, reason = 0.5, "Could not parse verdict"

        store_verdict(session_id, fact_id, score, reason)
        print(f"   📌 [{score:.2f}] {fact_text[:80]}")



# GATHER CONTEXT

def gather_context(goal: str, session_id: str) -> str:
    # Raw results for URL extraction
    raw_results = search_web_raw(goal, max_results=5)

    if not raw_results:
        return "No search results found."

    query_id = create_query_node(session_id, goal)

    # Top 3 URLs to browse — same as Genesis Agent
    top_urls = [r["url"] for r in raw_results[:3]]

    print("\n🌐 Browsing top 3 URLs...")
    page_contents = []

    for url in top_urls:
        print(f"   → {url}")

        if already_visited(session_id, url):
            print(f"   🧠 Already in memory — skipping")
            continue

        content, title = fetch_url(url)

        if not content:
            print(f"   ⚠️  Failed to fetch")
            continue

        create_webpage(session_id, query_id, url, title or url)
        print(f"   ✅ Fetched: {title[:60]}")
        print(f"   🔬 Extracting facts...")

        extract_verify_store(session_id, url, content)

        page_contents.append(f"URL: {url}\n{content[:800]}")

    # Formatted string for LLM context
    search_text = search_web(goal, max_results=5)

    return f"Search Results:\n{search_text}\n\nPage Content:\n{'---'.join(page_contents)}"


# MAIN AGENT LOOP — same structure as Genesis Agent

def run_agent(goal: str, session_id: str = None):
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

    print("\n" + "─" * 40)
    print(f"🎯 Goal: {goal}")
    print(f"🆔 Session: {session_id}")
    print("─" * 40)

    # Init session in graph
    create_session(session_id, topic=goal)

    # ── ROUTER ──────────────────────────────
    context = ""
    if needs_search(goal, session_id):
        print("\n🔍 Search needed - gathering context...")
        context = gather_context(goal, session_id)
        print("\n✅ Context gathered and stored in graph!")
    else:
        # Pull known facts from graph memory as context
        known = get_known_facts(session_id, limit=8)
        if known:
            context = "Known facts from memory:\n" + "\n".join(f"- {f}" for f in known)
            print("\n🧠 Using graph memory as context")
        else:
            print("\n💡 No search needed - using LLM knowledge directly")

    # ── BUILD MESSAGES ───────────────────────
    SYSTEM_PROMPT = f"""You are a helpful assistant working for a busy executive.
Your tone is friendly but direct, they prefer short clear and direct writing.
You try to accomplish the specific task you are given.
Today is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nGoal: {goal}" if context else goal
        }
    ]

    final_answer = ""
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"\n🔄 Iteration {iteration}/{MAX_ITERATIONS}")

        response = llm(messages)
        print(f"\n🤖 Agent: {response[:300]}...")

        messages.append({"role": "assistant", "content": response})

        # LLM-as-Judge
        result = llm_judge(goal, response)

        if result["done"]:
            print("\n" + "─" * 40)
            print("✅ GOAL COMPLETED!")
            print("─" * 40)
            print(f"\n📋 Final Answer:\n{response}")
            print(f"\n🧠 Graph session: {session_id}")
            final_answer = response
            break

        if result.get("feedback"):
            messages.append({
                "role": "user",
                "content": f"Feedback: You still need to complete: {result['feedback']}"
            })

        if iteration == MAX_ITERATIONS:
            print("\n⚠️  Max iterations reached!")
            final_answer = response

    return final_answer



# ENTRY POINT — user types query in terminal

if __name__ == "__main__":
    goal = input("Enter prompt: ")
    run_agent(goal)