"""Paper-domain taxonomy and lightweight fallback classification.

The paper note folder should reflect the paper's primary research contribution,
not merely a tool keyword. For example, a VR relaxation system evaluated with
participants is HCI even if it uses AI-assisted generation as a component.
"""
from __future__ import annotations

import re


DOMAIN_RULES = [
    {
        "name": "HCI",
        "description": (
            "Human-centered systems, interaction design, user experience, "
            "user studies, empirical evaluation with participants, VR/AR "
            "experiences, accessibility, CSCW, and health/wellbeing interfaces."
        ),
        "positive_cues": [
            "user study",
            "participants",
            "participant",
            "usability",
            "user experience",
            "interaction",
            "interactive system",
            "human-computer interaction",
            "hci",
            "qualitative feedback",
            "interview",
            "presence",
            "questionnaire",
            "stai",
            "ipq",
            "vr relaxation",
            "virtual reality",
            "art therapy",
            "biofeedback",
        ],
        "priority_rule": (
            "Use HCI when the main contribution is a human-facing system, "
            "interaction technique, user experience, or empirical user study. "
            "This overrides AI/ML when AI is only an enabling component."
        ),
    },
    {
        "name": "Generative AI",
        "description": (
            "Generative models and synthesis methods for image, video, audio, "
            "text, 3D assets, faces, avatars, meshes, diffusion, GANs, and "
            "neural rendering."
        ),
        "positive_cues": [
            "diffusion",
            "generative model",
            "text-to-image",
            "text to image",
            "image generation",
            "video generation",
            "mesh generation",
            "3d generation",
            "neural synthesis",
            "neural rendering",
            "gan",
            "vae",
            "score distillation",
        ],
        "priority_rule": (
            "Use Generative AI as primary only when the proposed model or "
            "generation method is the main contribution."
        ),
    },
    {
        "name": "Computer Science",
        "description": (
            "Algorithms, systems, programming languages, software engineering, "
            "databases, networking, graphics infrastructure, and core computing."
        ),
        "positive_cues": [
            "algorithm",
            "runtime",
            "compiler",
            "database",
            "distributed system",
            "software architecture",
            "graphics pipeline",
            "gpu",
            "rendering pipeline",
        ],
        "priority_rule": (
            "Use Computer Science for core technical mechanisms when no more "
            "specific research domain dominates."
        ),
    },
    {
        "name": "Statistics",
        "description": (
            "Statistical inference, hypothesis testing, estimation, causal "
            "analysis, uncertainty, experimental design, and meta-analysis."
        ),
        "positive_cues": [
            "hypothesis test",
            "p-value",
            "confidence interval",
            "equivalence test",
            "false discovery rate",
            "rank test",
            "rank-based",
            "test statistics",
            "estimator",
            "regression",
            "meta-analysis",
            "statistical power",
        ],
        "priority_rule": (
            "Use Statistics when the main contribution is a statistical method "
            "or evaluation framework."
        ),
    },
    {
        "name": "Mathematics",
        "description": (
            "Mathematical theory, proofs, optimization, linear algebra, "
            "probability theory, calculus, and formal derivations."
        ),
        "positive_cues": [
            "theorem",
            "proof",
            "lemma",
            "optimization",
            "linear algebra",
            "probability theory",
            "matrix",
            "closed form",
        ],
        "priority_rule": (
            "Use Mathematics when the contribution is primarily formal theory "
            "rather than an empirical system or application."
        ),
    },
]


def domain_names() -> list[str]:
    return [d["name"] for d in DOMAIN_RULES]


def prompt_block(extra_domains: list[str] | None = None) -> str:
    """Human-readable taxonomy for the LLM classifier prompt."""
    known = set(domain_names())
    lines = []
    for d in DOMAIN_RULES:
        cues = ", ".join(d["positive_cues"][:10])
        lines.append(
            f"- {d['name']}: {d['description']}\n"
            f"  Cues: {cues}\n"
            f"  Rule: {d['priority_rule']}"
        )
    for name in extra_domains or []:
        if name and name not in known:
            lines.append(f"- {name}: Existing user folder/domain in the vault.")
            known.add(name)
    return "\n".join(lines)


def normalize_domain(name: str, candidates: list[str] | None = None) -> str:
    """Return a canonical candidate casing when possible."""
    raw = re.sub(r"\s+", " ", str(name or "")).strip()
    if not raw:
        return ""
    lookup = {d.lower(): d for d in domain_names()}
    for c in candidates or []:
        if c:
            lookup.setdefault(str(c).strip().lower(), str(c).strip())
    return lookup.get(raw.lower(), raw)


def tag_for_domain(domain: str) -> str:
    tag = str(domain or "").strip().lower()
    tag = tag.replace("&", "and")
    tag = re.sub(r"[\s_]+", "-", tag)
    tag = re.sub(r"[^0-9a-z\-\/]", "", tag)
    tag = re.sub(r"-{2,}", "-", tag)
    return tag.strip("-")


def classify_text_heuristic(text: str, candidates: list[str] | None = None) -> str:
    """Best-effort domain for existing notes or LLM fallback.

    The heuristic intentionally gives HCI a priority boost for user-study and
    human-facing system cues, so papers like ASafePlace do not get filed under
    Generative AI merely because AI is part of the implementation.
    """
    hay = " ".join(str(text or "").lower().split())
    if not hay:
        return ""
    scores: dict[str, int] = {}
    for domain in DOMAIN_RULES:
        score = 0
        for cue in domain["positive_cues"]:
            if _cue_present(hay, cue):
                score += 3 if domain["name"] == "HCI" else 2
        scores[domain["name"]] = score

    # Strong HCI override: human evaluation + interactive/VR/wellbeing context.
    hci_eval = any(
        _cue_present(hay, x)
        for x in ("user study", "participants", "qualitative feedback", "questionnaire")
    )
    hci_context = any(
        _cue_present(hay, x)
        for x in ("interactive", "vr", "virtual reality", "relaxation", "therapy", "presence")
    )
    if hci_eval and hci_context:
        scores["HCI"] = scores.get("HCI", 0) + 8

    best, score = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    if score < 4:
        return ""
    return normalize_domain(best, candidates)


def _cue_present(text: str, cue: str) -> bool:
    """Match cues as words/phrases, not arbitrary substrings."""
    cue = str(cue or "").strip().lower()
    if not cue:
        return False
    pattern = re.escape(cue)
    pattern = pattern.replace(r"\ ", r"[\s\-]+")
    pattern = pattern.replace(r"\-", r"[\s\-]+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text) is not None
