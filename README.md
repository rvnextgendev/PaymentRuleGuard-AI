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

### Debug Python locally on Windows with VS Code

Run the Python processes on your computer to hit local breakpoints. Rebuilding a
Docker image is not needed for this workflow. Open the **repository root folder**
in VS Code (the folder containing `.vscode/launch.json`), not only `backend`.
Install the Microsoft **Python** and **Python Debugger** extensions.

#### Complete VS Code walkthrough: local Python + Docker Ollama

Follow this sequence when debugging Python on Windows while Ollama runs in Docker.
Docker Desktop must be running. Python runs under the VS Code debugger, while
only Ollama and its model-download job need Docker.

1. Stop your existing API: click the terminal running Uvicorn and press **Ctrl+C**.
   If a VS Code debug session is running, stop it with **Shift+F5**.
2. Select **File → Open Folder** and open
   `C:\Users\RajeshDas\PaymentRuleGuard-AI` (or your checkout location).
   Open the repository root, not just `backend`; `.vscode/launch.json` must be
   inside the opened folder.
3. Open **Terminal → New Terminal**. From the repository root, update the code
   and install dependencies. The `.env` copy below preserves an existing file:

   ```powershell
   git pull --ff-only origin main
   # Create the environment only if it does not already exist:
   if (-not (Test-Path backend/.venv/Scripts/python.exe)) {
       python -m venv backend/.venv
   }
   .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
   if (-not (Test-Path backend/.env)) {
       Copy-Item backend/.env.example backend/.env
   }
   docker compose stop backend streamlit
   docker compose -f compose.yaml -f compose.debug.yaml up -d ollama ollama-init
   docker compose -f compose.yaml -f compose.debug.yaml logs -f ollama-init
   ```

   Wait for the model download to complete. Press **Ctrl+C** to leave the logs;
   this does not stop Ollama. If Git reports local edits, preserve and resolve
   them before pulling; do not discard your changes.
4. Open `backend/.env` in VS Code and set:

   ```dotenv
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2:3b
   OLLAMA_BASE_URL=http://localhost:11435
   API_URL=http://localhost:8000
   ```

   Verify the published Docker endpoint from the terminal:

   ```powershell
   Invoke-RestMethod http://localhost:11435/api/tags
   ```

   The model list should contain `llama3.2:3b`. If the connection fails, follow
   **Local Python with Docker Ollama: fix connection refused** below before F5.
5. Press **Ctrl+Shift+X** and install Microsoft's **Python** and **Python Debugger**
   extensions.
6. Press **Ctrl+Shift+P**, search for **Python: Select Interpreter**, and choose
   `backend\.venv\Scripts\python.exe`. If it is missing, select
   **Enter interpreter path → Find** and browse to that executable.
7. Open `backend/app.py`. Click the left margin beside
   `return review_diff(req.diff, req.changed_paths)`; a red breakpoint dot appears.
   For graph debugging, add breakpoints in `backend/review.py` inside `collect`,
   `route_review`, and `analyze`.
8. Press **Ctrl+Shift+D** to open **Run and Debug**. Select
   **Debug FastAPI review API** from the top dropdown and press **F5**. The launch
   configuration explicitly uses `backend/.venv`. Wait for application startup
   complete in the terminal. Do not start another terminal Uvicorn process.
9. Open http://localhost:8000/docs, expand **POST /review**, click **Try it out**,
   replace the example body with the following JSON, and click **Execute**:

   ```json
   {
     "diff": "- if (amount <= 0)\n+ if (amount < 0)",
     "changed_paths": ["src/Payments/PaymentService.cs"]
   }
   ```

10. VS Code should pause at the breakpoint. Inspect `req.diff` and
    `req.changed_paths` under **Variables**. Use **F10** to step over, **F11** to
    step into, **Shift+F11** to step out, and **F5** to continue. Continue until
    Swagger receives the review. The model should identify the PR-001 zero-value
    payment issue; wording varies and no .NET tests run from this request.
11. To debug Streamlit as well, keep the API session running, set a breakpoint
    at `r = requests.post(...)` in `backend/streamlit_app.py`, select
    **Debug Streamlit UI**, and click the green play button to start a second
    debug session. Open http://localhost:8501 and click **Review change**.
    Continue each session when its breakpoint is hit.
