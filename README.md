# Aster Infrastructure

A locally branded distribution for agent inference, feedback, harness evolution,
and model training.

## Start

Use the local `.env` file for your DeepSeek API key. On a fresh checkout,
create it with `(umask 077; cp -n .env.example .env)`. Edit
`ASTER_UPSTREAM_API_KEY` locally. Git ignores `.env`, and the checked-in
`.env.example` contains only placeholders and public settings.

From this directory, run `./aster demo` to use the included pi example.
It uses the provider URL and model from `.env` and writes
`tutorials/evolve-your-harness/work/replay.html` on completion.
The demo makes paid model calls. It needs Node.js, npm, and Git LFS.
`./aster demo native` selects the native agent instead.

Run `./aster serve` for the persistent harness service at
`http://127.0.0.1:8901`. Route agent tasks through it and send scored
feedback to trigger evolution. Environment variables set in the shell
take precedence over values in `.env`.

`aster serve -c recipes/basic/local-sglang.yaml` starts the bundled
inference config. Its health route is `http://127.0.0.1:8900/healthz`.

## License

Aster is open source under the Apache-2.0 license. See LICENSE.
