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
            "computer vision",
            "image",
            "video",
            "recognition",
            "face recognition",
            "facial recognition",
            "face reconstruction",
            "3d face",
            "shape model",
            "active shape model",
            "point distribution model",
            "body model",
            "skinned multi-person",
            "blend skinning",
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
            "multiple testing",
            "equivalence test",
            "false discovery rate",
            "t test",
            "correlation",
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

SUBDOMAIN_RULES = {
    "Computer Science": [
        {
            "name": "Algorithms & Theory",
            "positive_cues": [
                "algorithm",
                "complexity",
                "data structure",
                "approximation",
                "theorem",
                "proof",
                "graph algorithm",
            ],
        },
        {
            "name": "Artificial Intelligence",
            "positive_cues": [
                "artificial intelligence",
                "planning",
                "reasoning",
                "agent",
                "knowledge representation",
                "reinforcement learning",
            ],
        },
        {
            "name": "Machine Learning",
            "positive_cues": [
                "machine learning",
                "deep learning",
                "neural network",
                "training",
                "classification",
                "representation learning",
                "self-supervised",
            ],
        },
        {
            "name": "Computer Vision",
            "positive_cues": [
                "computer vision",
                "dataset",
                "image recognition",
                "face recognition",
                "facial recognition",
                "object detection",
                "segmentation",
                "pose estimation",
                "facial expression",
                "active shape model",
                "point distribution model",
                "facial component",
                "single-view",
                "3d reconstruction",
            ],
        },
        {
            "name": "Computer Graphics",
            "positive_cues": [
                "computer graphics",
                "rendering",
                "mesh",
                "3d face reconstruction",
                "face reconstruction",
                "3d face model",
                "morphable face model",
                "3d morphable",
                "statistical face model",
                "animation",
                "geometry processing",
                "avatar",
                "body model",
                "skinned multi-person",
                "blend skinning",
                "facial shape",
                "blendshape",
                "riggable",
                "uv",
            ],
        },
        {
            "name": "Systems & Networking",
            "positive_cues": [
                "operating system",
                "distributed system",
                "computer network",
                "network protocol",
                "runtime",
                "scheduler",
                "throughput",
                "latency",
            ],
        },
        {
            "name": "Databases & Information Retrieval",
            "positive_cues": [
                "database",
                "query processing",
                "indexing",
                "information retrieval",
                "search engine",
                "ranking",
            ],
        },
        {
            "name": "Software Engineering",
            "positive_cues": [
                "software engineering",
                "program analysis",
                "software testing",
                "unit testing",
                "debugging",
                "code generation",
                "developer tools",
            ],
        },
        {
            "name": "Programming Languages",
            "positive_cues": [
                "programming language",
                "compiler",
                "type system",
                "static analysis",
                "interpreter",
                "syntax",
            ],
        },
        {
            "name": "Security & Privacy",
            "positive_cues": [
                "security",
                "privacy",
                "cryptography",
                "attack",
                "malware",
                "vulnerability",
                "differential privacy",
            ],
        },
    ],
    "HCI": [
        {
            "name": "VR/AR Interaction",
            "positive_cues": [
                "vr",
                "virtual reality",
                "augmented reality",
                "mixed reality",
                "presence",
                "immersive",
                "head-mounted display",
            ],
        },
        {
            "name": "User Experience & Usability",
            "positive_cues": [
                "user experience",
                "usability",
                "questionnaire",
                "interview",
                "qualitative feedback",
            ],
        },
        {
            "name": "Health & Wellbeing",
            "positive_cues": [
                "wellbeing",
                "mental health",
                "relaxation",
                "anxiety",
                "therapy",
                "biofeedback",
            ],
        },
        {
            "name": "Creativity & Design Tools",
            "positive_cues": [
                "design tool",
                "creativity",
                "co-creation",
                "personalization",
                "art therapy",
            ],
        },
        {
            "name": "CSCW & Social Computing",
            "positive_cues": [
                "collaboration",
                "social computing",
                "cscw",
                "community",
                "group work",
            ],
        },
    ],
    "Generative AI": [
        {
            "name": "Image Generation",
            "positive_cues": ["text-to-image", "image generation", "diffusion image"],
        },
        {
            "name": "Video Generation",
            "positive_cues": ["video generation", "text-to-video", "temporal"],
        },
        {
            "name": "3D Generation",
            "positive_cues": ["3d generation", "mesh generation", "neural rendering"],
        },
        {
            "name": "Language Models",
            "positive_cues": ["large language model", "llm", "text generation"],
        },
        {
            "name": "Generative Evaluation",
            "positive_cues": ["benchmark", "evaluation", "fid", "human preference"],
        },
    ],
    "Statistics": [
        {
            "name": "Statistical Inference",
            "positive_cues": [
                "hypothesis test",
                "confidence interval",
                "p-value",
                "multiple testing",
                "false discovery rate",
                "equivalence test",
                "t test",
                "correlation",
                "meta-analysis",
            ],
        },
        {
            "name": "Regression & Causal Analysis",
            "positive_cues": ["regression", "causal", "treatment effect"],
        },
        {
            "name": "Experimental Design",
            "positive_cues": ["experimental design", "statistical power", "sample size"],
        },
    ],
    "Mathematics": [
        {
            "name": "Linear Algebra",
            "positive_cues": ["linear algebra", "matrix", "eigenvalue"],
        },
        {
            "name": "Optimization",
            "positive_cues": ["optimization", "convex", "gradient"],
        },
        {
            "name": "Probability Theory",
            "positive_cues": ["probability theory", "random variable", "distribution"],
        },
    ],
}


