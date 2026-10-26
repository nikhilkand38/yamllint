# yamllint-report

Runs [yamllint](https://yamllint.readthedocs.io/) on YAML files and writes a SonarQube-style HTML report:
quality gate, summary cards, files scanned (with line counts and pass/fail status), issues by rule and file,
and the full issue list with the offending source line.

## Setup

Requires Python 3.8+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.
On Git Bash use `source .venv/Scripts/activate`.

## Usage

```powershell
python yamllint_report.py <path> [<path> ...] [-o report.html] [-c config.yml] [-x DIR]
```

| option | meaning | default |
|---|---|---|
| `path` | files or folders; folders are searched recursively for `*.yml`, `*.yaml`, `.yamllint` | required |
| `-o, --output` | HTML report path | `yamllint-report.html` |
| `-c, --config` | yamllint config file | `.yamllint.yml` next to the script |
| `-x, --exclude` | folder name to skip (repeatable) | `.venv`, `.git` |

Examples:

```powershell
# One file
python yamllint_report.py C:\work\repo\ci\build.yml

# A whole folder tree, custom report name
python yamllint_report.py C:\Users\kandun2\yaml-check -o yaml-check-report.html

# Open the report
Invoke-Item .\yaml-check-report.html
```

The script prints `N file(s), N issue(s) -> <report>` and exits with:

* `0` - no error-level issues (warnings are allowed)
* `1` - at least one error-level issue (quality gate Failed)

so it can be used as a CI gate.

## Configuration

Rules live in `.yamllint.yml` (default: yamllint's `default` ruleset with a 550-character line limit).
Edit it, or pass your own with `-c`. Rule reference: <https://yamllint.readthedocs.io/en/stable/rules.html>.

Report severities: yamllint `error` = Major, `warning` = Minor.

## Notes

* Line-ending errors (`new-lines`: expected `\n`) mean the file has CRLF endings; convert the file to LF.
* Files are passed to yamllint explicitly, so the config is not picked up from the scanned folder - only `-c` or the bundled `.yamllint.yml` applies.
