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
MODEL  = os.getenv("GROQ_MODEL")
if not MODEL:
    raise ValueError("GROQ_MODEL not set in .env - add your model name")

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
    search_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet'][:200]}"
        for r in raw_results
    ])

    return f"Search Results:\n{search_text}\n\nPage Content:\n{'---'.join(page_contents)}"


# MAIN AGENT LOOP — same structure as Genesis Agent

def run_agent(goal: str, session_id: str = None):
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        print(f"\n🆕 New session: {session_id}")
    else:
        print(f"\n♻️  Resuming session: {session_id}")


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

            # at the very end of run_agent, replace the final_answer tracking with this:

    result = {
        "session_id":   session_id,
        "final_answer": final_answer,
        "completed":    bool(final_answer),
        "iterations":   iteration
    }

    print(f"\n📊 Result: {result['iterations']} iterations, completed: {result['completed']}")
    return result



# ENTRY POINT — user types query in terminal

if __name__ == "__main__":
    print("─" * 40)
    print("Genesis-graph")
    print("─" * 40)

    existing = input("Enter session ID to resume (or press Enter for new): ").strip()
    session_id = existing if existing else None

    goal   = input("Enter prompt: ")
    result = run_agent(goal, session_id=session_id)

    print(f"\n🆔 Session ID (save this to resume): {result['session_id']}")