---
title: Exponential Relaxation
type: Concept
subject: Affective Computing
source: https://doi.org/10.1140/epjds/s13688-019-0219-3
license: CC BY 4.0
kb-generated: true
public-review: source-checked
tags: [exponential-decay, emotion-dynamics, mathematical-modeling]
---

# Exponential Relaxation

> [!note] Public review copy
> Derived by PaperRoach from Pellert, Schweighofer, and Garcia (2020), then checked against the source. The generated draft accidentally reused the instantaneous regulation equation; this copy restores the paper's continuous relaxation equation. See the [change log](../CHANGELOG.md).

## Definition

Exponential relaxation is a mean-reverting process in which a baseline-centered state changes quickly when far from equilibrium and progressively more slowly as it approaches that equilibrium.

## Formulation

For individual $i$ with baseline $\mu_i$:

$$
\frac{\mathrm{d}x_i(t)}{\mathrm{d}t}=-\gamma\left(x_i(t)-\mu_i\right)+\xi(t)
$$

Ignoring the mean-zero noise in expectation, the state after $\Delta t$ is:

$$
E[x_i(t+\Delta t)]=e^{-\gamma\Delta t}\left(x_i(t)-\mu_i\right)+\mu_i
$$

The factor $e^{-\gamma\Delta t}$ shrinks the distance from baseline. Larger $\gamma$ means faster relaxation.

## Intuition

The mechanism resembles a warm object cooling toward room temperature. The distance to equilibrium is largest at the start, so the expected change is largest then; the change becomes smaller as the state nears its baseline.

## Evidence in the source

The fitted relaxation rate was higher for arousal ($\gamma_a=0.0105\,\mathrm{s}^{-1}$) than for valence ($\gamma_v=0.0070\,\mathrm{s}^{-1}$). Correlation between consecutive status updates first became non-significant after 129 seconds for arousal and 141 seconds for valence.

## Limits

The model describes affect scores inferred from status-update text. The paper notes that the model is not intended to predict sentiment accurately at long timescales.

## Related Concepts

- [[Affective Dynamics Model]]
- [[Individual Baseline]]
- [[Regulation Effect]]

## Source

- Max Pellert, Simon Schweighofer, and David Garcia, *The individual dynamics of affective expression on social media* (2020), https://doi.org/10.1140/epjds/s13688-019-0219-3, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
