# TODO

- [ ] Fix InstaRadar (3rd fallback) gating so it runs when Inflact fails, even if Instapeep was only rate-limited (e.g., 429) and not disabled via 503.
- [x] Remove/disable FORCE_INSTARADAR debug logic if not desired for production.
- [ ] Run daily collector once (or targeted run) to verify InstaRadar is called after an Inflact timeout.
- [ ] Verify git diff is clean and commit the changes.


