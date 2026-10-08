---
name: release
description: Cut a new CozyBot version for production. Use whenever the user wants to release, ship, publish a new version, bump the version, or move dev to prod. Updates CHANGELOG.md and the version string in every place it appears, in one commit.
---

# Release a new CozyBot version

This is how every release from 2.0.1 to 2.2.0 was made. Follow it in order. Commit rules in `.claude/rules/commits.md` apply.

## 1. Check the starting point

- Be on `dev`, with a clean working tree (`git status --porcelain` prints nothing).
- Find the current version: `grep -m1 '^## \[' CHANGELOG.md`.
- List what changed since the last release:
  `git log --format='%h %s' $(git log -1 --format=%h --grep='^feat: [0-9]\+\.[0-9]\+\.[0-9]\+$')..dev`

## 2. Choose the version number

Semantic versioning, `MAJOR.MINOR.PATCH`:

- only `fix:` commits since the last release: bump PATCH (2.2.0 to 2.2.1)
- at least one user-facing `feat:`: bump MINOR (2.2.0 to 2.3.0)
- breaking change for users or the API: bump MAJOR, only if the user asks

Propose the number and the changelog draft to the user, and wait for their approval before editing anything.

## 3. Write the CHANGELOG.md entry

Add the new section at the top, right after the intro line `All notable changes to this project will be documented in this file.`, above the previous version:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added

- ...

### Changed

- ...

### Fixed

- ...
```

- Use only the headings that have entries, in this order: Added, Changed, Fixed, Removed.
- One bullet per user-visible change, in English, a full sentence ending with a period. Describe the effect for users, not the code. Wrap command names in backticks (`/rain`).
- Leave out internal-only changes (refactors, tests, CI) unless they change behaviour.
- Date is today, in UTC.
- Do not edit older entries.

## 4. Update the version everywhere

Replace the old version with the new one in all of these. They all must change together (the two web files were missed around 2.1.6 and needed the follow-up commit 484f32c):

| File | What to change |
|---|---|
| `README.md` | title `# CozyBot vX.Y.Z` and the shields.io badge `Version-X.Y.Z-blue` |
| `scripts/deploy.sh` | banner line `Version X.Y.Z` (keep the box alignment: same total width) |
| `stack/apps/bot/api/app.py` | `version="X.Y.Z"` and the root route `"version": "X.Y.Z"` (2 places) |
| `stack/apps/bot/api/routes/health.py` | `"version": "X.Y.Z"` |
| `stack/apps/bot/live_api/app.py` | `version="X.Y.Z"` |
| `stack/apps/bot/main.py` | `Welcome to CozyBot CLI vX.Y.Z` |
| `stack/apps/bot/utils/logging_utils.py` | banner line `Version X.Y.Z` (same alignment rule) |
| `web/src/app/shared/footer/footer.component.ts` | `version = 'X.Y.Z';` |
| `web/src/app/shared/header/header.component.ts` | `version = 'X.Y.Z';` |

Do not touch `web/package.json` (its own `version` stays `0.0.0`; `karma-coverage` `~2.2.0` is a dependency, not our version).

Then verify nothing was missed. This must print only CHANGELOG.md lines and the `karma-coverage` dependency:

```bash
git grep -n -F 'OLD.VERSION' -- . ':!*.lock'
```

And this must print exactly 11 lines, the version spots of the table above (`README.md` and `api/app.py` have 2 each):

```bash
git grep -n -F 'NEW.VERSION' -- . ':!CHANGELOG.md' ':!*.lock' | grep -v karma-coverage
```

If a new place showing the version was added since this skill was written, update it and add it to the table above in the same release.

## 5. Commit

One atomic commit containing only CHANGELOG.md and the version strings:

```
feat: X.Y.Z
```

No body. Author kitsuiwebster, no co-author line.

## 6. Ship to production (only with the user's explicit go)

Pushing `main` deploys to production automatically (`.github/workflows/prod-deploy.yml`). Never push without the user saying so for this release.

1. Before pushing, check that the deploy target in `.github/workflows/prod-deploy.yml` is the current production server.
2. Push `dev` first (`git push origin dev`), this deploys to the dev environment.
3. Bring `main` to `dev` (fast-forward when possible): `git checkout main && git merge --ff-only dev && git push origin main && git checkout dev`.
4. Watch the workflow: `gh run watch $(gh run list --workflow=prod-deploy.yml -L1 --json databaseId -q '.[0].databaseId')`.

## 7. Verify in production

- `curl -s https://api.cozybot.online/api/public/health` shows the new version.
- The website header and footer show the new version.
- Report the result to the user with the evidence.
