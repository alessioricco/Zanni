---
name: explore-the-app
description: How to explore the running app for bugs, and turn each into a finding with a failing test. Load before exploring.
---

# Explore the app

1. Start the app in your workspace with the spec's start command, and use it as a person would: with HTTP requests to
   its pages and endpoints, with wrong and edge-case input as well as normal input.
2. For each bug, write `findings/<short-name>.md`: what you did, what you expected, what happened.
3. For each finding, write a test that fails because of the bug, under `tests/findings/`, and name the finding in it.
   The next round's product owner decides when it is fixed; these tests don't count against this round.
4. Stop the app when you are done. Report how many findings you wrote, or that you found none.
