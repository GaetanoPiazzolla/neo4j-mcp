# Neo4j MCP + Claude Code Skill

End-to-end guide to run a local Neo4j instance, populate it with sample data, and connect it to Claude Code in two ways:
1. directly via the official Neo4j MCP server
2. wrapped in a Claude Code skill that adds a procedural layer for schema inspection, error recovery, and result ranking.

The guide also covers MCPorter — a CLI that proxies MCP calls as plain shell commands — for token-sensitive setups and use outside of Claude.

---

## 1. Start Neo4j

```bash
docker compose up -d
```

Verify the server is running at [http://localhost:7474](http://localhost:7474).

| Field    | Value        |
|----------|--------------|
| User     | `neo4j`      |
| Password | `neo4jneo4j` |

```bash
docker compose down  # to stop
```

---

## 2. Populate the database

The import script creates the target database and loads the Northwind dataset — products, categories, suppliers, customers, orders.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run_import.py
```

Expected output:

```
Database 'mcp-test' ready.
Connected. Running 14 statement(s) from northwind.cypher
...
Import complete.
```

The script is idempotent.

---

## 3. Install the neo4j-mcp binary

Download the binary for your platform from the [official releases page](https://github.com/neo4j/mcp/releases).

**macOS (Apple Silicon):**

```bash
curl -L https://github.com/neo4j/mcp/releases/latest/download/neo4j-mcp_Darwin_arm64.tar.gz | tar xz neo4j-mcp
sudo mv neo4j-mcp /usr/local/bin/
```

**macOS (Intel):**

```bash
curl -L https://github.com/neo4j/mcp/releases/latest/download/neo4j-mcp_Darwin_x86_64.tar.gz | tar xz neo4j-mcp
sudo mv neo4j-mcp /usr/local/bin/
```

**Linux (amd64):**

```bash
curl -L https://github.com/neo4j/mcp/releases/latest/download/neo4j-mcp_Linux_x86_64.tar.gz | tar xz neo4j-mcp
sudo mv neo4j-mcp /usr/local/bin/
```

Verify installation with:

```bash
neo4j-mcp -v  
```

---

## 4. Register neo4j-mcp in Claude Code

```bash
claude mcp add \
      --transport stdio \
      -e NEO4J_URI=bolt://127.0.0.1:7687 \
      -e NEO4J_USERNAME=neo4j \
      -e NEO4J_PASSWORD=neo4jneo4j \
      -e NEO4J_DATABASE=neo4j \
      -e NEO4J_READ_ONLY=true \
      -- neo4j-mcp neo4j-mcp
```

Verify MCP is added correctly with:

```bash
claude mcp list 
```

Claude Code now has three tools available against your database:

| Tool | Description |
|---|---|
| `get-schema` | Inspect labels, relationship types, and properties |
| `read-cypher` | Run read-only Cypher queries |
| `write-cypher` | Run write queries |

### Test the integration

Try these questions in a (new) Claude Code session:

- What products are currently in stock?
- Which customers have placed the most orders?
- What are the top 5 most expensive products?
- Which suppliers provide beverages?
- What products has customer ALFKI ordered?
- Which categories have discontinued products?
- Who are the top customers by total order value?
- What products are low on stock (less than 10 units)?
- Which countries do our suppliers come from?
- What is the most ordered product of all time?

---

## 5. Create a Claude Code skill

The MCP server gives Claude the tools. A skill gives it the judgment to use them well.

A skill is a markdown file loaded on-demand into Claude's context when invoked. It sits above the raw MCP layer and encodes the decisions that the model would otherwise have to infer: inspect the schema before writing Cypher, retry with a reformulated query before surfacing an error, re-rank results by relevance rather than returning whatever the query happened to return. The LLM runs that logic natively between tool calls, chaining schema inspection, querying, and summarization within a single turn.

The skill is already included at [.claude/skills/neo4j-query/SKILL.md](.claude/skills/neo4j-query/SKILL.md). It calls the registered MCP tools directly:

```
mcp__neo4j-mcp__get-schema
mcp__neo4j-mcp__read-cypher  { query: "<CYPHER>" }
```

---

## 6. Evolving the skill from MCP to CLI via MCPorter

### What is MCPorter?

[MCPorter](https://github.com/steipete/mcporter) is a Node.js CLI that proxies calls to any MCP server as plain shell commands — useful for scripting, CI, or calling MCP tools from outside Claude entirely. Install it globally to avoid startup overhead on every invocation:

```bash
npm install -g mcporter
```

### Why bother?

When `neo4j-mcp` is registered in Claude Code, its full tool schema loads into **every conversation**, including ones that never touch the database. For large schemas or setups where every token counts, that overhead is constant and unavoidable.

A skill backed by MCPorter trades that for on-demand loading: the markdown enters context only when the skill is invoked, and the MCP registration can be removed entirely.

### Prerequisites

The `neo4j-mcp` binary must be on your PATH (step 3). The MCP registration from step 4 is not required.

### Configure MCPorter

MCPorter reads server definitions from `~/.mcporter/mcporter.json`. Credentials use `${VAR}` interpolation, so the config file itself contains no secrets:

```bash
mkdir -p ~/.mcporter
```

Create `~/.mcporter/mcporter.json`:

```json
{
  "mcpServers": {
    "neo4j-mcp": {
      "command": "neo4j-mcp",
      "env": {
        "NEO4J_URI": "${NEO4J_URI}",
        "NEO4J_USERNAME": "${NEO4J_USERNAME}",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}",
        "NEO4J_DATABASE": "${NEO4J_DATABASE:-neo4j}",
        "NEO4J_READ_ONLY": "${NEO4J_READ_ONLY:-true}"
      }
    }
  }
}
```

Credentials are read from the shell environment. Before calling MCPorter, load them from `.env`:

```bash
export $(grep -v '^#' .env | xargs)
```

### Remove the Claude Code MCP registration (optional but recommended)

If you registered `neo4j-mcp` in step 4 and want to use the CLI skill exclusively:

```bash
claude mcp remove neo4j-mcp
```

### Verify

```bash
export $(grep -v '^#' .env | xargs)
mcporter list
```

You should see `neo4j-mcp` listed with 3 tools.

### Call tools directly

MCPorter's function-call syntax handles Cypher queries cleanly without shell quoting issues:

```bash
export $(grep -v '^#' .env | xargs)
mcporter call neo4j-mcp.get-schema
mcporter call 'neo4j-mcp.read-cypher(query: "MATCH (p:Product) RETURN p.productName LIMIT 5")'
```

---

## 7. Create a Claude Code skill (CLI variant)

Same skill as section 5, but backed by MCPorter instead of the registered MCP tools. 

The skill file is at [.claude/skills/neo4j-query-cli/SKILL.md](.claude/skills/neo4j-query-cli/SKILL.md).

The skill calls MCPorter via the `Bash` tool, exporting `.env` before each call so credentials are available:

```bash
export $(grep -v '^#' .env | xargs)
mcporter call 'neo4j-mcp.read-cypher(query: "<CYPHER>")'
```

---

## 8. Conclusion — MCP, CLI, or both?

For most use cases, the MCPorter path adds complexity without much payoff.

A skill can call `mcp__neo4j-mcp__read-cypher` natively — the model still reasons between calls, error recovery still works, all the procedural logic still applies. The token overhead from registering the MCP server is real, but for local development and experimentation, it rarely matters.

MCPorter becomes worth the setup in two cases: production or token-sensitive deployments where schema loading on every turn is genuinely costly, and scripting — where its value has nothing to do with Claude at all. Once `~/.mcporter/mcporter.json` is configured, any terminal, CI job, or script can invoke Neo4j through the same MCP interface without running a separate server.

| Approach | When it makes sense |
|---|---|
| **MCP registered + skill calls tools natively** | Default. Simplest setup, full LLM reasoning, no extra tooling |
| **MCP removed + skill calls MCPorter CLI** | Token-sensitive setups where schema overhead matters every conversation |
| **MCPorter standalone** | Scripting, CI, or calling MCP tools from outside Claude entirely |
