# Public review change log

The `*.generated.md` files preserve the actual PaperRoach drafts, with only local paths and internal IDs redacted. The sibling files without `.generated` are the source-checked public copies.

## Redactions applied to the generated paper note

- Replaced the absolute Zotero storage path in `kb-source` with `[redacted-local-path]`.
- Replaced the local `kb-doc-id` with `[redacted-internal-id]`.
- Added an unreviewed-output warning and a portable CC BY 4.0 attribution notice to every generated draft.
- Normalized the published generated copies to LF line endings and removed trailing whitespace; analytical text was not changed.

No analytical claim or formula was corrected in `paper-note.generated.md`; the mistakes remain visible for comparison.

## Corrections in the reviewed paper note

- Changed the automated `Computer Science / Computer Vision` routing to `Affective Computing / Computational Social Science`.
- Replaced the ambiguous `Pages: 1` metadata. The journal uses article number 1; the PDF has 14 pages.
- Corrected Equation (4) so the arousal branch uses $\gamma_a$, $k_a$, and $\epsilon_a$, not copied valence variables.
- Clarified that individual baselines are computed per user, while $k$ and $\gamma$ are estimated with pooled nonlinear regression over 16,863,066 consecutive update pairs.
- Replaced broad claims about internal emotional states with the paper's measured quantity: text-derived expressed valence and arousal.
- Added exact reported values for baselines, short-timescale correlation, relaxation rates, and regulation coefficients.
- Added the paper's limitations on prediction, self-selection, performative posting, and observational interpretation.
- Removed local-vault related-paper suggestions because they are not part of the source paper's reference list or this public bundle.
- Kept the blank `My Notes` section to demonstrate PaperRoach's user-owned editing boundary.

## Corrections in the reviewed concept notes

- **Affective Dynamics Model:** separated the instantaneous expression-associated component from continuous exponential relaxation; identified pooled estimates.
- **Exponential Relaxation:** replaced the incorrectly reused regulation equation with the paper's mean-reverting differential equation and expected-value solution.
- **Individual Baseline:** restored the source notation $\mu_i$, described how baselines are estimated, and limited interpretation to the observed sample and text measure.
- **Regulation Effect:** restored $\mu_i$, distinguished it from relaxation, and removed causal and clinical overreach.

## Reproducibility note

The historic local run did not retain the exact Ollama model tag or PaperRoach package version. The manifest reports those fields as not recorded rather than guessing them.
