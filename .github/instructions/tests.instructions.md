---
description: "Use when writing or editing tests under tests/
applyTo: "tests/**/*.py"
---

# Test Guidelines

- Use `# GIVEN`, `# WHEN`, and `# THEN` comments in tests.
- Additional explanation is usually unnecessary.
- Keep test cases in alphabetical order within the current module or test class.
- Infrastructure tests may use real databases and storage backends. Other layers should prefer mocks.
