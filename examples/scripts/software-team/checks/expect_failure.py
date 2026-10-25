"""The project's tests run, and fail: new tests fail before the code they test exists (D55).

    python expect_failure.py [--code N]... -- <the project's test command>...

Exits 0 when the command exits with one of the codes given (default 1, what most test runners use for "some tests
failed"), and 1 otherwise: when the tests pass, or the runner itself broke (a usage error, a crash, no tests found).
Give a runner's other codes for "the code under test doesn't exist yet" too: pytest exits with 2 when a test can't
import its module, so a Python project passes --code 1 --code 2.
"""

import subprocess
import sys


def main(args: list[str]) -> int:
    codes = []
    while args[:1] == ["--code"]:
        codes, args = codes + [int(args[1])], args[2:]
    codes = codes or [1]
    if args[:1] != ["--"] or len(args) < 2:
        print("usage: expect_failure.py [--code N]... -- <command>...")
        return 2
    result = subprocess.run(args[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(result.stdout[-3000:])
    expected = " or ".join(map(str, codes))
    if result.returncode in codes:
        print(f"the tests ran and failed (exit code {result.returncode}), as new tests should before their code exists")
        return 0
    print(f"expected the tests to fail with exit code {expected}; the command exited with {result.returncode}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
