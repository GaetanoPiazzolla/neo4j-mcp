import os
import time
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError

load_dotenv()

URI = os.environ["NEO4J_URI"]
USERNAME = os.environ["NEO4J_USERNAME"]
PASSWORD = os.environ["NEO4J_PASSWORD"]
DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")
_SCRIPT_DIR = Path(__file__).parent
CYPHER_FILE = _SCRIPT_DIR / os.environ.get("CYPHER_FILE", "import.cypher")


def parse_statements(script: str) -> list[str]:
    statements = []
    for raw in script.split(";"):
        lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("//")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements


def create_database(driver, name: str):
    try:
        with driver.session(database="system") as session:
            session.run(f"CREATE DATABASE `{name}` IF NOT EXISTS")
            for _ in range(30):
                result = session.run(
                    "SHOW DATABASE $name YIELD name, currentStatus",
                    name=name,
                )
                row = result.single()
                if row and row["currentStatus"] == "online":
                    break
                time.sleep(1)
            else:
                raise RuntimeError(f"Database '{name}' did not come online in time")
        print(f"Database '{name}' ready.")
    except ClientError as e:
        if "not supported in community edition" in str(e).lower():
            print(
                f"Warning: Community Edition detected — cannot create database '{name}'.\n"
                f"  Set NEO4J_DATABASE=neo4j in .env to use the default database."
            )
        else:
            raise


def run():
    script = Path(CYPHER_FILE).read_text()
    statements = parse_statements(script)

    print(f"Connecting to {URI} (database: {DATABASE})")
    with GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD)) as driver:
        driver.verify_connectivity()
        create_database(driver, DATABASE)
        print(f"Connected. Running {len(statements)} statement(s) from {CYPHER_FILE}\n")

        with driver.session(database=DATABASE) as session:
            for i, stmt in enumerate(statements, 1):
                preview = stmt.splitlines()[0][:72]
                print(f"[{i}/{len(statements)}] {preview}...")
                # The main import query calls the SO API 20 times — allow up to 5 minutes
                result = session.run(stmt, timeout=300)
                counters = result.consume().counters
                print(
                    f"  nodes_created={counters.nodes_created} "
                    f"rels_created={counters.relationships_created} "
                    f"constraints_added={counters.constraints_added}\n"
                )

    print("Import complete.")


if __name__ == "__main__":
    run()
