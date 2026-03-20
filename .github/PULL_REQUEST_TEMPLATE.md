## Summary

- What changed?
- Why does it exist?

## Checks

- [ ] `make api-test`
- [ ] `make web-test`
- [ ] `make web-build`
- [ ] I noted any checks I could not run and why

## Architecture

- [ ] Backend remains the sole owner of hardware access
- [ ] AxiDraw-specific behavior stays isolated to adapters and wrappers
- [ ] Mock adapters still work, or I explained why they changed

## Risk Review

- [ ] I called out any hardware assumptions or undocumented behavior
- [ ] I updated docs or config notes if behavior changed
- [ ] This PR is a narrow, reviewable slice
