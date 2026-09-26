# Contributing

Open an issue with the failing case ID, agent version, operating system, redacted
`result.json`, and the exact command. Remove personal data and tokens first.

For code changes, keep each task fictional and give every score a checkable
source. Run `./run-fixture.sh` and `python3 -m unittest discover -s tests` before
opening a pull request. A new adapter must produce the same evidence contract;
it may not replace a failed live call with fixture output.
