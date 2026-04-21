## Summary

Shelf Back is the backend for a self-hosted file manager with a dedicated Photos app. It manages namespaces, files, sharing, thumbnails, and photo workflows on top of storage-backed blobs while keeping application code isolated from infrastructure details.

## Terminology

- Blob: storage primitive that represents an item in storage; app-specific entities build on top of it.
- File: Files app entity for a user file or folder inside a Namespace.
- MediaItem: Photos app entity for an image, and later video; on the database layer it is composed from Blob and MediaItem models.
- Namespace: root storage space owned by a user account.
- Use Case: workflow orchestration layer called by the API.
- Service: reusable business-logic layer that depends on protocols, not concrete infrastructure adapters.

## Architecture

The backend is written in Python using FastAPI for the API, Tortoise ORM for database interactions, and Arq for background tasks. The codebase is organized into layers to maintain separation of concerns and promote testability.

The backend is mid-migration toward Blob-centered storage concerns. Prefer changes that move Files in that direction instead of adding new app-specific storage coupling.

- Respect the layered flow: API -> usecases -> services -> infrastructure. Domain models may be shared, but each layer should only call the next valid layer.
- `app/app` is the application layer and must stay infrastructure-agnostic. Define protocols there and implement them under `app/infrastructure`.
- `app/app/files` - contains the business logic for the Files app.
- `app/app/photos` - contains the business logic for the Photos app.
- `app/app/files` and `app/app/photos` are isolated and must not import each other. Shared storage concerns belong in `app/app/blobs`.
- Tortoise ORM is the persistence layer. Repository protocols live in the application layer; Tortoise repositories live in infrastructure.

## Task planning and problem-solving

- Before each task, you must first complete the following steps:
  1. Provide a full plan of your changes.
  2. Provide a list of behaviors that you'll change.
  3. Provide a list of test cases to add.
- Start by identifying the correct layer for the change and keep logic in the highest valid layer instead of leaking infrastructure details upward.
- Before you add any code, always check if there is a similar case in the codebase and align with it.
- If a contract changes, update the application protocol first, then align every infrastructure implementation and its tests.
- For database changes, keep Tortoise models, repositories, and migrations in sync.
- Preserve app isolation: do not introduce cross-imports between Files and Photos; use Blob as the shared primitive.
- Keep coverage at 100%.
- Before adding a new test, always make sure that a similar test
  doesn't exist already.
- If you add new code or change existing code, always verify that everything still works by running *each* of the following checks:
  1. `source ./.venv/bin/activate` to activate the virtual environment (if not already active)
  2. `pre-commit run --all-files` to run set of linters (make sure you run from the venv)
  3. `pytest . --cov` to run tests and confirm coverage (make sure you run from the venv)

## Coding guidelines

- API handlers should call usecases, not services or infrastructure directly.
- Usecases should depend on services; services should depend on protocols from `app/app/infrastructure` or on primitive services.
- Follow existing code style and patterns. If you find yourself writing new patterns, check if they already exist in the codebase and align with them.
- Maintain alphabetical order for methods and classes.
- Keep Blob reusable for current and future apps, such as Files, Photos, and potential new domains built on the same storage primitive.
