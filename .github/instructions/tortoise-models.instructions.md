---
description: "Use when editing Tortoise ORM models in app/infrastructure/database/tortoise/models.py. Covers required migrations, safe rollout patterns, confirmation before applying migrations, and Tortoise model docs."
applyTo: "app/infrastructure/database/tortoise/models.py"
---

# Tortoise Model Guidelines

- Any change to a model in this file must be accompanied by a migration.
- Generate migrations with `tortoise -c app.infrastructure.database.tortoise.migrations._config.TORTOISE_ORM makemigrations`.
- Apply migrations with `tortoise -c app.infrastructure.database.tortoise.migrations._config.TORTOISE_ORM migrate`.
- Ask for confirmation before running `tortoise migrate` or any other migration-application command.
- Migrations must be backward compatible and safe to apply. Prefer additive, multi-step rollouts over breaking one-step schema changes.
- Example: when adding a new required field to an existing table, add it as nullable or with a safe default, backfill data, then make it non-nullable in a later migration.
- Use the following Tortoise ORM docs when changing models or schema definitions:
- https://tortoise.github.io/models.html - Tortoise ORM models reference
- https://tortoise.github.io/fields.html - Toroise ORM fields reference
- https://tortoise.github.io/indexes.html - Tortoise ORM indexes reference
- https://tortoise.github.io/migration.html - Tortoise ORM migrations reference
