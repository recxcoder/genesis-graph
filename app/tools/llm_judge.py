from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL")
if not MODEL:
    raise ValueError("GROQ_MODEL not set in .env — add your model name")


def llm_judge(goal: str, response: str) -> dict:
    """
    Evaluates whether the agent has completed the goal.
    Returns {"done": bool, "feedback": str}

    Same logic as Genesis Agent's llm_judge tool.
    """
    result = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """You are a judge evaluating if a goal has been completed.
Respond ONLY in this exact format:
DONE: YES or NO
FEEDBACK: what is still missing (empty if done)"""
            },
            {
                "role": "user",
                "content": f"Goal: {goal}\n\nResponse: {response}"
            }
        ],
        max_tokens=200,
        temperature=0.1
    ).choices[0].message.content.strip()

    done     = "DONE: YES" in result.upper()
    feedback = ""

    for line in result.splitlines():
        if line.upper().startswith("FEEDBACK:"):
            feedback = line.split(":", 1)[1].strip()

    return {"done": done, "feedback": feedback}