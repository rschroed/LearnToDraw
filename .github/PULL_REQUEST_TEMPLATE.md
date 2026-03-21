## Summary

- What changed?
- Why does it exist?
- What was the slice plan or plan summary?

## Checks

- [ ] `make api-test`
- [ ] `make web-test`
- [ ] `make web-build`
- [ ] I listed the verification I actually ran in the PR body
- [ ] I noted any checks I could not run and why

## Architecture

- [ ] Backend remains the sole owner of hardware access
- [ ] AxiDraw-specific behavior stays isolated to adapters and wrappers
- [ ] Mock adapters still work, or I explained why they changed

## Risk Review

- [ ] I called out any hardware assumptions or undocumented behavior
- [ ] I called out version-sensitive behavior when relevant
- [ ] I updated docs or config notes if behavior changed
- [ ] This PR is a narrow, reviewable slice
