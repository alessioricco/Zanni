# Verifier seat

Zanni's built-in role `zanni:verifier` (D45). A verifier seat runs no model: it is Zanni's own code. When the director sends `zanni.verify`, it reads every file of the stage over MCP into a fresh folder, runs exactly the command it was sent, within its timeout, and answers `zanni.verdict` with the exit code and the end of the output.
