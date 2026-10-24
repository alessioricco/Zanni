---
name: make-it-pass
description: How to make one module's failing tests pass. Load before writing any code.
---

# Make it pass

1. Read every test that imports your module, and note each input and expected output.
2. Read the spec for the module: the function's name, its arguments and what it returns.
3. Write the whole module in one `stage_write` call, keeping the function's signature from the spec.
4. Use only Python's standard library. Don't add files other than the module your cue names.
