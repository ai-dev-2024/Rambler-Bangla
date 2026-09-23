# Contributing

Thanks for helping. A few ground rules keep this project safe to use.

## Before you open a pull request

1. Fetch the toolchain and run the static suite:

   ```bash
   bash scripts/bootstrap_tools.sh
   pip install androguard==4.1.4
   source tools/tool-env.sh
   bash tests/run_tests.sh      # expect "17 passed, 0 failed"
   ```

   CI runs the same steps on every push and pull request.
2. Keep changes small and targeted. The patch is fail-closed on purpose:
   a fingerprint mismatch must abort, never guess.
3. Conversion changes need fixtures: add input/expected pairs so the
   behaviour is locked by a test.

## What not to commit

- APKs, dex files, keystores or signing keys (`.gitignore` blocks the common
  ones).
- Google or third-party app content. The test fixture is synthetic for
  this reason.
- API keys, tokens, or personal data.

## Licence

By contributing you agree your work is released under GPL-3.0, the
project licence (see `LICENSE`).
