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
http://localhost:8000/docs. Ollama is available only inside the Compose network;
it does not publish a host port, so an existing Windows/host Ollama can keep running.
The API and Streamlit ports bind only to the local machine. Inside Docker, Streamlit calls
`http://backend:8000` and the API calls `http://ollama:11434`.
No Groq key or host Ollama installation is required. An existing host service
using ports 8000 or 8501 must be stopped or the host ports changed in
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

### Update an existing checkout (including the Ollama port conflict fix)

From the repository root in PowerShell or a terminal:

```bash
git pull --ff-only origin main
docker compose down
docker compose up --build -d
docker compose logs -f ollama-init
```

This retains the downloaded models. If Git reports local edits to `compose.yaml`,
back up your changes and resolve them before pulling. The updated `ollama` service
has no `ports` section. If Docker still reports a bind on port 11434, run
`docker compose config` and check for an old port mapping in a Compose override file.

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

## Scenarios to test in Streamlit

Start the stack, open http://localhost:8501, and select **PR Review**.
For each scenario below, copy the path into **Changed C# file**, paste the diff
into **Paste Git diff**, and click **Review change**. Wait for **Review complete**;
local CPU inference can take several minutes. Expand **Mapped rules and tests**
to inspect the evidence.

These snippets are review inputs; pasting them does not modify or execute the .NET
application. AI wording and findings may vary. The rule IDs and mapped tests below
are the expected evidence; check whether the model explains the relevant violation.
The UI does not run xUnit tests and must not claim they passed.

### 1. Zero-value payment is accepted

Path: `src/Payments/PaymentService.cs`

```diff
- if (amount <= 0) throw new ArgumentOutOfRangeException(nameof(amount));
+ if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
```

Expected finding: zero payments are now allowed, violating **PR-001** in
`rules/global.md`. Evidence should map `PaymentRuleGuard.Tests.PaymentTests`;
the relevant test is `RejectsNonPositiveAmounts`.

### 2. Duplicate charge protection is removed

Path: `src/Payments/PaymentService.cs`

```diff
- return _processed.Add(idempotencyKey);
+ return true;
```

Expected finding: repeated requests report a new successful charge, violating
**PR-002** in `rules/global.md`. Recommend
`PaymentTests.RepeatedKeyDoesNotCreateSecondCharge`.

### 3. Refund exceeds the captured amount

Path: `src/Refunds/RefundService.cs`

```diff
- if (amount <= 0 || amount > capturedAmount) throw new ArgumentOutOfRangeException(nameof(amount));
+ if (amount <= 0) throw new ArgumentOutOfRangeException(nameof(amount));
```

Expected finding: an excessive refund is accepted, violating **RF-001** in
`rules/refunds.md`. Evidence includes global and refund rules and maps
`PaymentRuleGuard.Tests.RefundTests`. Recommend `RefundTests.RejectsInvalidRefunds`.

### 4. Duplicate refund protection is removed

Path: `src/Refunds/RefundService.cs`

```diff
- return _refunded.Add(requestKey);
+ return true;
```

Expected finding: repeated refund keys succeed again, violating **RF-002** in
`rules/refunds.md`. Recommend `RefundTests.DuplicateRefundKeyDoesNotRefundAgain`.

### 5. Sensitive payment information is logged

Path: `src/Payments/PaymentService.cs`

```diff
+ logger.LogInformation("Card={CardNumber}, CVV={Cvv}", cardNumber, cvv);
```

Expected finding: logging card details violates **PR-003** in `rules/global.md`.
Use only placeholder data. This is an illustrative snippet; the sample service has
no logger/card fields. No dedicated PR-003 xUnit test exists yet; the reviewer
should recommend adding one rather than inventing a passing test.

### 6. Transaction is completed before provider confirmation

Path: `src/Transactions/TransactionService.cs`

```diff
- var confirmation = await provider.ChargeAsync(request);
- payment.Status = confirmation.Success ? "Completed" : "Failed";
+ payment.Status = "Completed";
+ var confirmation = await provider.ChargeAsync(request);
```

Expected finding: **TX-001** in `rules/transactions.md` is violated. Evidence maps
`PaymentRuleGuard.Tests.TransactionTests` and also includes **TX-002** and global
rules. The existing transaction integration test is **skipped**, not passed.
This illustrative service is not implemented in the sample .NET project.

### 7. Unknown C# component requires manual review

Path: `src/Unknown/Unknown.cs`

```diff
+ public bool Process() => true;
```

Expected deterministic result: `MANUAL REVIEW REQUIRED: unmapped C# paths:` followed
by the path. No LLM call is made, so this scenario works even without a model or
API key once the backend is running. Inspect `evidence.unmapped` for the same path.

### 8. A valid guard is restored

Path: `src/Payments/PaymentService.cs`

```diff
- if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
+ if (amount <= 0) throw new ArgumentOutOfRangeException(nameof(amount));
```

Expected review: recognize that this fixes the zero-value payment check under
**PR-001**. It should recommend verification without claiming tests ran or approving
a merge. This is a useful comparison with scenario 1, not proof of whole-app safety.

### Run the actual automated tests

From the repository root with Python dependencies and .NET SDK 8 installed:

```bash
python -m pytest tests -q
dotnet test sample-dotnet/PaymentRuleGuard.Tests/PaymentRuleGuard.Tests.csproj --configuration Release
```

