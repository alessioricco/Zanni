---
name: explore-app
description: How to explore the running app in a browser and turn each bug into a finding with a failing test. Load before exploring.
---

# Explore the app

1. Open the app with the `browser` tool and walk through each flow named in `spec/`.
2. For each unexpected behaviour, write `findings/<item>.md`: what you did, what you expected, what happened.
3. Add a failing test that reproduces it under `tests/`.
