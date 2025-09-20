# How Status is Determined

The final `Development Status` is determined using a waterfall logic. The tool checks for statuses in order, from most
to least mature.

A project **must** pass check **R1** (have at least one release on PyPI) to be classifiable beyond `Planning`.

---

### Production/Stable (Status 5)

A project is classified as `Production/Stable` if it passes **ALL** of the following checks and its version is
`>=1.0.0`:

- **Release/packaging:** R1–R6
- **Quality discoverability:** Q1–Q7
- **API stability:** S1
- **Deprecation hygiene:** D1
- **Security/supply chain:** C1–C4
- **Maintenance:** M1–M2
- **Completeness:** At least 4 of 5 `Cmpl` checks must pass.

---

### Mature (Status 6)

A project is `Mature` if it meets all `Production/Stable` criteria **AND**:

- Its first `1.0.0` release was at least **24 months** ago.
- Its release cadence is relaxed: **R4** (recent release) is only required within the last **24 months**.

---

### Planning, Pre-Alpha, Alpha, Beta (Statuses 1-4)

For projects that are not yet Production/Stable, a status is assigned based on an **Early-Phase Score (EPS)**. The score
is the total number of checks passed from the following set:

`{R2, R3, R5, R6, Q1, Q2, Q3, Q4, Q5, Q6, Q7, S1, D1, C1, C3, C4, M1}`

| Status            | EPS Score | Version Constraint | Other Constraints                                                    |
|-------------------|-----------|--------------------|----------------------------------------------------------------------|
| **1 - Planning**  | `0 - 3`   | `<0.1.0`           | Fails R1 (no release) or meets score/version requirements.           |
| **2 - Pre-Alpha** | `4 - 6`   | `<0.1.0`           | -                                                                    |
| **3 - Alpha**     | `7 - 11`  | `<1.0.0`           | -                                                                    |
| **4 - Beta**      | `≥ 12`    | `<1.0.0`           | Must pass R4 (release in last 12 months) and ≥3 completeness checks. |