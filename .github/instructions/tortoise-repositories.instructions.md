---
description: "Use when editing Tortoise ORM repositories under app/infrastructure/database/tortoise/repositories/. Covers single-row query style, N+1 avoidance, raw SQL avoidance, and Tortoise query docs."
applyTo: "app/infrastructure/database/tortoise/repositories/**/*.py"
---

# Tortoise Repository Guidelines

- When a query should return exactly one row and that is enforced by a primary key or other uniqueness constraint, prefer `.get(...)` with `except DoesNotExist` over `.filter(...).first()`.
- Avoid N+1 query patterns. Prefer batching, prefetching, aggregation, or other set-based ORM queries when loading related data.
- Avoid raw SQL unless there is no reasonable ORM alternative and the tradeoff is explicit.
- Use the following Tortoise ORM docs as a reference when writing or editing ORM queries in repositories:
  - https://tortoise.github.io/query.html - Tortoise ORM query reference
  - https://tortoise.github.io/functions.html - Tortoise ORM query functions & aggregations reference
  - https://tortoise.github.io/expressions.html - Tortoise ORM expressions reference
