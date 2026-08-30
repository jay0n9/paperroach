---
title: Affective Dynamics Model
type: Concept
subject: Affective Computing
source: https://doi.org/10.1140/epjds/s13688-019-0219-3
license: CC BY 4.0
kb-generated: true
public-review: source-checked
tags: [affective-dynamics, computational-modeling, social-media]
---

# Affective Dynamics Model

> [!note] Public review copy
> Derived by PaperRoach from Pellert, Schweighofer, and Garcia (2020), then checked against the source. The generated draft's local metadata was removed and its two model components were separated correctly. See the [change log](../CHANGELOG.md).

## Definition

The affective dynamics model describes short-timescale changes in **text-derived expressed valence and arousal** relative to a person's observed baseline. It combines two mechanisms: an immediate proportional movement associated with expression and a continuous exponential relaxation between expressions.

## Formulation

The expression-associated component is:

$$
x_i(t_{\mathrm{after}})=\left(x_i(t_{\mathrm{before}})-\mu_i\right)k+\mu_i
$$

The mean-reverting relaxation component is:

$$
\frac{\mathrm{d}x_i(t)}{\mathrm{d}t}=-\gamma\left(x_i(t)-\mu_i\right)+\xi(t)
$$

where $\mu_i$ is the individual's baseline, $k$ is the fraction remaining after the expression-associated adjustment, $\gamma$ is the relaxation rate, and $\xi(t)$ represents unmodeled influences.

## Intuition

First center a person's expressed affect around their own long-run average. A new expression is associated with an immediate reduction in that baseline-centered magnitude. The remaining deviation then decays over time. The model therefore separates a discrete event from the continuous passage of time.

## Evidence in the source

The paper fits the model to 16,863,066 consecutive status-update pairs. It reports $k_v=0.38$, $k_a=0.45$, $\gamma_v=0.0070\,\mathrm{s}^{-1}$, and $\gamma_a=0.0105\,\mathrm{s}^{-1}$. These are pooled regression estimates, not a separate $k$ and $\gamma$ fit for every user.

## Limits

This is an observational model of affective expression measured with text lexicons. It does not prove that posting causes emotional recovery, and it is not a clinical or long-horizon prediction model.

## Related Concepts

- [[Exponential Relaxation]]
- [[Individual Baseline]]
- [[Regulation Effect]]

## Source

- Max Pellert, Simon Schweighofer, and David Garcia, *The individual dynamics of affective expression on social media* (2020), https://doi.org/10.1140/epjds/s13688-019-0219-3, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