def domain_names() -> list[str]:
    return [d["name"] for d in DOMAIN_RULES]


def subdomain_names(domain: str | None = None) -> list[str]:
    if domain:
        return [d["name"] for d in SUBDOMAIN_RULES.get(normalize_domain(domain), [])]
    out: list[str] = []
    for rules in SUBDOMAIN_RULES.values():
        out.extend(d["name"] for d in rules)
    return out


def domain_for_subdomain(name: str) -> str:
    """Return the parent domain for a known subdomain name."""
    raw = re.sub(r"\s+", " ", str(name or "")).strip().lower()
    if not raw:
        return ""
    for domain, rules in SUBDOMAIN_RULES.items():
        for rule in rules:
            if rule["name"].lower() == raw:
                return domain
    return ""


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


def subdomain_prompt_block() -> str:
    """Human-readable subdomain taxonomy for the LLM classifier prompt."""
    lines = []
    for domain, rules in SUBDOMAIN_RULES.items():
        items = []
        for rule in rules:
            cues = ", ".join(rule["positive_cues"][:6])
            items.append(f"  - {rule['name']}: cues include {cues}")
        lines.append(f"{domain}:\n" + "\n".join(items))
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


def normalize_subdomain(
    name: str, primary_domain: str | None = None, candidates: list[str] | None = None
) -> str:
    """Return canonical subdomain casing when possible."""
    raw = re.sub(r"\s+", " ", str(name or "")).strip()
    if not raw:
        return ""
    lookup = {d.lower(): d for d in subdomain_names(primary_domain)}
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
                if domain["name"] == "HCI":
                    score += 3
                elif domain["name"] in {"Computer Science", "Statistics"}:
                    score += 3
                else:
                    score += 2
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


def classify_subdomain_heuristic(
    text: str, primary_domain: str, candidates: list[str] | None = None
) -> str:
    """Best-effort subdomain for an already-chosen primary domain."""
    domain = normalize_domain(primary_domain)
    hay = " ".join(str(text or "").lower().split())
    if not hay or not domain:
        return ""
    best, score = _best_subdomain(hay, domain)
    if score < 2:
        return ""
    return normalize_subdomain(best, domain, candidates)


def classify_subdomain_any(text: str) -> tuple[str, str]:
    """Best metadata-derived (domain, subdomain) pair across all domains."""
    hay = " ".join(str(text or "").lower().split())
    if not hay:
        return "", ""
    best_domain = ""
    best_subdomain = ""
    best_score = 0
    for domain in SUBDOMAIN_RULES:
        subdomain, score = _best_subdomain(hay, domain)
        if score > best_score:
            best_domain, best_subdomain, best_score = domain, subdomain, score
    if best_score < 2:
        return "", ""
    return best_domain, best_subdomain


def _best_subdomain(hay: str, domain: str) -> tuple[str, int]:
    rules = SUBDOMAIN_RULES.get(domain, [])
    if not rules:
        return "", 0
    scores: dict[str, int] = {}
    head = hay[:2000]
    for rule in rules:
        score = 0
        if _cue_present(head, rule["name"].lower()):
            score += 20
        for cue in rule["positive_cues"]:
            if _cue_present(head, cue):
                score += 5
            elif _cue_present(hay, cue):
                score += 2
        scores[rule["name"]] = score
    return max(scores.items(), key=lambda kv: (kv[1], kv[0]))


def _cue_present(text: str, cue: str) -> bool:
    """Match cues as words/phrases, not arbitrary substrings."""
    cue = str(cue or "").strip().lower()
    if not cue:
        return False
    parts = [re.escape(part) for part in re.split(r"[\s\-]+", cue) if part]
    if not parts:
        return False
    pattern = r"[\s\-]+".join(parts)
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text) is not None
