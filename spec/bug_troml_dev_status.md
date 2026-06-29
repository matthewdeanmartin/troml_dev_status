# Bug report: `troml-dev-status validate` fails a project's *first* release

- **Tool:** `troml-dev-status`
- **Version:** 0.6.1
- **Subcommand:** `troml-dev-status validate .`
- **Reporter context:** gui4aws, preparing its first-ever release (0.1.0) to PyPI.

## Summary

`troml-dev-status validate` exits non-zero (exit code `2`) for any project that
has **not yet been published to PyPI**, because it unconditionally infers
`Development Status :: 1 - Planning` when there is no release history — regardless
of how complete, tested, and mature the codebase actually is.

This makes the `validate` subcommand unusable as a pre-publish quality gate: the
one moment you most want to validate your classifier (just before the first
`uv publish`) is exactly the moment the tool is guaranteed to disagree with any
classifier above "Planning". It is a chicken-and-egg failure.

## Steps to reproduce

1. Take any repo that is **not** on PyPI yet.
1. Declare a reasonable first-release classifier in `pyproject.toml`, e.g.:
   ```toml
   classifiers = ["Development Status :: 3 - Alpha"]
   ```
1. Run:
   ```bash
   troml-dev-status validate .
   ```

## Observed behaviour

```
Mismatch detected.
  Declared: Development Status :: 3 - Alpha
  Inferred: Development Status :: 1 - Planning
```

Exit code: `2`.

`troml-dev-status analyze .` shows the project passing essentially every
*code-quality* signal the tool measures:

| ID | Check | Status |
|-------|----------------------|--------|
| C3 | Dependencies Pinned | OK |
| C4 | Reproducible Dev Env | OK |
| Cmpl1 | TODO markers | OK (0 per 1k LOC) |
| Cmpl2 | NotImplemented usage | OK (0/834) |
| Cmpl3 | Placeholder `pass` | OK (0.24%) |
| Cmpl4 | Stub files | OK (0/187) |
| Fail0 | Zero file count | OK (187 files) |
| Fail1 | Tiny code base | OK (21,682 LOC) |
| Fail10| Bad metadata | OK |
| Fail11| Pointless content | OK (187/187) |

…yet the final verdict is:

```
Final Inferred Classifier: Development Status :: 1 - Planning
Reason: Project has no releases on PyPI.
```

So a single missing signal — *"no PyPI releases yet"* — overrides every positive
code-maturity signal and pins the inference to "Planning".

## Expected behaviour

For a pre-publish project, one of the following would make `validate` usable as a
release gate:

1. **Don't hard-floor to "Planning" on zero releases.** Treat "no release history"
   as *absence of evidence*, not as *evidence of immaturity*. Fall back to the
   classifier inferred from the code-quality signals (which here would be well
   above "Planning").
1. **Provide an opt-out / tolerance**, e.g.
   `troml-dev-status validate . --allow-first-release` or a
   `[tool.troml-dev-status] require_release_history = false` setting, so the
   no-releases signal is skipped on the first publish.
1. **Distinguish "validate against declared" from "infer absolute".** Allow the
   declared classifier to be accepted when the only disagreement is driven by
   release-history signals the project cannot satisfy until after it ships.

## Impact / workaround

Because `validate` cannot pass before the first publish, we removed it from the
blocking pre-release gate and made it **advisory** (`... || true`) in our
`Makefile`'s `dev-status` target. We intend to re-enable it as a hard gate once
0.1.0 is on PyPI and the release-history signal can actually be satisfied. See the
`dev-status` target comment in the `Makefile`.

This is a reasonable workaround, but it means the tool provides no value at the
exact point it is most needed (first release), and it silently stops gating until
someone remembers to flip it back.

## Suggested priority

Medium. The tool is otherwise useful; this single behaviour just makes the
`validate` gate unusable for greenfield/first-release projects, which is a common
and important case.
