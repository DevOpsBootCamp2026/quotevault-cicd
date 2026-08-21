# REPORT — QuoteVault CI/CD

Repo: https://github.com/DevOpsBootCamp2026/quotevault-cicd
Image: `ghcr.io/devopsbootcamp2026/quotevault-cicd`

---

## 1. Green CI run — all four jobs

Run [32451308181](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451308181):

```
✓ fix/latest-tag-flavor CI DevOpsBootCamp2026/quotevault-cicd#4 · 32451308181
Triggered via pull_request

JOBS
✓ lint         in  6s (ID 96680216416)
✓ api-tests    in  7s (ID 96680236977)
✓ unit-tests   in  9s (ID 96680236983)
✓ docker-build in 17s (ID 96680264683)
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

Push to `main` — CD run [32451460592](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451460592):

```
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:main
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:sha-1ab9095

publish → success
release → skipped        (not a version tag)
```

`sha-1ab9095` is the actual merge commit, because CD checks out
`workflow_run.head_sha` rather than whatever the default branch happens to point
at.

### `docker pull` / `run` / `curl`

**Skipped.** The local Docker daemon was not running
(`dial unix /Users/hamzeh/.docker/run/docker.sock: no such file or directory`),
so this was not captured. To fill it in later:

```bash
docker pull ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
docker run -d -p 8000:8000 --name qv ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
curl localhost:8000/health     # {"status":"ok"}
docker rm -f qv
```

The equivalent check does run in CI on every build: `docker-build` builds this
same Dockerfile and smoke-tests `/health` against the running container, and it
passed on the commit that produced this image (see section 1).

---

## 3. Release proof

Tag pushed: **v1.1.1** (on commit `1ab9095`).

CI on the tag — run [32451431945](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451431945) → `success`.

CD run [32451479727](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451479727):

```
publish → success
release → success

--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:1.1.1
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:v1.1.1
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:sha-1ab9095
```

The semver tag `1.1.1` is published and `latest` is **not** applied to a tag
build. Release created:

```
tag=v1.1.1 name=v1.1.1 draft=false
https://github.com/DevOpsBootCamp2026/quotevault-cicd/releases/tag/v1.1.1
```

An earlier tag, **v1.1.0**, is also released:
https://github.com/DevOpsBootCamp2026/quotevault-cicd/releases/tag/v1.1.0

---

## 4. Failures the pipeline caught

### 4.1 The deliberate one — a broken unit test

PR [#5](https://github.com/DevOpsBootCamp2026/quotevault-cicd/pull/5) changed
`test_keeps_provided_author` to assert `Obi-Wan` instead of `Yoda`.

Run [32451881460](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451881460):

```
lint         → success
api-tests    → success
unit-tests   → failure
docker-build → skipped

>       assert value["author"] == "Obi-Wan"
E       AssertionError: assert 'Yoda' == 'Obi-Wan'
tests/unit/test_validation.py:14: AssertionError
FAILED tests/unit/test_validation.py::test_keeps_provided_author
1 failed, 4 passed in 0.03s
```

`docker-build` never ran — `needs: [unit-tests, api-tests]` blocked it, so no
broken image was ever built. CD run
[32451904890](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451904890)
→ **skipped**. Nothing was published. The PR was closed, not merged.

The next five were **not** deliberate. They were already live in the pipeline and
were found by reading run logs rather than trusting the green check marks.

### 4.2 A green CI that verified nothing

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

### 4.3 `docker-build` could no longer be scheduled

The job was pinned to `runs-on: self-hosted`. `GET /repos/.../actions/runners`
returns an empty list — no self-hosted runner is registered on this repo any
more, so the job would queue indefinitely. Moved to `ubuntu-latest`.

Its cleanup step also ran `docker rm -f quotvault || ture` — a typo that turns
the fallback into a command-not-found, failing the step whenever `docker rm`
failed.

### 4.4 CD published on a pull request

Opening PR [#3](https://github.com/DevOpsBootCamp2026/quotevault-cicd/pull/3)
triggered CD run
[32450626107](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32450626107),
which pushed to GHCR:

```
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:latest
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:main
--tag ghcr.io/devopsbootcamp2026/quotevault-cicd:sha-0c09525
```

A pull request overwrote `latest`. The `workflow_run` trigger fires on *every*
completed CI run and the only guard was `conclusion == 'success'`. Fixed by also
requiring `workflow_run.event == 'push'` and a head branch of `main` or `v*`.

Verified after the fix: PR [#4](https://github.com/DevOpsBootCamp2026/quotevault-cicd/pull/4)
produced a green CI and CD run
[32451349990](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451349990)
→ **skipped**, both jobs skipped, nothing published.

### 4.5 Version tags were never published

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
checking out `head_sha`, so the published image is the exact commit CI tested.

### 4.6 `metadata-action` re-added `latest` to tag builds

After 4.5 was fixed, the `v1.1.0` build
([32451104860](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451104860))
*still* published `latest` alongside `1.1.0`, even though the explicit condition
had evaluated correctly:

```
Processing tags input
type=semver,pattern={{version}},value=v1.1.0,enable=true,priority=900
type=raw,value=latest,enable=false,priority=200      <-- correctly disabled
Processing flavor input
latest=auto                                          <-- re-added it anyway
```

`metadata-action` defaults to `flavor: latest=auto`, which adds `latest` whenever
a `type=semver` or `type=match` tag matches — silently overriding the explicit
`enable=false`. Fixed with `flavor: latest=false`, making the default-branch
condition the only thing that applies `latest`. Confirmed on the `v1.1.1` build
in section 3.

---

## 5. CI vs CD

CI runs on every push and pull request targeting `main` and only ever *asks a
question* — does the code lint, do the unit and API tests pass, does the image
build and answer `/health` — writing nothing outside the runner, so a red CI
costs nothing but a failed check.

CD runs only after a CI run has concluded successfully on `main` or a `vX.Y.Z`
tag and *changes the world* — it authenticates to GHCR, pushes tagged images and
cuts a GitHub Release, which is why it carries `packages: write` and is gated on
CI's conclusion rather than duplicating CI's checks.

---

## Appendix — definition of done

| Check | Result |
|---|---|
| PR → CI runs, all four jobs pass, nothing published | ✅ CI [32451308181](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451308181) green, CD [32451349990](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451349990) skipped |
| Merge to `main` → CI passes and CD publishes | ✅ CD [32451460592](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451460592) → `main`, `latest`, `sha-1ab9095` |
| `docker pull` + `run` + `curl /health` | ⏭️ skipped — local Docker daemon not running |
| `vX.Y.Z` tag → semver image tag + Release | ✅ CD [32451479727](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451479727) → `1.1.1`, Release `v1.1.1` |
| Breaking a test makes CI red, nothing published | ✅ CI [32451881460](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451881460) red, CD [32451904890](https://github.com/DevOpsBootCamp2026/quotevault-cicd/actions/runs/32451904890) skipped |
