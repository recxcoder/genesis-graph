from groq import Groq
from dotenv import load_dotenv
import os
import json

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def verify_fact(fact: str, source_url: str) -> tuple[float, str]:
    """
    Score guide:
      0.9+ → clearly factual, well-known
      0.7  → likely true, reasonable claim
      0.5  → uncertain, needs more sources
      0.3  → doubtful, weak claim
      0.1  → likely false or misleading
    """

    prompt = f"""You are a strict fact-checking judge. Evaluate this claim.

CLAIM: {fact}
SOURCE: {source_url}

Respond ONLY with a valid JSON object. No explanation outside the JSON.

{{
  "score": <float between 0.0 and 1.0>,
  "reason": "<one sentence explaining the score>"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model adds them
        raw = raw.replace("```json", "").replace("```", "").strip()

        data = json.loads(raw)
        score = float(data["score"])
        reason = str(data["reason"])

        score = max(0.0, min(1.0, score))

        return score, reason

    except json.JSONDecodeError:
        return 0.5, "Could not parse verdict — defaulting to uncertain"

    except Exception as e:
        print(f"[verifier] Error: {e}")
        return 0.5, "Verification failed due to an error"