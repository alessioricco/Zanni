"""Every acceptance criterion in the round's backlog has a test that names its id (D55).

    python criteria.py <backlog folder> <tests folder>

The round is the highest n with a <backlog folder>/round-<n>.md. A criterion id is written like R1-3: an R, the
round, a dash, its number. A test names it anywhere in its file, as R1-3 or as r1_3 (a test function's name can't hold
a dash), in any language. Exits 0 when every id is named, 1 otherwise, saying which are missing.
"""

import re
import sys
from pathlib import Path

ID = re.compile(r"(?<![A-Za-z0-9])R(\d+)-(\d+)(?![0-9])")


def latest_backlog(folder: Path) -> Path | None:
    rounds = [(int(m[1]), p) for p in folder.glob("round-*.md") if (m := re.fullmatch(r"round-(\d+)\.md", p.name))]
    return max(rounds)[1] if rounds else None


def named(ident: tuple[str, str], text: str) -> bool:
    round_, number = ident
    return re.search(rf"(?<![A-Za-z0-9])[Rr]{round_}[-_]{number}(?![0-9])", text) is not None


def main(backlog: Path, tests: Path) -> int:
    path = latest_backlog(backlog)
    if path is None:
        print(f"no backlog file: {backlog}/round-<n>.md is missing")
        return 1
    ids = sorted(set(ID.findall(path.read_text())), key=lambda i: (int(i[0]), int(i[1])))
    if not ids:
        print(f"{path} names no criterion id; write each criterion with one, such as R1-1")
        return 1
    texts = []
    for p in sorted(tests.rglob("*")) if tests.is_dir() else []:
        if p.is_file():
            try:
                texts.append(p.read_text())
            except UnicodeDecodeError:
                continue
    missing = [f"R{r}-{n}" for r, n in ids if not any(named((r, n), t) for t in texts)]
    if missing:
        print(f"{len(missing)} of {len(ids)} criteria in {path} have no test naming them: {', '.join(missing)}")
        return 1
    print(f"every one of the {len(ids)} criteria in {path} has a test naming it")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: criteria.py <backlog folder> <tests folder>")
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
