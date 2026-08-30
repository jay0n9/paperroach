---
Date: 2026-07-27
Type:
- Concept
Subject: Computer Science
Parent:
- '[[Computational Modeling]]'
Sibling:
- '[[Exponential Relaxation]]'
- '[[Individual Baseline]]'
- '[[Regulation Effect]]'
Status:
tags:
- Computer_Science
- computational-modeling
- affective-computing
- emotion-dynamics
- psychology
- social-media
kb-generated: true
---
> [!warning] Unreviewed generated output
> This file preserves the actual PaperRoach draft for transparency. It is **not source-verified and should not be cited**. Only local paths and internal IDs were redacted; use the sibling reviewed file for corrected content.
>
> [!info] Attribution
> Adapted from Max Pellert, Simon Schweighofer, and David Garcia, *The individual dynamics of affective expression on social media* (2020), [DOI](https://doi.org/10.1140/epjds/s13688-019-0219-3), © The Author(s) 2020, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). A publication warning was added and local-only metadata was redacted where present; see [attribution and changes](../ATTRIBUTION.md).

# Affective Dynamics Model
---

## Definition

The Affective Dynamics Model is a computational framework that describes how individuals' emotional states—specifically valence (positive/negative sentiment) and arousal (intensity of emotion)—return to an individual-specific baseline after being stimulated by an emotional event, such as posting on social media. This model integrates insights from the Cyberemotions and DynAffect models, emphasizing the exponential nature of emotional recovery and the regulatory effect of emotional expression.

## Formulation

The model is formalized with the equation:
$$x_{i}(t_{\text{after}})=\left(x_{i}(t_{\text{before}})-u_{i}\right)\cdot k+u_{i}$$

Where:
- $x_{i}(t_{\text{after}})$ is the emotional state (valence or arousal) of individual $i$ after the emotional expression.
- $x_{i}(t_{\text{before}})$ is the emotional state of individual $i$ before the emotional expression.
- $u_{i}$ is the individual-specific baseline for emotional state $i$.
- $k$ is a constant factor representing the regulation effect of emotional expression, which determines how strongly the emotional state is pulled toward the baseline.

This equation captures the idea that emotional states exponentially return to a baseline after being stimulated, with the regulation effect modulated by the constant $k$.

## Intuition

Imagine you are feeling very happy (high valence) after receiving good news. If you then post about this on social media, the act of expressing your emotion helps you return to your usual emotional state—your baseline. The Affective Dynamics Model suggests that this return is not immediate but happens gradually, like a pendulum swinging back to its resting position. The speed and strength of this return depend on individual differences and the nature of the emotional expression. The model helps explain how people regulate their emotions through social media, providing a quantitative way to understand the emotional "reset" that occurs after expressing feelings.

## Applications

The Affective Dynamics Model has several important applications:
- **Affective Computing**: It aids in the development of systems that can detect, interpret, and respond to human emotions, particularly in social media contexts.
- **Collective Emotion Detection**: By analyzing large-scale social media data, the model helps understand how individual emotional dynamics contribute to broader patterns of collective emotions.
- **Psychological Research**: It provides a framework for studying emotional regulation and its impact on mental health, offering insights into abnormal or pathological emotional dynamics.
- **Social Media Analytics**: The model can be used to analyze user behavior, track emotional trends, and improve content recommendation systems by understanding how users express and regulate their emotions online.

## Related Concepts

%% kb-related-concepts-start %%
- [[Regulation Effect]]
- [[Individual Baseline]]
- [[Affective Circumplex Model]]
- [[Exponential Relaxation]]
- [[Neural Regression Model]]
%% kb-related-concepts-end %%

## Source

- From: [[The individual dynamics of affective expression on social media (2020)]]

---
# References
