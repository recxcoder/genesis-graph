from app.graph.client import get_graph


# 1. DEDUP CHECK — before fetching any URL

def already_visited(session_id: str, url: str) -> bool:
    
    g = get_graph(session_id)
    result = g.query("""
        MATCH (w:WebPage {url: $url})
        RETURN count(w) > 0 AS seen
    """, {'url': url})

    if result.result_set:
        return bool(result.result_set[0][0])
    return False


# 2. KNOWN FACTS — inject into LLM context

def get_known_facts(session_id: str, limit: int = 10) -> list[str]:

    g = get_graph(session_id)
    result = g.query("""
        MATCH (w:WebPage)-[:MENTIONS]->(f:Fact)
        WHERE f.verified = true
        RETURN f.text, f.confidence, w.url
        ORDER BY f.confidence DESC
        LIMIT $limit
    """, {'limit': limit})

    return [
        f"[{row[1]:.2f}] {row[0]} (source: {row[2]})"
        for row in result.result_set
    ]


# 3. PRIOR QUERIES — what has been searched

def get_prior_queries(session_id: str) -> list[str]:
    
    g = get_graph(session_id)
    result = g.query("""
        MATCH (s:Session {id: $sid})-[:CONTAINED]->(q:Query)
        RETURN q.text
        ORDER BY q.timestamp ASC
    """, {'sid': session_id})

    return [row[0] for row in result.result_set]


# 4. MULTI-HOP — the graph superpower

def multihop_related_facts(session_id: str, topic: str) -> list[str]:
    
    g = get_graph(session_id)
    result = g.query("""
        MATCH (s:Session {id: $sid})
              -[:CONTAINED]->(q:Query)
              -[:FOUND]->(w:WebPage)
              -[:MENTIONS]->(f:Fact)
        WHERE toLower($topic) CONTAINS toLower(q.text)
          AND f.verified = true
        RETURN f.text, f.confidence, w.url
        ORDER BY f.confidence DESC
        LIMIT 5
    """, {'sid': session_id, 'topic': topic})

    return [
        f"[{row[1]:.2f}] {row[0]} (via: {row[2]})"
        for row in result.result_set
    ]


# 5. FULL GRAPH SNAPSHOT — for /graph API

def get_graph_snapshot(session_id: str) -> dict:
    g = get_graph(session_id)

    result = g.query("""
        MATCH (q:Query)-[:FOUND]->(w:WebPage)-[:MENTIONS]->(f:Fact)
        OPTIONAL MATCH (f)-[:VERIFIED_BY]->(v:Verdict)
        RETURN q.text, w.url, w.title, f.text, f.confidence, f.verified, v.reason
    """)

    nodes      = []
    edges      = []
    seen_urls  = set()
    seen_facts = set()   # ← add this
    seen_edges = set()   # ← add this

    for row in result.result_set:
        query_text, url, title, fact, confidence, verified, reason = row

        if url not in seen_urls:
            nodes.append({'type': 'WebPage', 'url': url, 'title': title})
            seen_urls.add(url)

        # ← dedup facts
        if fact not in seen_facts:
            nodes.append({
                'type':           'Fact',
                'text':           fact,
                'confidence':     confidence,
                'verified':       verified,
                'verdict_reason': reason
            })
            seen_facts.add(fact)

        # ← dedup edges
        edge_key = f"{url}→{fact}"
        if edge_key not in seen_edges:
            edges.append({
                'from':         url,
                'to':           fact,
                'relationship': 'MENTIONS'
            })
            seen_edges.add(edge_key)

    return {
        'session_id':   session_id,
        'total_facts':  len(seen_facts),   # ← accurate count now
        'total_pages':  len(seen_urls),
        'nodes':        nodes,
        'edges':        edges
    }