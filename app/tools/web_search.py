from ddgs import DDGS

def search_web(query: str, max_results: int = 5) -> str:
    
    try:
        results = []

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", "")
                })

        if not results:
            return "No results found."

        formatted = []
        for r in results:
            formatted.append(
                f"Title: {r['title']}\n"
                f"URL: {r['url']}\n"
                f"Snippet: {r['snippet'][:200]}"
            )

        return "\n---\n".join(formatted)

    except Exception as e:
        print(f"[search_web] Failed: {e}")
        return "Search failed."


def search_web_raw(query: str, max_results: int = 5) -> list[dict]:
    
    try:
        results = []

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", "")
                })

        return results

    except Exception as e:
        print(f"[search_web_raw] Failed: {e}")
        return []