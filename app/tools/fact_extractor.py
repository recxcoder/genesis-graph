# app/tools/fact_extractor.py

from groq import Groq
from dotenv import load_dotenv
from app.graph.writer import create_fact, store_verdict
import os, json

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def extract_facts(content: str) -> list[str]:
    """
    Takes raw page content.
    Returns list of factual claim strings.
    """
    try:
        raw = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""Extract 3 to 5 key factual claims from this content.
Return ONLY a valid JSON array of strings. No explanation. No markdown fences.
Example: ["Fact one.", "Fact two.", "Fact three."]

Content:
{content[:2000]}"""
            }],
            max_tokens=400,
            temperature=0.1
        ).choices[0].message.content.strip()

        raw   = raw.replace("```json", "").replace("```", "").strip()
        facts = json.loads(raw)
        return facts if isinstance(facts, list) else []

    except Exception as e:
        print(f"[extract_facts] Failed: {e}")
        return []


def verify_fact(fact: str, source_url: str) -> tuple[float, str]:
    """
    LLM-as-Judge: scores a single fact 0.0–1.0.
    Returns (score, reason).
    """
    try:
        raw = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""You are a fact-checking judge. Evaluate this claim.

CLAIM: {fact}
SOURCE: {source_url}

Respond ONLY with valid JSON:
{{"score": <0.0 to 1.0>, "reason": "<one sentence>"}}

Score guide:
0.9+ = clearly factual
0.7  = likely true
0.5  = uncertain
0.3  = doubtful
0.1  = likely false"""
            }],
            max_tokens=150,
            temperature=0.1
        ).choices[0].message.content.strip()

        raw     = raw.replace("```json", "").replace("```", "").strip()
        verdict = json.loads(raw)
        score   = max(0.0, min(1.0, float(verdict.get("score", 0.5))))
        reason  = verdict.get("reason", "")
        return score, reason

    except Exception as e:
        print(f"[verify_fact] Failed: {e}")
        return 0.5, "Verification failed"


def extract_verify_store(session_id: str, url: str, content: str):
    """
    Full pipeline:
    1. Extract facts from content
    2. Verify each fact with LLM-as-Judge
    3. Store fact + verdict in FalkorDB graph

    Call this after fetching any URL.
    """
    facts = extract_facts(content)

    if not facts:
        print("   ⚠️  No facts extracted")
        return

    for fact_text in facts:
        # Write fact node to graph
        fact_id = create_fact(session_id, url, fact_text)

        # Verify with LLM-as-Judge
        score, reason = verify_fact(fact_text, url)

        # Write verdict to graph
        store_verdict(session_id, fact_id, score, reason)

        print(f"   📌 [{score:.2f}] {fact_text[:80]}")