from app.graph.client import get_graph
from datetime import datetime
import uuid

def _now() -> str:
    return datetime.utcnow().isoformat()

# 1. SESSION - top level container

def create_session(session_id: str, topic:str):
    g = get_graph(session_id)
    g.query("""
        MERGE (s:Session {id: $id})
        ON CREATE SET s.topic = $topic, s.created_at = $ts""", {'id':session_id, 'topic': topic, 'ts':_now()})


# 2. QUERY - each search the agent makes

def create_query_node(session_id: str, query_text: str) -> str:
    g = get_graph(session_id)
    query_id = f"q_{uuid.uuid4().hex[:8]}"

    g.query("""
        MERGE (q:Query {id: $qid})
        ON CREATE SET q.text = $text, q.timestamp = $ts
    """, {'qid':query_id, 'text': query_text, 'ts': _now()})

    # Link: Session -[:CONTAINED]-> Query
    g.query("""
        MATCH (s:Session {id: $sid}), (q:Query {id: $qid})
        MERGE (s)-[:CONTAINED]->(q)
    """, {'sid': session_id, 'qid': query_id})

    return query_id


# 3. WEBPAGE - every URL the agent visits

def create_webpage(session_id: str, query_id: str, url: str, title: str):
    
    g = get_graph(session_id)

    g.query("""
        MERGE (w:WebPage {url: $url})
        ON CREATE SET w.title = $title, w.fetched_at = $ts
    """, {'url': url, 'title': title, 'ts': _now()})

    # Link: Query -[:FOUND]-> WebPage
    g.query("""
        MATCH (q:Query {id: $qid}), (w:WebPage {url: $url})
        MERGE (q)-[:FOUND]->(w)
    """, {'qid': query_id, 'url': url})


# 4. FACT — individual claims extracted

def create_fact(session_id: str, url: str, fact_text: str) -> str:

    g = get_graph(session_id)
    fact_id = f"f_{uuid.uuid4().hex[:8]}"

    g.query("""
        MERGE (f:Fact {id: $fid})
        ON CREATE SET f.text = $text, f.verified = false, f.confidence = 0.0
    """, {'fid': fact_id, 'text': fact_text})

    # Link: WebPage -[:MENTIONS]-> Fact
    g.query("""
        MATCH (w:WebPage {url: $url}), (f:Fact {id: $fid})
        MERGE (w)-[:MENTIONS]->(f)
    """, {'url': url, 'fid': fact_id})

    return fact_id


# 5. VERDICT — LLM-as-Judge result

def store_verdict(session_id: str, fact_id: str, score: float, reason: str):
    
    g = get_graph(session_id)
    verdict_id = f"v_{fact_id}"

    g.query("""
        MERGE (v:Verdict {id: $vid})
        ON CREATE SET v.score = $score, v.reason = $reason
    """, {'vid': verdict_id, 'score': score, 'reason': reason})

    # Link: Fact -[:VERIFIED_BY]-> Verdict
    # Also update the Fact node itself
    g.query("""
        MATCH (f:Fact {id: $fid}), (v:Verdict {id: $vid})
        MERGE (f)-[:VERIFIED_BY]->(v)
        SET f.confidence = $score,
            f.verified   = ($score > 0.6)
    """, {'fid': fact_id, 'vid': verdict_id, 'score': score})