12. When finished, stop both Python sessions with **Shift+F5** (select each
    session as needed). To stop Docker Ollama while keeping its downloaded model:

    ```powershell
    docker compose -f compose.yaml -f compose.debug.yaml down
    ```

For a model-free API check at step 9, use `src/Unknown/Unknown.cs` as the changed
path. The graph returns manual review and skips the model call and `analyze` node.

#### 1. Prepare the Python interpreter

Open a PowerShell terminal in the repository root:

```powershell
python --version  # Python 3.11 or newer
python -m venv backend/.venv
# Use the environment's executable directly; activation is optional:
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
if (-not (Test-Path backend/.env)) {
    Copy-Item backend/.env.example backend/.env
}
```

Press Ctrl+Shift+P, choose **Python: Select Interpreter**, then select
`backend/.venv/Scripts/python.exe`. If it is not listed, choose **Enter interpreter
path** and browse to it. The checked-in debug configurations use this interpreter.

For macOS/Linux, use `python3 -m venv backend/.venv`, install with
`backend/.venv/bin/python -m pip install -r backend/requirements.txt`, and select
`backend/.venv/bin/python` instead.

#### 2. Choose Groq or local Ollama

Edit `backend/.env`. For Groq:

```dotenv
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=<your-real-key-entered-only-in-this-local-file>
API_URL=http://localhost:8000
```

