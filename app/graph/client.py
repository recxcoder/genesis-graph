from falkordb import FalkorDB
from dotenv import load_dotenv
import os

load_dotenv()

def _connect() -> FalkorDB:
    return FalkorDB(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        username=os.getenv("FALKORDB_USERNAME"),
        password=os.getenv("FALKORDB_PASSWORD")
    )

# Single connection shared across the whole app
_db = _connect()

def get_graph(session_id: str):
    #Each session gets its own isolated named graph
    return _db.select_graph(f"genesis_{session_id}")
