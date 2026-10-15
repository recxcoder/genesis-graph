from falkordb import FalkorDB
from dotenv import load_dotenv
import os

load_dotenv()

db = FalkorDB(
    host=os.getenv("FALKORDB_HOST"),
    port=int(os.getenv("FALKORDB_PORT")),
    username=os.getenv("FALKORDB_USERNAME"),   # ← add this
    password=os.getenv("FALKORDB_PASSWORD")
)

g = db.select_graph("genesis_test")

g.query("CREATE (:Person {name: 'Shivam', role: 'builder'})")
print("✓ Node created")

result = g.query("MATCH (p:Person) RETURN p.name, p.role")
for row in result.result_set:
    print(f"✓ Found: {row[0]} — {row[1]}")

print("\n✅ Connected successfully!")