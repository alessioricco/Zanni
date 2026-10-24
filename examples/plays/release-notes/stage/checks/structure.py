"""The `notes-structure` verifier: notes/release-notes.md has the style guide's sections and covers every change.

Run in a snapshot of the stage (D45): exits 0 when the notes pass, 1 with what is missing otherwise.
"""

import re
import sys
from pathlib import Path

notes = Path("notes/release-notes.md")
if not notes.is_file():
    sys.exit("notes/release-notes.md doesn't exist yet")
text = notes.read_text()
changes = re.findall(r"#\d+", Path("changelog.md").read_text())
problems = []
if not re.search(r"^# What's new in \S+", text, re.M):
    problems.append("the title `# What's new in <version>` is missing")
for heading in ("## New", "## Fixed"):
    if not re.search(rf"^{heading}\s*$", text, re.M):
        problems.append(f"the section `{heading}` is missing")
if re.search(r"^## New", text, re.M) and re.search(r"^## Fixed", text, re.M):
    if text.index("## New") > text.index("## Fixed"):
        problems.append("`## New` must come before `## Fixed`")
missing = [c for c in changes if f"({c})" not in text]
if missing:
    problems.append(f"these changes aren't in the notes: {', '.join(missing)}")
if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"the notes have both sections and all {len(changes)} changes")
