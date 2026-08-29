## Summary

Describe the user-visible change and why it is needed.

## Validation

- [ ] Added or updated tests
- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall -q kb paperroach tests`
- [ ] `python -m pip wheel . --no-deps -w dist`
- [ ] `python scripts/smoke_wheel.py dist`

## Compatibility and Data Safety

- [ ] No migration is needed
- [ ] A migration or rebuild requirement is documented
- [ ] This change preserves user-authored vault content
