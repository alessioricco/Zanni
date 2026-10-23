"""Golden rule 4: only src/zanni/engine/ may import the engine's packages."""

import ast
from pathlib import Path

SRC = Path(__file__).parents[1] / "src" / "zanni"
ENGINE_PACKAGES = {"pydantic_ai", "mcp", "a2a", "fastmcp", "genai_prices", "anthropic", "openai"}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_only_the_engine_imports_engine_packages():
    offenders = {}
    for path in SRC.rglob("*.py"):
        if (SRC / "engine") in path.parents:
            continue
        found = imports(path) & ENGINE_PACKAGES
        if found:
            offenders[str(path.relative_to(SRC))] = sorted(found)
    assert not offenders, f"only src/zanni/engine/ may import these: {offenders}"
