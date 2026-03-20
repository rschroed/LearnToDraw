# Workflow

This repo should optimize for a stable `main`, short-lived branches, and small reviewable slices.

## Core Rules

- `main` stays releasable and should only move through reviewed pull requests.
- Branch from the latest `main` for each slice of work.
- Use a short-lived `codex/<topic>` branch name for implementation work.
- Keep each branch scoped to one concern. Split follow-up work into a new branch instead of extending an old one indefinitely.
- Prefer squash merges so each merged branch lands as one intentional change on `main`.
- Delete the branch immediately after merge.

## Branch Lifecycle

1. Sync `main`.
2. Create a branch from `main`.
3. Make a small, coherent slice of changes.
4. Run the relevant checks locally before opening or updating the PR.
5. Open a pull request early once the branch has a clear direction.
6. Merge only after the checklist is complete.
7. Delete the branch locally and remotely after merge.

Example:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b codex/<short-topic>
```

## Commit Expectations

- Prefer small commits at slice boundaries.
- Write commit messages that describe the behavior change, not the mechanic.
- Avoid mixing refactors, behavior changes, and incidental cleanup in one commit unless they are inseparable.
- Do not commit generated build output, runtime artifacts, or temporary recovery files.

## Pull Request Expectations

- Explain the user-facing or architectural impact briefly.
- Call out hardware-related assumptions or version-sensitive behavior explicitly.
- State which checks were run and which were not.
- Keep the PR narrow enough that it can be reviewed in one pass.

## Required Checks

For substantial changes, run:

```bash
make api-test
make web-test
make web-build
```

When relevant, also run:

```bash
make api-lint
make web-lint
```

If a check cannot run, note the reason in the PR.

## Cleanup Routine

Run this regularly to keep local state aligned with the remote:

```bash
git fetch --prune
git branch --merged main
```

Delete merged branches you no longer need:

```bash
git branch -d <branch>
```

Avoid keeping `-backup`, `-pre-rebase`, or similar recovery branches around as part of normal workflow. If a safety point is needed, use a temporary local branch or tag and remove it once the risk window has passed.

## Rebase And Recovery

- Rebase a short-lived branch onto `main` when it falls behind and has not been merged yet.
- Do not create permanent `pre-rebase` or `backup` branches as routine practice.
- If a rebase becomes risky, pause and create one temporary recovery ref intentionally, then delete it after the branch is stable again.

## When To Split Work

Start a new branch when:

- the current PR is already reviewable
- the next change is logically independent
- the next change changes both frontend and backend in a way that deserves its own review
- the current branch has been open long enough that rebasing and review are getting noisy

## Maintainer Defaults

- Enable branch protection on `main`.
- Require pull requests before merging.
- Require passing status checks for CI.
- Enable auto-delete for head branches after merge.
- Prefer squash merging and disable merge commits if the team wants a linear history.
