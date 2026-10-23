import json, os, urllib.request
from review import review_diff

repo = os.environ["GITHUB_REPOSITORY"]
number = os.environ["PR_NUMBER"]
token = os.environ["GITHUB_TOKEN"]
api = f"https://api.github.com/repos/{repo}"
def request(url, method="GET", payload=None, accept="application/vnd.github+json"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "PaymentRuleGuard-AI",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode()
files = []
page = 1
while True:
    batch = json.loads(request(f"{api}/pulls/{number}/files?per_page=100&page={page}"))
    files.extend(batch)
    if len(batch) < 100: break
    page += 1
paths = [f["filename"] for f in files]
# GitHub file patches may be truncated or omitted. Fail closed for incomplete diffs.
incomplete = [f["filename"] for f in files if "patch" not in f and f["filename"].endswith(".cs")]
if incomplete:
    review = "MANUAL REVIEW REQUIRED: missing/truncated GitHub file patches: " + ", ".join(incomplete)
else:
    diff = "\n".join(f"FILE: {f['filename']}\n{f.get('patch','')}" for f in files)
    if len(diff) > 25000:
        review = "MANUAL REVIEW REQUIRED: PR diff exceeds review context limit."
    else:
        review = review_diff(diff, paths)["review"]
body = "### 🛡️ PaymentRuleGuard AI (advisory)\n\n" + review[:50000] + "\n\n> Human review and CI tests remain mandatory."
request(f"{api}/issues/{number}/comments", method="POST", payload={"body": body})
print("Posted advisory PR comment")
