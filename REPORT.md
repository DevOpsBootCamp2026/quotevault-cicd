# REPORT — QuoteVault CI/CD

Repo: https://github.com/DevOpsBootCamp2026/quotevault-cicd
Image: `ghcr.io/devopsbootcamp2026/quotevault-cicd`

---

## 1. Green CI run — all four jobs

Run [32450582632](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32450582632), triggered by pull request [#3](https://github.com/DevOpsBootCamp2026/quotevault-cicd/pull/3):

```
✓ fix/cicd-pipeline CI DevOpsBootCamp2026/quotevault-cicd#3 · 32450582632
Triggered via pull_request

JOBS
✓ lint         in 11s (ID 96678227516)
✓ api-tests    in  7s (ID 96678270521)
✓ unit-tests   in  9s (ID 96678270555)
✓ docker-build in 12s (ID 96678303279)
```

Job graph enforced with `needs:`:

```
lint ─┬─ unit-tests ─┐
      └─ api-tests ──┴─ docker-build
```

Step output:

```
lint         Successfully set up CPython (3.12.14)
lint         Run flake8 quotevault            → clean
unit-tests   5 passed in 0.02s
api-tests    5 passed in 0.16s
```

The smoke test proves the retry loop does real work — gunicorn is not up on the
first attempt:

```
docker-build  Smoke test /health  curl: (56) Recv failure: Connection reset by peer
docker-build  Smoke test /health  health check attempt 1 failed, retrying in 2s
docker-build  Smoke test /health  health check passed on attempt 2
docker-build  Cleanup container   quotevault-ci
```

---

## 2. Published image

_Pending the merge of #3 to `main`._

```
docker pull ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
docker run -p 8000:8000 ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
curl localhost:8000/health
```

---

## 3. Release proof

_Pending the tag push after #3 is merged._

---

## 4. Failures the pipeline caught

Three of these were **not** caused on purpose — they were already live in the
pipeline and were found by reading the run logs rather than trusting the green
check marks.

### 4.1 A green CI that verified nothing

In run [30379283925](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/30379283925)
the `docker-build` job reported success. Its log:

```
Health check failed, retrying...   (×10)
Post job cleanup.
```

The smoke test failed **all ten attempts** and the job still went green. Two
independent causes:

1. It grepped for `OK`, but `/health` returns `{"status":"ok"}` — lowercase.
2. The retry loop had `exit 0` on success but **no `exit 1` after the loop**, so
   exhausting every retry left the step's exit status at 0.

The pipeline was structurally incapable of failing on a broken container. Fixed
by matching `"ok"` and adding `docker logs` + `exit 1` after the loop.

### 4.2 `docker-build` could no longer be scheduled

The job was pinned to `runs-on: self-hosted`. `GET /repos/.../actions/runners`
returns an empty list — no self-hosted runner is registered on this repo any
more, so the job would queue indefinitely. Moved to `ubuntu-latest`.

### 4.3 CD published on a pull request

Opening #3 triggered CD run
[32450626107](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32450626107),
which pushed to GHCR:

```
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:main
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:sha-0c09525
```

A pull request overwrote `latest`. The `workflow_run` trigger fires on *every*
completed CI run, and the only guard was `conclusion == 'success'`. Fixed by
also requiring `workflow_run.event == 'push'` and a head branch of `main` or
`v*`.

### 4.4 Version tags were never published

CD run [30379413266](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/30379413266)
followed the CI run for tag **v1.0.3** and published:

```
DOCKER_METADATA_OUTPUT_TAGS: ghcr.io/devopsbootcamp2026/quotevault-cicd:main
"tags": ["...:main", "...:latest", "...:sha-0c09525"]
```

No `1.0.3` tag. In a `workflow_run` event `GITHUB_REF` resolves to the **default
branch**, not the ref that triggered the upstream run, so `type=ref,event=branch`
yielded `main` and `type=semver` had no version to match. It also built main's
tip (`0c09525`) rather than the tagged commit.

Additionally, `type=raw, value=latest, enabled={is_default_branch}` is not valid
`metadata-action` syntax — the input is `enable`, and templates need `{{ }}`. The
malformed attribute was ignored, so `latest` was applied to **every** build,
including tag builds.

Fixed by deriving every tag from `workflow_run.head_branch` / `head_sha` and
checking out `head_sha` so the published image is the exact commit CI tested.

---

## 5. CI vs CD

CI runs on every push and pull request targeting `main` and only ever *asks a
question* — does the code lint, do the unit and API tests pass, does the image
build and answer `/health` — writing nothing outside the runner, so a red CI
costs nothing but a failed check.

CD runs only after a CI run has concluded successfully on `main` or a `vX.Y.Z`
tag and *changes the world* — it authenticates to GHCR, pushes tagged images, and
cuts a GitHub Release, which is why it carries `packages: write` and is gated on
CI's conclusion rather than duplicating CI's checks.
