# Guide Service Dependency Security Audit — D2-33

**Audit date:** 19 November 2026
**Repository:** `ujala100/setu-guide`
**Base branch:** `dev`

## 1. Runtime dependency audit

Command:

```bash
pip-audit -r requirements.txt
```

Result:

```text
No known vulnerabilities found
```

No known vulnerabilities were reported in the runtime dependencies at the time of this audit.

## 2. Development dependency audit

Command:

```bash
pip-audit -r requirements-dev.txt
```

Result:

```text
No known vulnerabilities found
```

No known vulnerabilities were reported in the development dependencies at the time of this audit.

## 3. Test results

Command:

```bash
python -m pytest tests/ -v
```

Result:

```text
323 passed, 3 skipped, 2 warnings in 6.12s
```

- Passed: 323
- Skipped: 3
- Warnings: 2
- Failed: 0

The warning details were not captured in the audit results.

## 4. Test environment

- Test dependencies were installed in a temporary virtual environment.
- The dependency audit tool was installed in an isolated temporary environment.
- No project dependency files were changed for the audit.
- The repository working tree was clean after testing.

## 5. Conclusion

- Runtime dependency audit: No known vulnerabilities found.
- Development dependency audit: No known vulnerabilities found.
- Guide service tests: 323 passed, 3 skipped, 2 warnings.
- No dependency or application-code changes were made.

This is a documentation-only change. No dependencies, lockfiles, application code, or CI configuration are changed.
