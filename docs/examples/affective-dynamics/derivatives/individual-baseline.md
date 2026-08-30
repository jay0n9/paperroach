---
title: Individual Baseline
type: Concept
subject: Affective Computing
source: https://doi.org/10.1140/epjds/s13688-019-0219-3
license: CC BY 4.0
kb-generated: true
public-review: source-checked
tags: [individual-differences, emotion-dynamics, baseline-modeling]
---

# Individual Baseline

> [!note] Public review copy
> Derived by PaperRoach from Pellert, Schweighofer, and Garcia (2020), then checked against the source. Wording was narrowed to text-derived expressed affect and the original notation $\mu_i$ was restored. See the [change log](../CHANGELOG.md).

## Definition

An individual baseline $\mu_i$ is the person's long-run average level of expressed valence or arousal in the analyzed status updates. The model treats this value as the equilibrium toward which a baseline-centered affect score tends to return in the absence of modeled stimulation.

## Estimation

The paper estimates each user's baseline as the mean valence or arousal score over that user's analyzed updates. It subtracts these individual means before fitting the pooled relaxation and regulation parameters.

## Intuition

Two people can use affective language differently even when each is close to their own usual pattern. Centering on a personal baseline avoids treating a single universal midpoint as the equilibrium for everyone.

## Evidence in the source

Across users, baseline valence was concentrated slightly above the midpoint of the 1–9 scale, with mean 5.88. Baseline arousal was below the midpoint, with mean 4.13. These are aggregate descriptions of the study sample, not universal emotional norms.

## Limits

The baseline is computed from observed Facebook text between 2009 and 2011. It may reflect platform, language, selection, and measurement effects, and it should not be interpreted as a clinical trait or a complete measure of internal emotion.

## Related Concepts

- [[Affective Dynamics Model]]
- [[Exponential Relaxation]]
- [[Regulation Effect]]

## Source

- Max Pellert, Simon Schweighofer, and David Garcia, *The individual dynamics of affective expression on social media* (2020), https://doi.org/10.1140/epjds/s13688-019-0219-3, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
