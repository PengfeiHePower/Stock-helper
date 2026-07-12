from __future__ import annotations

from typing import Any

_LIKELIHOOD_WEAKEN_DELTA = 0.06
_LIKELIHOOD_INVALIDATE_THRESHOLD = 0.35
_SELECTED_SWITCH_WEAKEN = True


def track_hypothesis_evolution(
    current: dict[str, Any],
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    """Diff hypotheses vs prior snapshot — likelihood moves and new evidence."""
    if not prior or not prior.get("hypotheses"):
        return {
            "has_prior": False,
            "diffs": [],
            "selected_changed": False,
            "summary": "First tracked run — hypothesis deltas start next session.",
        }

    prior_hyps = {
        h["slug"]: h for h in (prior.get("hypotheses") or {}).get("hypotheses") or []
    }
    prior_selected = (prior.get("hypotheses") or {}).get("selected") or {}
    cur_selected = current.get("selected") or {}

    diffs: list[dict[str, Any]] = []
    for h in current.get("hypotheses") or []:
        slug = h["slug"]
        prev = prior_hyps.get(slug)
        if not prev:
            diffs.append(
                {
                    "slug": slug,
                    "label": h["label"],
                    "prior_likelihood": None,
                    "current_likelihood": h["likelihood"],
                    "delta": None,
                    "direction": "new",
                    "newly_supported": h.get("supporting_evidence") or [],
                    "newly_contradicted": h.get("contradicting_evidence") or [],
                }
            )
            continue

        delta = round(
            float(h.get("evidence_score", h.get("likelihood", 0)))
            - float(prev.get("evidence_score", prev.get("likelihood", 0))),
            2,
        )
        if delta > 0.02:
            direction = "up"
        elif delta < -0.02:
            direction = "down"
        else:
            direction = "flat"

        prev_support = set(prev.get("supporting_evidence") or [])
        prev_contra = set(prev.get("contradicting_evidence") or [])
        cur_support = set(h.get("supporting_evidence") or [])
        cur_contra = set(h.get("contradicting_evidence") or [])

        diffs.append(
            {
                "slug": slug,
                "label": h["label"],
                "prior_likelihood": prev.get("evidence_score", prev.get("likelihood")),
                "current_likelihood": h.get("evidence_score", h.get("likelihood")),
                "delta": delta,
                "direction": direction,
                "newly_supported": sorted(cur_support - prev_support),
                "newly_contradicted": sorted(cur_contra - prev_contra),
                "dropped_support": sorted(prev_support - cur_support),
                "resolved_contradictions": sorted(prev_contra - cur_contra),
            }
        )

    selected_changed = prior_selected.get("id") != cur_selected.get("id")
    return {
        "has_prior": True,
        "diffs": diffs,
        "selected_changed": selected_changed,
        "prior_selected": prior_selected,
        "current_selected": cur_selected,
        "summary": _diff_summary(diffs, selected_changed, cur_selected, prior_selected),
    }


def compute_thesis_status(
    hypotheses: dict[str, Any],
    thesis: dict[str, Any],
    prior: dict[str, Any] | None,
    hypothesis_diff: dict[str, Any],
    *,
    uncertainties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    HOLD — selected explanation stable, confidence acceptable.
    WEAKEN — likelihood fell, new contra evidence, or leadership rotated.
    INVALIDATED — dominant explanation collapsed or thesis-breaker risk dominates.
    """
    if not prior or not hypothesis_diff.get("has_prior"):
        return {
            "status": "HOLD",
            "reason": "Baseline session — thesis established for tracking.",
            "prior_confidence": None,
            "current_confidence": thesis.get("overall_confidence"),
            "confidence_delta": None,
        }

    selected = hypotheses.get("selected") or {}
    sel_slug = selected.get("id")
    sel_diff = next(
        (d for d in hypothesis_diff.get("diffs") or [] if d["slug"] == _slug_from_id(sel_slug, hypotheses)),
        None,
    )

    prior_thesis = prior.get("thesis") or {}
    prior_conf = prior_thesis.get("overall_confidence") or prior_thesis.get("derivation_confidence")
    cur_conf = thesis.get("overall_confidence") or thesis.get("derivation_confidence")
    conf_delta = None
    if prior_conf is not None and cur_conf is not None:
        conf_delta = round(float(cur_conf) - float(prior_conf), 2)

    reasons: list[str] = []

    # INVALIDATED checks
    if hypothesis_diff.get("selected_changed"):
        prev_label = (hypothesis_diff.get("prior_selected") or {}).get("label", "prior view")
        new_label = selected.get("label", "new view")
        reasons.append(f"Lead explanation rotated: {prev_label} → {new_label}")

    if sel_diff and sel_diff.get("current_likelihood", 1) < _LIKELIHOOD_INVALIDATE_THRESHOLD:
        reasons.append(
            f"Selected hypothesis likelihood fell to {sel_diff['current_likelihood']} "
            f"(below {_LIKELIHOOD_INVALIDATE_THRESHOLD})"
        )

    if sel_diff and (sel_diff.get("newly_contradicted") or []):
        if len(sel_diff["newly_contradicted"]) >= 2:
            reasons.append("Multiple new contradictions on selected hypothesis")

    headline_prior = (prior_thesis.get("headline") or "")[:80]
    headline_cur = (thesis.get("headline") or "")[:80]
    if headline_prior and headline_cur and _headline_pivot(headline_prior, headline_cur):
        reasons.append("Thesis narrative pivoted materially")

    if len(reasons) >= 2 or (
        hypothesis_diff.get("selected_changed") and sel_diff and (sel_diff.get("delta") or 0) <= -0.1
    ):
        return _status_payload(
            "INVALIDATED",
            reasons,
            prior_conf,
            cur_conf,
            conf_delta,
            selected,
            sel_diff,
        )

    # WEAKEN checks
    weaken_reasons: list[str] = []
    if sel_diff and (sel_diff.get("delta") or 0) <= -_LIKELIHOOD_WEAKEN_DELTA:
        weaken_reasons.append(
            f"{selected.get('label')}: {sel_diff['prior_likelihood']} → "
            f"{sel_diff['current_likelihood']} ({sel_diff['delta']:+.2f})"
        )
    if sel_diff and sel_diff.get("newly_contradicted"):
        weaken_reasons.append(f"New contra: {'; '.join(sel_diff['newly_contradicted'][:2])}")
    if conf_delta is not None and conf_delta <= -0.08:
        weaken_reasons.append(f"Overall confidence {prior_conf} → {cur_conf} ({conf_delta:+.2f})")
    if hypothesis_diff.get("selected_changed") and _SELECTED_SWITCH_WEAKEN:
        weaken_reasons.extend(reasons[:1])
        # Do not treat explanation refinement alone as WEAKEN for reader status
        if len(weaken_reasons) == 1 and "rotated" in weaken_reasons[0]:
            weaken_reasons.clear()

    prior_conflict = (prior.get("conflict") or {}).get("level")
    # conflict not passed here - could add later

    if weaken_reasons:
        return _status_payload(
            "WEAKEN",
            weaken_reasons,
            prior_conf,
            cur_conf,
            conf_delta,
            selected,
            sel_diff,
        )

    hold_note = "Selected explanation stable"
    if sel_diff and sel_diff.get("direction") == "up":
        hold_note += f" — likelihood strengthened ({sel_diff['delta']:+.2f})"
    elif sel_diff and sel_diff.get("newly_supported"):
        hold_note += f" — new support: {sel_diff['newly_supported'][0][:60]}"
    return _status_payload(
        "HOLD",
        [hold_note],
        prior_conf,
        cur_conf,
        conf_delta,
        selected,
        sel_diff,
    )


def _slug_from_id(hid: str | None, hypotheses: dict[str, Any]) -> str | None:
    if not hid:
        return None
    for h in hypotheses.get("hypotheses") or []:
        if h.get("id") == hid:
            return h.get("slug")
    return None


def _headline_pivot(a: str, b: str) -> bool:
    """Rough check if thesis theme changed."""
    keys = ("rate", "rotation", "profit", "idiosyncratic", "concentrat", "ai", "breadth")
    a_set = {k for k in keys if k in a.lower()}
    b_set = {k for k in keys if k in b.lower()}
    return bool(a_set and b_set and a_set != b_set)


def _diff_summary(
    diffs: list[dict[str, Any]],
    selected_changed: bool,
    cur_selected: dict[str, Any],
    prior_selected: dict[str, Any],
) -> str:
    movers = [d for d in diffs if d.get("direction") in ("up", "down")]
    if not movers and not selected_changed:
        return "Hypothesis likelihoods unchanged since last run."
    parts = []
    for d in movers[:3]:
        parts.append(
            f"{d['label']}: {d.get('prior_likelihood')} → {d.get('current_likelihood')} "
            f"({d.get('delta'):+.2f})"
        )
    if selected_changed:
        parts.append(
            f"Selection: {prior_selected.get('label', '—')} → {cur_selected.get('label', '—')}"
        )
    return "; ".join(parts)


def _status_payload(
    status: str,
    reasons: list[str],
    prior_conf: Any,
    cur_conf: Any,
    conf_delta: float | None,
    selected: dict[str, Any],
    sel_diff: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reasons": reasons,
        "prior_confidence": prior_conf,
        "current_confidence": cur_conf,
        "confidence_delta": conf_delta,
        "selected_hypothesis": selected.get("label"),
        "selected_likelihood": sel_diff.get("current_likelihood") if sel_diff else selected.get("confidence"),
        "likelihood_delta": sel_diff.get("delta") if sel_diff else None,
    }
