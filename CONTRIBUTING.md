# Contributing

Thanks for helping improve GitHub Stars Badge API. This guide explains the local workflow and expectations for small, reviewable pull requests.

## Getting started

1. Fork and clone the repository.
2. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install the project and development dependencies:

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. Copy the sample environment file if you want to run against a GitHub token:

   ```bash
   cp .env.example .env
   ```

   `GITHUB_TOKEN` is optional for local development, but it helps avoid GitHub API rate limits.

5. Start the API locally:

   ```bash
   python -m src
   ```

## Code standards

- Follow PEP 8 naming and formatting conventions.
- Add type hints to new public functions and service methods where practical.
- Keep API handlers thin; put GitHub API and caching behavior in the service/storage layers.
- Avoid committing generated cache/database files such as `store.db`, `index.db`, or local LMDB directories.
- Keep documentation updates in sync with any endpoint, environment variable, or response-shape changes.

## Tests and checks

Run the test suite before opening a pull request:

```bash
pytest
```

Run the same quality checks as CI when you touch application code:

```bash
pylint src/ --rcfile=.pylintrc
black --check src/
mypy src/
```

To run these checks before each commit, you can install a local Git hook:

```bash
cat > .git/hooks/pre-commit <<'SH'
#!/bin/sh
set -e
pylint src/ --rcfile=.pylintrc
black --check src/
mypy src/
SH
chmod +x .git/hooks/pre-commit
```

If you change endpoints, also test the affected route manually against the local server with `curl` or your browser.

## Commit conventions

Use short, descriptive commit messages. Conventional Commit prefixes are encouraged:

- `fix:` for bug fixes
- `feat:` for new behavior
- `docs:` for documentation-only updates
- `test:` for test additions or updates
- `chore:` for maintenance tasks

Examples:

```text
fix: handle missing repository names
docs: add badge usage example
test: cover user star count caching
```

## Pull request process

1. Create a focused branch, for example `docs/contributing-guide` or `fix/repo-badge-cache`.
2. Keep each PR scoped to one problem or issue.
3. Include a clear summary of what changed and why.
4. Link the related issue when one exists.
5. Paste the commands you ran, such as `pytest` or `pylint src/`.
6. Call out any follow-up work that is intentionally left for a separate PR.

Reviewers should be able to understand the change, reproduce the checks, and merge without unrelated cleanup mixed in.
