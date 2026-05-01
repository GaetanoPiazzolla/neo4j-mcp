---
name: neo4j-query
description: >
  Query the local Neo4j database using natural language. Use this skill whenever
  the user asks anything about products, customers, orders, suppliers, categories,
  or any other data in the graph — even if they don't say "Neo4j" or "Cypher".
  Translates questions into Cypher, executes them via the neo4j-mcp MCP tools,
  and reasons over results before responding. Invoke for lookups, aggregations,
  graph traversals, rankings, stock checks, and relationship queries of any kind.
---

## Prerequisites

The `neo4j-mcp` MCP server must be registered in Claude Code (see step 4 of the README).
`read-cypher` validates queries server-side via `EXPLAIN` before execution — no need
to run EXPLAIN manually in this skill.

## Standard Operating Procedure

### 1. Classify the question

| Type | Pattern |
|---|---|
| Lookup | Single entity by name or ID → `MATCH … WHERE` |
| Aggregation | Counts, totals, rankings → `RETURN … ORDER BY … LIMIT` |
| Traversal | Relationships between entities → multi-hop `MATCH` with pattern |
| Filter | Subset by property → `WHERE` with conditions |

### 2. Check schema when uncertain

If the question involves labels or properties you are not sure about, call
`mcp__neo4j-mcp__get-schema` first. Do not guess property names — wrong names
produce empty results, not errors.

### 3. Write the Cypher query

- Never string-interpolate user input — use inline literal values only
- Use `LIMIT` on open-ended queries (default 25)
- Exclude discontinued products unless explicitly asked: `WHERE p.discontinued = false`
- Prefer `MATCH … RETURN` over `MATCH … WITH … RETURN` unless aggregation requires it

### 4. Execute

Call `mcp__neo4j-mcp__read-cypher` with the query as a parameter.

After receiving results:
- Empty result set → re-examine property names or relationship direction, retry once
- Too many rows → add `LIMIT` or tighten the `WHERE` clause
- Ambiguous question → use LLM judgment to pick the most relevant rows

### 5. Format the response

- Lists → markdown table with the most relevant columns
- Single value → one sentence
- Graph traversal → describe the path in plain language before showing data
- Note edge cases (out-of-stock but not discontinued, ties in rankings)

## Error Recovery

| Error | Action |
|---|---|
| `property not found` | Call `mcp__neo4j-mcp__get-schema`, correct the property name, retry |
| `relationship direction` | Reverse the arrow in the pattern, retry |
| `syntax error` | Re-read the Cypher, fix the clause, retry |
| After 2 failed retries | Surface the error with the last query attempted |

## Example Patterns

**Top customers by order count:**
```cypher
MATCH (c:Customer)-[:PURCHASED]->(o:Order)
RETURN c.companyName AS customer, count(o) AS orders
ORDER BY orders DESC LIMIT 10
```

**Products supplied by a specific country:**
```cypher
MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)-[:PART_OF]->(c:Category)
WHERE s.country = 'Germany'
RETURN p.productName AS product, c.categoryName AS category, s.companyName AS supplier
ORDER BY category, product
```

**Low stock alert (active products only):**
```cypher
MATCH (p:Product)
WHERE p.unitsInStock < 10 AND p.discontinued = false
RETURN p.productName AS product, p.unitsInStock AS stock
ORDER BY stock ASC
```

**Most ordered product of all time:**
```cypher
MATCH (p:Product)<-[:ORDERS]-(:Order)
RETURN p.productName AS product, count(*) AS times_ordered
ORDER BY times_ordered DESC LIMIT 1
```
