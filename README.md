# PaymentRuleGuard-AI

Reviews C# payment changes against mapped Markdown rules using LangGraph and Ollama
(or Groq). Reviews are advisory; the UI does not run .NET tests or approve merges.

## Debug from the UI: local Python + Docker Ollama

Requires Docker Desktop, Python 3.11+, VS Code, and Microsoft's **Python** and
**Python Debugger** extensions. Open this repository root in VS Code.

### 1. Prepare Python (PowerShell, repository root)

In VS Code, use **File > Open Folder** to open `PaymentRuleGuard-AI`, then
**Terminal > New Terminal** and select **PowerShell**. Run the commands below
from the repository root: the folder containing `README.md`, `compose.yaml`,
and `backend`. If your terminal is in another folder, first use
`cd C:\Users\RajeshDas\PaymentRuleGuard-AI` (replace this with your checkout path).

Check that Python is installed:

```powershell
python --version
```

This should show Python **3.11 or newer**. Then copy and run this entire block:

```powershell
# Create a project-specific Python environment if it does not already exist.
if (-not (Test-Path backend/.venv/Scripts/python.exe)) {
    python -m venv backend/.venv
}

# Install the API, UI, model integration, and test dependencies into that environment.
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

# Create local configuration from the example, preserving any existing .env file.
if (-not (Test-Path backend/.env)) {
    Copy-Item backend/.env.example backend/.env
}
```

The `.venv` folder keeps this project's packages separate from other Python
projects. These commands call its Python executable directly, so you do not
need to activate the environment. Wait for installation to finish without errors.
You should now have `backend/.venv/Scripts/python.exe` and `backend/.env`;
you will update the Ollama connection settings in step 3.

Tell VS Code to use the same Python environment for debugging:

1. Press **Ctrl+Shift+P** to open the Command Palette.
2. Search for **Python: Select Interpreter** and select it.
3. Choose the interpreter at `backend\.venv\Scripts\python.exe`.
   If it is missing from the list, choose **Enter interpreter path > Find**,
   then browse to that file inside your checkout.

If the interpreter command is missing, install Microsoft's **Python** extension
and reopen the Command Palette.

### 2. Start only Ollama in Docker

Stop any old local API/UI processes or debug sessions first. Then run:

```powershell
docker compose stop backend streamlit
docker compose -f compose.yaml -f compose.debug.yaml up -d ollama ollama-init
docker compose -f compose.yaml -f compose.debug.yaml logs -f ollama-init
```

Wait for the model pull to finish (exit code 0), then press **Ctrl+C** to leave
logs. The first download can take several minutes. Check the model:

```powershell
Invoke-RestMethod http://localhost:11435/api/tags
```

The list should contain `llama3.2:3b`. The debug override publishes Docker Ollama
on host port **11435**; no edits to `compose.yaml` are needed.

### 3. Configure local Python

Set these values in `backend/.env`, then restart any running debug sessions:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11435
API_URL=http://localhost:8000
```

Keep `OLLAMA_MODEL` equal to the Compose model (default `llama3.2:3b`). To change
it, also set `OLLAMA_MODEL` in a repository-root `.env` and rerun step 2.

### 4. Set breakpoints and click Review

1. Set breakpoints at `return review_diff(...)` in `backend/app.py`, inside
   `collect` / `analyze` in `backend/review.py`, and at `r = requests.post(...)`
   in `backend/streamlit_app.py`.
2. Open **Run and Debug**, choose **Debug UI + API (Docker Ollama)**, and press
   **F5**. Wait for API startup. Both Python processes run locally under VS Code.
3. Open http://localhost:8501 and select **PR Review**. Use path
   `src/Payments/PaymentService.cs` and this diff:

   ```diff
   - if (amount <= 0) throw new ArgumentOutOfRangeException(nameof(amount));
   + if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
   ```

4. Click **Review change**. Continue the UI breakpoint with **F5**, then select
   the API debug session when it pauses. Use **F10** to step over, **F11** to step
   into, and **F5** to continue. Expand **Mapped rules and tests** in the result.

Expected: a finding about zero payments under **PR-001**; wording varies.
Flow: UI -> `POST /review` -> rule retrieval -> model -> UI result.
For a model-free check, use `src/Unknown/Unknown.cs`: it returns manual review
and skips `analyze`. API-only debugging is also available at http://localhost:8000/docs.

## Quick fixes

| Problem | Fix |
| --- | --- |
| Breakpoint never hits | Stop old Docker API/UI and terminal Python processes. Use the F5 sessions on ports 8000/8501. |
| Ollama connection refused | Repeat step 2; verify `/api/tags` and `OLLAMA_BASE_URL=http://localhost:11435`. |
| Model missing | Run `docker compose -f compose.yaml -f compose.debug.yaml run --rm ollama-init`. |
| Missing Python module | Install requirements with the virtual-environment Python from step 1. |
| UI request times out | Continue all breakpoints; the UI waits 10 minutes. CPU inference can be slow. Use `/docs` when stepping slowly. |

Restart debug sessions after code or environment changes; API debugging uses no
reload process. Keep both `-f` arguments when updating Docker during debugging.
Stop Python with **Shift+F5** (the compound stops both), then stop Docker with:

```powershell
docker compose -f compose.yaml -f compose.debug.yaml down
```

Downloaded models are retained.

## Run everything in Docker (without local breakpoints)

Stop local debug sessions, then run `docker compose up --build -d`.
Open http://localhost:8501. The backend uses `http://ollama:11434` inside Docker;
this mode does not publish Ollama to the host. Stop with `docker compose down`.

## Tests and further reading

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests -q
dotnet test sample-dotnet/PaymentRuleGuard.sln
```

Python tests mock the model; .NET tests require SDK 8. Transaction integration
tests remain skipped. See [the detailed reference](docs/REFERENCE.md) for review
scenarios, Groq/CI setup, rule mapping, .NET debugging, and production limitations.
