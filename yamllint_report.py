"""Run yamllint on files/folders and write a SonarQube-style HTML report.

Exit code: 1 if any error-level finding exists, else 0.
"""
import argparse
import fnmatch
import html
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

LINE_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): \[(?P<level>error|warning)\] (?P<msg>.*?)(?: \((?P<rule>[\w-]+)\))?$")
SEVERITY = {"error": "Major", "warning": "Minor"}
YAML_PATTERNS = ("*.yaml", "*.yml", ".yamllint")
DEFAULT_EXCLUDES = (".venv", ".git")
DEFAULT_CONFIG = Path(__file__).with_name(".yamllint.yml")
CHUNK = 100  # files per yamllint call, keeps the Windows command line short


def norm(p):
    return os.path.normcase(os.path.abspath(p))


def scanned_files(paths, excluded):
    found = {}
    for p in paths:
        path = Path(p)
        if path.is_file():
            found[norm(path)] = path
            continue
        for root, dirs, names in os.walk(path):
            dirs[:] = [d for d in dirs if d not in excluded]
            for name in names:
                if any(fnmatch.fnmatch(name, g) for g in YAML_PATTERNS):
                    f = Path(root) / name
                    found[norm(f)] = f
    return [found[k] for k in sorted(found)]


def run_yamllint(files, config):
    issues = []
    for start in range(0, len(files), CHUNK):
        cmd = [sys.executable, "-m", "yamllint", "-f", "parsable"]
        if config:
            cmd += ["-c", str(config)]
        proc = subprocess.run(
            cmd + [str(f) for f in files[start:start + CHUNK]],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode not in (0, 1):
            sys.exit(f"yamllint failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
        for raw in proc.stdout.splitlines():
            m = LINE_RE.match(raw.strip())
            if m:
                d = m.groupdict()
                d["rule"] = d["rule"] or "syntax"
                issues.append(d)
    return issues


def source_line(file, line):
    try:
        return Path(file).read_text(encoding="utf-8", errors="replace").splitlines()[int(line) - 1]
    except (OSError, IndexError):
        return ""


def file_stats(files, issues):
    by_file = {}
    for i in issues:
        by_file.setdefault(norm(i["file"]), []).append(i)
    stats = []
    for f in files:
        found = by_file.get(norm(f), [])
        n_err = sum(i["level"] == "error" for i in found)
        status = "Failed" if n_err else ("Warnings" if found else "Passed")
        lines = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
        stats.append({"file": str(f), "lines": lines, "status": status, "issues": len(found)})
    return stats


def render(issues, paths, stats):
    ncloc = sum(s["lines"] for s in stats)
    errors = sum(i["level"] == "error" for i in issues)
    warnings = len(issues) - errors
    passed = errors == 0
    by_rule = Counter(i["rule"] for i in issues).most_common()
    by_file = Counter(i["file"] for i in issues).most_common()
    e = html.escape

    rows = "".join(
        f"<tr><td><span class='sev {i['level']}'>{SEVERITY[i['level']]}</span></td>"
        f"<td>{e(i['file'])}</td><td>{i['line']}:{i['col']}</td><td>{e(i['rule'])}</td>"
        f"<td>{e(i['msg'])}<pre>{e(source_line(i['file'], i['line']).strip()[:200])}</pre></td></tr>"
        for i in sorted(issues, key=lambda x: (x["file"], int(x["line"])))
    )
    rule_rows = "".join(f"<tr><td>{e(r)}</td><td>{n}</td></tr>" for r, n in by_rule)
    file_rows = "".join(f"<tr><td>{e(f)}</td><td>{n}</td></tr>" for f, n in by_file)
    density = f"{len(issues) / ncloc * 1000:.1f}" if ncloc else "0.0"
    scanned_rows = "".join(
        f"<tr><td>{e(s['file'])}</td><td>{s['lines']}</td>"
        f"<td><span class='sev {s['status'].lower()}'>{s['status']}</span></td><td>{s['issues']}</td></tr>"
        for s in stats
    )

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>yamllint report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f3f3f3;color:#236a97}}
header{{background:#236a97;color:#fff;padding:16px 32px}}
main{{padding:24px 32px}}
.cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}
.card{{background:#fff;border:1px solid #e6e6e6;padding:16px 24px;min-width:140px}}
.card b{{display:block;font-size:28px;color:#262626}}
.gate{{font-weight:bold;padding:4px 12px;color:#fff;background:{'#00aa00' if passed else '#d4333f'}}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-bottom:24px}}
th,td{{border:1px solid #e6e6e6;padding:8px 12px;text-align:left;vertical-align:top;color:#262626}}
th{{background:#f9f9f9}}
pre{{margin:4px 0 0;padding:4px 8px;background:#f3f3f3;font-size:12px;overflow:auto}}
.sev{{padding:2px 8px;color:#fff;font-size:12px}}
.sev.error,.sev.failed{{background:#d4333f}} .sev.warning,.sev.warnings{{background:#ed7d20}} .sev.passed{{background:#00aa00}}
h2{{color:#262626}}
</style></head><body>
<header><h1>YAML Lint Report</h1>
<div>{e(', '.join(paths))} &mdash; {datetime.now():%Y-%m-%d %H:%M}</div></header>
<main>
<p>Quality Gate: <span class="gate">{'Passed' if passed else 'Failed'}</span> (fails on any error-level issue)</p>
<div class="cards">
<div class="card"><b>{len(issues)}</b>Issues</div>
<div class="card"><b>{errors}</b>Errors (Major)</div>
<div class="card"><b>{warnings}</b>Warnings (Minor)</div>
<div class="card"><b>{len(stats)}</b>Files scanned</div>
<div class="card"><b>{ncloc}</b>Lines scanned</div>
<div class="card"><b>{density}</b>Issues / 1k lines</div>
</div>
<h2>Files scanned</h2><table><tr><th>File</th><th>Lines</th><th>Status</th><th>Issues</th></tr>{scanned_rows or '<tr><td colspan=4>No files found</td></tr>'}</table>
<h2>Issues by rule</h2><table><tr><th>Rule</th><th>Count</th></tr>{rule_rows or '<tr><td colspan=2>None</td></tr>'}</table>
<h2>Issues by file</h2><table><tr><th>File</th><th>Count</th></tr>{file_rows or '<tr><td colspan=2>None</td></tr>'}</table>
<h2>Issues</h2><table><tr><th>Severity</th><th>File</th><th>Line:Col</th><th>Rule</th><th>Message</th></tr>{rows or '<tr><td colspan=5>No issues found</td></tr>'}</table>
</main></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", help="files or folders to scan (folders are searched recursively)")
    ap.add_argument("-o", "--output", default="yamllint-report.html", help="HTML report path (default: %(default)s)")
    ap.add_argument("-c", "--config", default=str(DEFAULT_CONFIG) if DEFAULT_CONFIG.is_file() else None,
                    help="yamllint config file (default: .yamllint.yml next to this script)")
    ap.add_argument("-x", "--exclude", action="append", metavar="DIR",
                    help=f"folder name to skip, repeatable (default: {', '.join(DEFAULT_EXCLUDES)})")
    args = ap.parse_args()

    files = scanned_files(args.paths, set(args.exclude or DEFAULT_EXCLUDES))
    issues = run_yamllint(files, args.config) if files else []
    stats = file_stats(files, issues)
    Path(args.output).write_text(render(issues, args.paths, stats), encoding="utf-8")
    print(f"{len(files)} file(s), {len(issues)} issue(s) -> {args.output}")
    return 1 if any(i["level"] == "error" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
