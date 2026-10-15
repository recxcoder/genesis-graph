import httpx
from bs4 import BeautifulSoup


def fetch_url(url: str, max_chars: int = 4000) -> tuple[str, str]:
    
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer",
                         "header", "aside", "form", "iframe"]):
            tag.decompose()

        # Extract title
        title = soup.title.string.strip() if soup.title else url

        # Extract clean text
        text = soup.get_text(separator="\n", strip=True)

        # Collapse blank lines
        lines = [line for line in text.splitlines() if line.strip()]
        clean = "\n".join(lines)

        return clean[:max_chars], title

    except Exception as e:
        print(f"[url_browser] Failed to fetch {url}: {e}")
        return "", ""