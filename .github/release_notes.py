"""Release notes from the commit messages since the previous release: each commit's subject as a
heading, its message under it. Leaves out the version bumps ("Vault 1.5.5") and Co-Authored-By lines.

    python .github/release_notes.py <previous tag> <this tag> [<commit>]   # prints Markdown
"""
import os
import re
import subprocess
import sys

previous, tag = sys.argv[1], sys.argv[2]
commit = sys.argv[3] if len(sys.argv) > 3 else "HEAD"
log = subprocess.run(["git", "log", "--reverse", "--format=%s%x1f%b%x1e", f"{previous}..{commit}"],
                     capture_output=True, text=True, check=True).stdout
notes = []
for record in log.split("\x1e"):
    if not record.strip():
        continue
    subject, body = record.strip("\n").split("\x1f", 1)
    if re.fullmatch(r"Vault \d+(\.\d+)*", subject.strip()):
        continue
    body = "\n".join(line for line in body.splitlines() if not line.startswith("Co-Authored-By:")).strip()
    notes.append(f"### {subject.strip()}\n\n{body}\n" if body else f"### {subject.strip()}\n")
repo = os.environ.get("GITHUB_REPOSITORY", "wards999/Vault")
notes.append(f"**All changes**: https://github.com/{repo}/compare/{previous}...{tag}")
print("\n".join(notes))
