# Repository Guidelines

## Project Structure & Module Organization
The repository currently centers on `Test market and limit orders (successful).py`, a self-contained Python harness for exercising Bitget spot trading endpoints. Keep production-ready logic in a dedicated `src/` package and reserve the existing script for end-to-end smoke tests; place helper modules under `src/bitget/` and persist recorded responses or fixtures under `tests/fixtures/` to avoid cluttering the root.

## Build, Test, and Development Commands
Use Python 3.10+ and isolate work in a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv
python "Test market and limit orders (successful).py"
```
The last command runs the full interactive order test sequence; prefer smaller entry points (e.g., `python -m src.bitget.orders --dry-run`) when you add modular code.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indents, snake_case for functions and modules, and UpperCamelCase for classes. Keep lines under 100 characters and favour f-strings for logging. Scripts with spaces in their names are hard to automate—name new files snake_case and relocate sensitive constants (API keys, passphrases) into environment variables loaded via `python-dotenv`.

## Testing Guidelines
Unit tests should live under `tests/` with filenames matching the module under test (e.g., `tests/test_orders.py`). Target high-value scenarios: signature generation, quantity formatting, and order payload composition. Run `pytest` locally before opening a PR and attach Bitget sandbox transcripts when altering exchange-facing flows.

## Commit & Pull Request Guidelines
Author small, focused commits with imperative subjects such as `Add Bitget signature helper` or `Refactor limit-order formatting`. Each PR should include: a concise summary, validation evidence (commands run, screenshots, or sandbox IDs), and a checklist for credential handling. Reference issue IDs where applicable and call out any new production secrets or config switches.

## Security & Configuration Tips
Never hard-code live credentials. Export them before execution:
```bash
export BITGET_API_KEY=...
export BITGET_SECRET=...
export BITGET_PASSPHRASE=...
```
Document required env vars in the PR description and rotate keys immediately if they appear in git history.
