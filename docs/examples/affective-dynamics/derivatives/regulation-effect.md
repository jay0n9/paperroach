---
title: Regulation Effect
type: Concept
subject: Affective Computing
source: https://doi.org/10.1140/epjds/s13688-019-0219-3
license: CC BY 4.0
kb-generated: true
public-review: source-checked
tags: [emotion-regulation, social-media, computational-modeling]
---

# Regulation Effect

> [!note] Public review copy
> Derived by PaperRoach from Pellert, Schweighofer, and Garcia (2020), then checked against the source. Causal wording was softened and the source notation $\mu_i$ was restored. See the [change log](../CHANGELOG.md).

## Definition

In the paper's model, the regulation effect is an **expression-associated, instantaneous proportional movement** of baseline-centered valence or arousal toward zero. It is represented by $k$, the fraction of the pre-expression deviation that remains.

## Formulation

$$
x_i(t_{\mathrm{after}})=\left(x_i(t_{\mathrm{before}})-\mu_i\right)k+\mu_i
$$

- $x_i(t_{\mathrm{before}})$: expressed affect before the modeled expression event.
- $x_i(t_{\mathrm{after}})$: expressed affect immediately after it.
- $\mu_i$: the individual's observed baseline.
- $k$: the remaining fraction; $0<k<1$ moves the value toward baseline.

## Intuition

After centering a user's score on their baseline, multiply the deviation by $k$. A value of $k=0.4$ leaves 40% of the prior deviation and removes 60% in the model's instantaneous component. Continuous exponential relaxation is a separate mechanism.

## Evidence in the source

The fitted coefficients were $k_v=0.38$ for valence and $k_a=0.45$ for arousal. The paper interprets these values as a considerable regulation effect associated with affective expression.

## Limits

The analysis is observational and measures expression through lexicon scores. The coefficient does not by itself prove that composing a post causes the corresponding internal emotional change. It should not be used as clinical advice.

## Related Concepts

- [[Affective Dynamics Model]]
- [[Exponential Relaxation]]
- [[Individual Baseline]]

## Source

- Max Pellert, Simon Schweighofer, and David Garcia, *The individual dynamics of affective expression on social media* (2020), https://doi.org/10.1140/epjds/s13688-019-0219-3, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