Python tests validate retrieval and the mocked review flow; they do not assess a
live model's accuracy. The .NET tests exercise the sample payment/refund services;
the provider/database transaction integration test remains skipped.

To reproduce a real failure for scenario 1, temporarily change `amount <= 0` to
`amount < 0` in `sample-dotnet/PaymentRuleGuard/PaymentService.cs`, then run:

```bash
dotnet test sample-dotnet/PaymentRuleGuard.Tests/PaymentRuleGuard.Tests.csproj --filter "FullyQualifiedName~RejectsNonPositiveAmounts"
```

The zero-amount case should fail while the negative-amount case still passes.
Restore the original guard afterward and rerun the same command. Make this local
experiment only with a clean file or a backup; do not commit the intentional bug.

## Run GitHub Actions manually

1. Open [Actions](https://github.com/rvnextgendev/PaymentRuleGuard-AI/actions)
   and select **PaymentRuleGuard AI Review**.
2. Click **Run workflow**, choose `main` (or a branch containing this workflow),
   and click **Run workflow** again.
3. Open the run and expand the .NET and Python test steps to inspect their output.

Manual runs execute the test job. The AI-comment job is intentionally skipped:
there is no pull request diff or comment destination on a manual run. No Groq key
is needed for this test job. A failed .NET step prevents later Python steps in
that job from executing; run Python separately locally when diagnosing both.

To test the **AI PR comment**, configure the repository Actions secret
`GROQ_API_KEY`, then use a branch in this repository:

```powershell
git checkout main
git pull --ff-only origin main
git checkout -b test/payment-review
```

Temporarily change `amount <= 0` to `amount < 0` in
`sample-dotnet/PaymentRuleGuard/PaymentService.cs`, then:

```powershell
git add sample-dotnet/PaymentRuleGuard/PaymentService.cs
git commit -m "Test zero payment regression detection"
git push -u origin test/payment-review
```

Open a PR targeting `main`. In **Checks**, expect the .NET zero-value case to fail;
the independent AI job should post an advisory comment citing PR-001. Fix the guard,
commit, and push again to rerun. Do not merge the intentional regression. Fork PRs
skip the AI-comment job. Groq rate limits, missing keys, and provider errors appear
in the AI job logs; model findings are not deterministic test assertions.

## Manual local testing and debugging

### Visual Studio: sample .NET solution

Open `sample-dotnet/PaymentRuleGuard.sln` in Visual Studio 2022 with .NET 8 support.
The solution contains both the class library and xUnit test project. Build it,
open **Test → Test Explorer**, and run the tests. To debug, set a breakpoint inside
`PaymentService.Charge` or `RefundService.Refund`, right-click the corresponding
test, and select **Debug**. Inspect `amount`, the request key, and the return value.
This is a library, so use the tests rather than trying to launch it as a web app.

From a terminal in the repository root:

```powershell
dotnet test sample-dotnet/PaymentRuleGuard.sln --configuration Debug
dotnet test sample-dotnet/PaymentRuleGuard.sln --filter "FullyQualifiedName~RepeatedKeyDoesNotCreateSecondCharge" --logger "console;verbosity=detailed"
```

The transaction integration test remains skipped until provider/database fixtures
exist. A skipped test does not prove transaction correctness.

### VS Code: API and Streamlit breakpoints

Install the Microsoft **Python** and **Python Debugger** extensions. From the
repository root, create a Python environment and install dependencies:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
# Copy only if backend/.env does not already exist:
Copy-Item backend/.env.example backend/.env
```

Select `backend/.venv` using **Python: Select Interpreter**. Configure `backend/.env`
for either host Ollama (`OLLAMA_BASE_URL=http://localhost:11434`) or Groq
(`LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL`). Do not commit your key.
For host Ollama, run `ollama pull llama3.2:3b` first. This local debugging mode
needs host Ollama or Groq; the Compose Ollama service does not publish a host port.

Stop the Compose stack with `docker compose down` to free ports 8000 and 8501.
In **Run and Debug**, select **Debug FastAPI review API**, then press F5. Set
breakpoints in `backend/app.py`, `backend/review.py` (`collect`, `route_review`,
`analyze`), and `backend/retrieval.py`. Open http://localhost:8000/docs and execute
`POST /review` with:

```json
{
  "diff": "- if (amount <= 0)\n+ if (amount < 0)",
  "changed_paths": ["src/Payments/PaymentService.cs"]
}
```

Inspect the mapped evidence before stepping into the model call. To debug without
an LLM, use `src/Unknown/Unknown.cs`; the graph routes to manual review.
For the UI, start a second debugging session using **Debug Streamlit UI**, open
http://localhost:8501, and click **Review change**. Both API and UI need to run;
`API_URL` should be `http://localhost:8000`. Stop sessions with Shift+F5.

### Python tests and Docker logs

```powershell
python -m pytest tests -v
# Enter Python's debugger on a failing test:
python -m pytest tests -x --pdb
# Inspect running Compose services (when using Docker instead of F5):
docker compose ps -a
docker compose logs --tail 100 backend streamlit ollama ollama-init
```

Python model tests use a fake response and require no key. For a live model check,
use the API or Streamlit scenarios above. On a review timeout, inspect backend and
Ollama logs and machine memory; on a connection error, verify the API is healthy.
Do not share logs containing keys or sensitive payment data.

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
