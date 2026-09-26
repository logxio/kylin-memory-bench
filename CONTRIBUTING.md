# Contributing

Start with the [reproduction guide](docs/live-openkylin.md) for live agents, or
run `./run-fixture.sh` to check the pipeline. Open a [bug report](https://github.com/logxio/kylin-memory-bench/issues/new/choose) with the case ID, versions, exact command, error, and redacted case evidence. A [case proposal](https://github.com/logxio/kylin-memory-bench/issues/new/choose) needs fictional turns, expected checks, and evidence the runner can observe. Do not post credentials, personal data, or an unredacted `result.json`.

Keep new tasks fictional and give every score a checkable source. A live adapter
must preserve raw replies, files, memory observations, errors, and their source
labels; a failed live call cannot turn into fixture evidence. See the
[scoring method](docs/method.md) before changing checks.

Run `python3 -m unittest discover -s tests`, `./run-fixture.sh`, and
`./packaging/build-deb.sh` before opening a pull request. Include the affected
case ID, the behavior changed, relevant redacted evidence, and command results
in the [pull request](https://github.com/logxio/kylin-memory-bench/compare).
For adapter changes, include a real-agent run with OS and agent versions when
the hardware and credentials are available; describe the tested scope exactly.
