if __name__ == "__main__":
    from app.tools.url_browser import *

    text, title = fetch_url("https://falkordb.com")
    print(f"Title: {title}")
    print(f"Text length: {len(text)} chars")
    print(f"Preview:\n{text[:300]}")
    print("\n✅ url_browser working")