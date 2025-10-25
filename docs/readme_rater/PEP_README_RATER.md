PEP: 8001
Title: Prescriptive Readme Quality Analysis via LLM
Author: Matthew Martin, Gemini 2.5 and ChatGPT
Status: Draft
Type: Informational
Created: 25-Oct-2025
Post-History: 26-Oct-2025 (Revised rubric, scoring, and hashing)

---

## Abstract

This PEP proposes a standardized methodology and reference tool for evaluating the quality of Python package README.md
files. It advocates moving beyond simple, brittle structural heuristics (e.g., "contains ## Installation") to a
goal-oriented, rubric-based evaluation.

This evaluation will be performed by a Large Language Model (LLM) accessed via an OpenAI-compatible API (such as
OpenRouter). The tool will provide prescriptive, actionable feedback in a machine-readable format (TOML). The proposal
includes specifications for context-aware prompting, efficient iterative analysis (convergence), and stateful caching to
create a practical and cost-effective tool for developers.

---

## Motivation

The README.md file is arguably the most critical piece of documentation for a new user. It is the "front page" of a
project. However, existing linting and quality-checking tools are rudimentary. They typically rely on regular
expressions or simple AST (Abstract Syntax Tree) checks to enforce structural conventions.

This approach is brittle and often fails:

* It misses semantic equivalence: A linter checking for ## Installation will fail if a project instead has a section ###
  Getting Started that links to a comprehensive docs/INSTALL.md page, even though the goal of guiding the user to
  installation is met.
* It cannot gauge quality: A linter can confirm a ## Usage section exists, but it cannot determine if the example code
  within it is clear, functional, or helpful.
* It provides poor advice: The resulting advice is often "Add ## Installation section," which doesn't help the developer
  improve the clarity of their existing instructions.

This PEP proposes a tool that judges a README not on its structure, but on its effectiveness in serving its key
audiences.

---

## Rationale

Large Language Models (LLMs) are uniquely suited to this task. They excel at semantic understanding and goal-oriented
reasoning.

Instead of asking, "Does a Markdown header matching ## Usage exist?" we can ask the LLM, "Can a new user find a clear,
minimal code example to understand this package's primary function?" This allows for infinite flexibility in how the
developer structures their README, so long as the goal is achieved.

This approach provides:

* **Nuanced Feedback:** The LLM can explain why a section is confusing or how an example could be improved.
* **Flexibility:** It respects developer freedom, caring about the "what" (clarity, accessibility of information) rather
  than the "how" (specific header names).
