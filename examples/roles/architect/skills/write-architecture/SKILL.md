---
name: write-architecture
description: How to write the design a round builds on, in spec/architecture/. Load before writing the spec.
---

# Write the architecture

1. Read the round's backlog, `vision.md`, the starter project files, and what is already in `app/` and `spec/`.
2. Write `spec/architecture/overview.md`:
   - **Modules:** each one's path under `app/`, what it does, and which criteria (by id, such as `R1-2`) it serves.
     Give modules paths that don't overlap, so separate people can build them at the same time.
   - **Contracts:** each module's public functions or endpoints: names, inputs, outputs and errors, precisely enough
     that a test can be written from them before the code exists.
   - **Shared files:** any file more than one module needs, such as an entry point or a router. Name which module
     owns it; only its owner changes it.
   - **Commands:** the exact commands, in the project's stack, to install, run the tests, and start the app,
     including the port it listens on (from the `PORT` environment variable, when the stack allows).
3. Keep it to what this round needs. A later round can extend it.
