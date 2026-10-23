import fnmatch, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "config" / "rule_map.json"
ID_RE = re.compile(r"\b(?:PR|RF|TX)-\d{3}\b")

def retrieve(changed_paths):
    config = json.loads(MAP.read_text(encoding="utf-8"))
    selected = set(config["global_rules"])
    components, tests = [], []
    for name, spec in config["components"].items():
        if any(fnmatch.fnmatch(path, pat) or fnmatch.fnmatch("/" + path, pat) for path in changed_paths for pat in spec["paths"]):
            components.append(name)
            selected.update(spec["rules"])
            tests.extend(spec.get("tests", []))
    # Fail closed: unmapped production code requires manual review, not an AI-only pass.
    unmapped = [p for p in changed_paths if p.endswith(".cs") and not any(
        fnmatch.fnmatch(p, pat) or fnmatch.fnmatch("/" + p, pat)
        for spec in config["components"].values() for pat in spec["paths"]
    )]
    sources = []
    for name in sorted(selected):
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise ValueError(f"Missing or unsafe rule file: {name}")
        content = path.read_text(encoding="utf-8")
        sources.append({"path": name, "content": content, "rule_ids": ID_RE.findall(content)})
    return {"sources": sources, "components": components, "tests": sorted(set(tests)), "unmapped": unmapped}
