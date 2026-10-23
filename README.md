# PaymentRuleGuard-AI — Deterministic Rule Review

Separate project for **one .NET payment application**. No vector DB, embeddings, or hybrid search.

## How it works
1. GitHub PR provides changed paths and diff.
2. Trusted base-branch `config/rule_map.json` maps C# files to rule Markdown and xUnit test classes.
3. Global rules are always included; unmapped C# files require manual review.
4. LangGraph loads mapped rules and asks Groq or Ollama to produce an **advisory** review with rule IDs.
5. CI runs actual .NET xUnit tests and coverage collection independently of the LLM.
6. GitHub Actions posts an advisory PR comment. Humans approve merges.

## Docker Compose: Ollama, API, and Streamlit

Install Docker Engine/Desktop with Docker Compose v2, then run these commands
from the repository root. Docker must have enough memory and disk for your model
(the default `llama3.2:3b` download is several GB). This configuration runs on CPU;
an NVIDIA GPU is optional and requires a separate Docker GPU configuration.

### Start

```bash
docker compose up --build -d
# Follow the initial model download (the app waits until it completes):
docker compose logs -f ollama-init
```

Press Ctrl+C to leave the logs; the containers keep running. The first start
builds the Python image and downloads the model. Later starts reuse the named
`ollama-data` volume. `ollama-init` exiting with code 0 is expected.

Once ready, open Streamlit at http://localhost:8501. The API is at
http://localhost:8000/docs and Ollama is at http://localhost:11434.
Ports bind only to the local machine. Inside Docker, Streamlit calls
`http://backend:8000` and the API calls `http://ollama:11434`.
No Groq key or host Ollama installation is required. An existing host service
using ports 11434, 8000, or 8501 must be stopped or the host ports changed in
`compose.yaml`.

### Check status and logs

```bash
docker compose ps -a
docker compose logs -f backend streamlit
curl --fail http://localhost:8000/health
curl --fail http://localhost:8501/_stcore/health
```

Use the Streamlit Review tab with the demo below to exercise the local model.
Model inference can take longer on CPU than the UI request timeout. If startup
fails, inspect `docker compose logs ollama ollama-init backend` and check available
memory, disk space, and model-registry connectivity.

### Stop and restart

```bash
# Stop containers, retaining them and the downloaded model:
docker compose stop
# Start again (also recreates containers if configuration changed):
docker compose up -d
# Remove containers and the Compose network, retaining the downloaded model:
docker compose down
```

To rebuild after code/dependency changes, run `docker compose up --build -d`.
To delete the downloaded model as well, run `docker compose down --volumes`.
This permanently removes the `ollama-data` volume; the next start downloads again.

### Choose another Ollama model

Create a `.env` file in the repository root (separate from `backend/.env`):

```dotenv
OLLAMA_MODEL=llama3.2:3b
```

Set this to your preferred Ollama model tag and run `docker compose up -d`.
Compose passes the same model name to the download job and backend. Model pulls
need Internet access to Ollama's registry and artifact storage. The Compose
stack explicitly selects Ollama; `backend/.env` Groq settings do not override it.

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

## LangGraph, LangChain, and Groq integration

The compiled graph follows `START → retrieve_rules → review_change → END`.
Unmapped C# files or missing rules route to `manual_review → END` without calling a model.
The review node uses a LangChain `ChatPromptTemplate | ChatGroq/ChatOllama | StrOutputParser`
chain. FastAPI and the GitHub review script share this graph.

For Groq, configure `backend/.env` (never commit your key):
```dotenv
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=<your-key>
```
The backend loads this file automatically; injected environment variables take precedence.
For GitHub Actions, open repository **Settings → Secrets and variables → Actions**:
- Add `GROQ_API_KEY` under **Secrets**.
- Optionally add `GROQ_MODEL` under **Variables** with a Groq model ID available to your account.
  The workflow defaults to `llama-3.3-70b-versatile` when this variable is unset.

The model name is configuration, not a secret. The API key stays in Actions secrets.
Groq requests use a 60-second timeout and two retries. Ollama remains the default local provider.

Run `python -m pytest tests -q` after installing `backend/requirements.txt` to verify
retrieval, graph routing, LangChain prompt/output handling, and provider configuration.
These tests use a fake model and do not require credentials or contact an LLM service.
A live Groq review additionally requires a valid key and access to `api.groq.com`.

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
