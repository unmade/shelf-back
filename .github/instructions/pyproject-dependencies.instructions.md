---
description: "Use when adding, removing, or editing Python dependencies in pyproject.toml. Covers project dependencies, dependency groups, and lock file regeneration with uv lock."
applyTo: "pyproject.toml"
---

# Dependency Update Guidelines

- When changing dependency entries in `pyproject.toml`, regenerate the lock file with `uv lock`.
- Treat changes under both `[project].dependencies` and `[dependency-groups]` as dependency edits that require `uv lock`.
- Do not leave dependency changes in `pyproject.toml` without the corresponding regenerated lock file.
- This instruction applies to dependency changes only; unrelated `pyproject.toml` metadata edits do not require `uv lock`.