GitHub Actions secrets are not automatically available on your computer. Never
commit your key or paste it into screenshots. `backend/.env` is ignored by Git.
Alternatively, for Ollama running on your computer:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
API_URL=http://localhost:8000
```

Start host Ollama and run `ollama pull llama3.2:3b`. The Compose Ollama service is
internal-only, so it is not reachable at the host URL above. Restart your debug
session after editing `.env`. Existing process environment variables take precedence
if they have the same names.

#### 3. Debug the API first

Stop the Compose stack with `docker compose down` to free ports 8000 and 8501.
This keeps downloaded models. In VS Code:

1. Open `backend/app.py` and click the left gutter beside
   `return review_diff(req.diff, req.changed_paths)` to set a breakpoint.
2. Add breakpoints in `backend/review.py` inside `collect`, `route_review`, and
   `analyze`, and in `backend/retrieval.py` inside `retrieve`.
3. Open **Run and Debug** (Ctrl+Shift+D), select **Debug FastAPI review API**,
   and press F5. Wait for Uvicorn to report application startup complete.
4. Open http://localhost:8000/docs, expand **POST /review**, click **Try it out**,
   paste the JSON below, and click **Execute**:

```json
{
  "diff": "- if (amount <= 0)\n+ if (amount < 0)",
  "changed_paths": ["src/Payments/PaymentService.cs"]
}
```

The debugger should pause at the API breakpoint. Inspect `req.diff` and
`req.changed_paths` in **Variables**. In the graph, inspect `state` and its
`evidence` field, including rule sources, unmapped paths, and mapped tests.
Use F10 to step over, F11 to step into your code, Shift+F11 to step out, and F5
to continue. LangGraph schedules nodes, so breakpoints in each node are the
clearest way to follow the flow. Shift+F5 stops the selected session.

For a model-free check, send the same request with
`changed_paths: ["src/Unknown/Unknown.cs"]`. It should pause in `collect` and
`route_review`, then return manual review without entering `analyze`.

You can also trigger a request from a second PowerShell terminal:

```powershell
$reviewBody = @{
    diff = "- if (amount <= 0)`n+ if (amount < 0)"
    changed_paths = @("src/Payments/PaymentService.cs")
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/review -ContentType "application/json" -Body $reviewBody
```

#### 4. Debug the Streamlit button

Keep the API debug session running. Set a breakpoint in
`backend/streamlit_app.py` at `r = requests.post(...)`. Select
**Debug Streamlit UI** in **Run and Debug** and start a second session using the
green play button. Open http://localhost:8501 and click **Review change**.

The UI breakpoint pauses before the request. Continue with F5, then switch to the
API session when its breakpoint is hit. Continue both sessions to see the review
result. The UI waits up to ten minutes for the API; long pauses at API breakpoints
can cause a timeout. Use `/docs` directly when stepping slowly through backend code.

#### 5. Debug Python tests without an API key

With the selected virtual environment, open the VS Code **Testing** panel, choose
**Configure Python Tests**, select **pytest**, then select the `tests` folder.
Set a breakpoint in `backend/review.py` or `backend/retrieval.py`, and use **Debug
Test** beside a test such as `test_graph_runs_langchain_with_mapped_evidence`.
The model is mocked for that test, so Ollama and Groq are not required.

To start directly in Python's terminal debugger:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests/test_review.py::test_graph_runs_langchain_with_mapped_evidence --trace -s
```

Use `n` for next, `s` to step into, `p state` when inside a graph node to inspect
state, `c` to continue, and `q` to quit. Use `--pdb` instead of `--trace` to enter
the debugger only after a test failure.

#### If a breakpoint does not hit

- A hollow breakpoint usually means the file has not loaded yet or the wrong
  interpreter/file is being used. Check the selected interpreter and open the root folder.
- A breakpoint inside `if st.button(...)` needs an actual button click.
- An `analyze` breakpoint will not hit for an unmapped C# path; that route skips the LLM.
- If the API returns results but local breakpoints never hit, stop old terminal
  Uvicorn processes and Docker services; send the request to the F5-launched API.
- For `ModuleNotFoundError`, install requirements using the same interpreter VS Code selected.
- For port errors, stop the previous debug session or container using 8000/8501.
- The API launch configuration intentionally omits `--reload` to keep debugging in
  one process. Stop and restart the debug session after backend code changes.

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

### Local Python with Docker Ollama: fix connection refused

`WinError 10061` means no service is accepting connections at the configured
Ollama address. Use the optional debug Compose override to publish port 11435
without conflicting with Windows Ollama on 11434. From the repository root:

```powershell
docker compose stop backend streamlit
docker compose -f compose.yaml -f compose.debug.yaml up -d ollama ollama-init
docker compose -f compose.yaml -f compose.debug.yaml logs -f ollama-init
```

Wait for the model download to finish, then press Ctrl+C to leave logs.
Verify the server and model directly:

```powershell
Invoke-RestMethod http://localhost:11435/api/tags
```

The returned model list should contain `llama3.2:3b`. Set `backend/.env`:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11435
API_URL=http://localhost:8000
```

Stop any terminal Uvicorn process with Ctrl+C, stop previous debug sessions, and
press F5 with **Debug FastAPI review API** selected. The checked-in configuration
explicitly uses the repository `backend/.venv` interpreter on Windows/macOS/Linux.
If that environment does not exist, create and install it using the steps above.
Do not launch using a global Python that reports `No module named uvicorn`.

If `/api/tags` still refuses connections, inspect
`docker compose -f compose.yaml -f compose.debug.yaml ps -a` and the Ollama logs.
If no 11435 mapping appears, check the rendered configuration with
`docker compose -f compose.yaml -f compose.debug.yaml config`.
Use the same `-f` arguments for subsequent Compose updates while debugging;
plain `docker compose up` can recreate Ollama without the debug port mapping.
To stop this stack, use
`docker compose -f compose.yaml -f compose.debug.yaml down`; models are retained.

### Fix `model 'llama3.2:3b' not found`

This means Ollama is reachable but the selected model is missing on that server.
For Python running locally against Windows Ollama, run:

```powershell
ollama pull llama3.2:3b
ollama list
```

Retry the review after the download finishes. A model downloaded inside Docker
is not installed in Windows Ollama. If using the Compose stack, download with
`docker compose run --rm ollama-init` instead. If `OLLAMA_MODEL` is customized,
pull that model name and ensure it matches the configured server.

To use your Groq key instead, set `LLM_PROVIDER=groq`,
`GROQ_MODEL=llama-3.3-70b-versatile`, and `GROQ_API_KEY` in `backend/.env`,
then fully stop and restart the API/debug session. Existing environment variables
can override `.env`; check the VS Code/terminal provider setting if Ollama is
still selected. The API returns HTTP 503 with recovery instructions for a missing
Ollama model, and Streamlit displays those instructions.

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