* **Actionability:** The feedback is prescriptive (e.g., "The installation instructions are present but buried. Move
  them closer to the top.")

---

## Specification

### 1. The Evaluation Rubric

The evaluation must be based on a two-tiered rubric, separating essential items from value-add (extra credit) items. The
`overall_score` will primarily be determined by the Core Items, but Extra Credit items can elevate the total score to a
perfect 100%.

### Scoring System (Expanded Prescription)

Each rubric item contributes to a weighted total score between 0 and 100. Core items contribute up to 80 points; extra
credit items contribute up to 20 points. However, extra credit can **replace missing mandatory items** — allowing
flexibility for specialized projects.

This ensures that:

* A project achieving 100% of core items scores 80.
* A project may reach 100% overall by completing all core items **or** 80% of core items plus sufficient extra credit.
* If a core item is marked *not applicable*, the points are redistributed proportionally across remaining core items.

Formally:

```
core_score = (passed_core / total_core) * 80
extra_score = (passed_extra / total_extra) * 20

if core_score + extra_score > 100:
    total_score = 100
else:
    total_score = core_score + extra_score
```

This adaptive scoring avoids penalizing niche or infrastructure libraries that may lack demos or visualizations.

### Core Items (80%)

Persona: **Potential User (The Evaluator)**

* **CLARITY_OF_PURPOSE:** Concise one-paragraph description of package purpose.
* **QUICKSTART_INSTALL:** Clear `pip install` or link to installation guide.
* **HELLO_WORLD_EXAMPLE:** Minimal example demonstrating main use case.
* **VISUAL_DEMONSTRATION:** Screenshot, GIF, or output if applicable.

Persona: **Contributor (The Collaborator)**

* **CONTRIBUTION_GATEWAY:** CONTRIBUTING.md link or section.
* **DEVELOPMENT_SETUP:** Instructions for local setup and tests.
* **LICENSE_CLARITY:** Explicit license link or declaration.

Persona: **Auditor (The Maintainer)**

* **PROJECT_HEALTH_BADGES:** CI, coverage, and PyPI version badges.

### Extra Credit Items (20%)

### Extra Credit Items (20%)

These items represent advanced or value-added documentation features that demonstrate maturity, transparency, and user
empathy. They are **not required** for usability but reward projects that go beyond the basics. Passing these can offset
up to 20% of the score.

#### Persona: **Potential User (Evaluator)**

* **PRIOR_ART_COMPARISON:** Discussion of similar tools or ecosystem placement.
* **DESIGN_RATIONALE:** Justification of design decisions or guiding philosophy.
* **TUTORIAL_OR_WALKTHROUGH:** Link to an in-depth tutorial, screencast, or example project.
* **REAL_WORLD_USAGE:** Mentions adopters, testimonials, or practical case studies.
* **PERFORMANCE_SECTION:** Benchmarks or performance comparisons.
* **CONTAINER_IMAGE_LINK:** Provides a ready-to-use Docker or OCI image.
* **SUPPORT_MATRIX:** Clear table of supported Python versions and platforms.
* **I18N_SUPPORT_INFO:** Notes on multilingual support or localization readiness.
* **ACCESSIBILITY_DISCUSSION:** Mentions accessibility or usability considerations.
* **ETHICAL_STATEMENT:** Notes on ethical stance, sustainability, or social responsibility.

#### Persona: **Contributor (Collaborator)**

* **CHANGELOG_LINK:** Direct link to CHANGELOG.md or release notes.
* **ROADMAP_OR_VISION:** Summary of planned features or project trajectory.
* **COMMUNITY_GUIDELINES:** Links to a Code of Conduct or contribution etiquette.
* **FUNDING_INFORMATION:** Mentions ways to support or sponsor the project.
* **ACKNOWLEDGMENTS:** Credits contributors, upstream projects, or community efforts.
* **CONFIGURATION_EXAMPLES:** Includes real configuration or environment examples.

#### Persona: **Maintainer (Auditor / Technical Steward)**

* **API_REFERENCE_LINK:** Direct link to full API or module documentation.
* **ARCHITECTURE_OVERVIEW:** Diagram or narrative explaining system design.
* **DEPENDENCY_POLICY:** States dependency management philosophy (e.g., minimal, pinned).
* **REPRODUCIBILITY_NOTES:** Mentions deterministic builds or reproducible environments.
* **SECURITY_POLICY_LINK:** Mentions vulnerability disclosure or security policy.

---

### 2. Scoring Interpretation

The `overall_score` will be expressed in both numeric and qualitative terms:

| Numeric Range | Label             | Meaning                                          |
|---------------|-------------------|--------------------------------------------------|
| 0-39          | Problematic       | Fails key criteria (no clear purpose or install) |
| 40-69         | Needs Improvement | Partial coverage, weak clarity or usability      |
| 70-89         | Good              | Solid documentation; all essential info present  |
| 90-100        | Excellent         | Complete and refined documentation, extra polish |

Extra credit cannot push a project past 100%. Its intent is to **forgive omissions** that are irrelevant to a given type
of project (e.g., CLI utilities without visuals).

---

### 3. Implementation and Caching

The reference tool (`readme-rater`) uses a normalized hash of the README and incremental analysis to avoid redundant LLM
calls. Results are stored in `.readme_rater.toml`, merging previous passes with new analyses.

---

## Reference Implementation

See Appendix A in the original pseudocode. The implementation prescribes normalization, cache handling, and convergence.

---

## Copyright

This document is placed in the public domain or under the CC0-1.0-Universal license, whichever is more permissive.
