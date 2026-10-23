# PaymentRuleGuard-AI — Deterministic Rule Review

Separate project for **one .NET payment application**. No vector DB, embeddings, or hybrid search.

## How it works
1. GitHub PR provides changed paths and diff.
2. Trusted base-branch `config/rule_map.json` maps C# files to rule Markdown and xUnit test classes.
3. Global rules are always included; unmapped C# files require manual review.
4. LangGraph loads mapped rules and asks Groq or Ollama to produce an **advisory** review with rule IDs.
5. CI runs actual .NET xUnit tests and coverage collection independently of the LLM.
6. GitHub Actions posts an advisory PR comment. Humans approve merges.

## Local setup
- Requirements: Python 3.11+, .NET SDK 8, and Ollama (or Groq API key).
- `cd backend`
- `python -m venv .venv` and activate it
- `pip install -r requirements.txt`
- Copy `.env.example` to `.env`
- For Ollama: `ollama pull llama3.2:3b` and set `LLM_PROVIDER=ollama`
- For Groq: set `LLM_PROVIDER=groq` and `GROQ_API_KEY`
- Terminal A: `uvicorn app:app --reload --port 8000`
- Terminal B: `streamlit run streamlit_app.py`
- UI: http://localhost:8501
- Rule tests: from repository root, `python -m pytest tests -q`
- .NET tests: `dotnet test sample-dotnet/PaymentRuleGuard.Tests/PaymentRuleGuard.Tests.csproj --collect:"XPlat Code Coverage"`

## Demo scenario
Review `src/Payments/PaymentService.cs` with diff:
```
- if (amount <= 0)
+ if (amount < 0)
```
Rule `PR-001` says zero-value payments are invalid, and `PaymentTests.RejectsNonPositiveAmounts` covers it.
For a *real test failure*, change the condition in `sample-dotnet/PaymentRuleGuard/PaymentService.cs` and run `dotnet test`.

## Adding a new rule
1. Add a unique rule ID and Markdown text.
2. Map its component file globs and test class in `config/rule_map.json`.
3. Add an xUnit test that checks the invariant; include the rule ID in its comment.
4. Add an integration test for rules involving DB/provider side effects.
5. Review and merge the mapping, rule, and test together.

## Important production gaps (do not skip)
- This is a **production-oriented reference**, NOT a certified production deployment.
- Sample in-memory idempotency is not durable or concurrency-safe. Production requires a database unique constraint and transaction.
- `PR-003` is a documented rule, not yet automatically enforced. Add secret scanners and logging tests.
- `TX-001/TX-002` integration tests are intentionally skipped until real database/provider test infrastructure exists.
- Coverage is collected, but a minimum threshold and rule-to-test completeness enforcement are not yet implemented.
- GitHub file patch API may truncate patches; verify full diff integrity and handle large PRs before rollout.
- Restrict who can edit workflow/rules/mappings with CODEOWNERS and branch protection.
- LLM results are advisory; protect sensitive code and secrets before sending to external providers.
- Add GitHub App authentication, rate limits, retries, observability, structured output, and PR comment deduplication.
- Never execute untrusted PR code in the privileged AI-review job.
