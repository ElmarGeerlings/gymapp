---
description: Ask Perplexity AI a question using MCP
argument-hint: [question to ask Perplexity]
---

# Perplexity Query: $ARGUMENTS

You have access to 3 Perplexity MCP tools with different capabilities:
- **ask**: Simple, direct questions
- **discover**: Advanced research with deeper analysis
- **research**: Complex problems requiring comprehensive investigation

## Instructions:
1. Analyze the complexity of: "$ARGUMENTS"
2. Choose the appropriate tool (ask/discover/research)
3. Be extremely verbose - add all relevant context about the stockitup codebase, business domain, or technical stack
4. Include background information that will help Perplexity provide optimal answers
5. Call the Perplexity tool directly - don't repeat the question back to the user

Context to potentially include:
- Stockitup is middleware for selling products
- Tech stack: Python/Django/Channels, PostgreSQL, Redis, RQ workers
- Business context: stock, fulfillment, analytics, logistics