"""Small escaped HTML components for the Streamlit presentation layer."""

from __future__ import annotations

from html import escape


def shirt_svg(color: str, initial: str, keeper: bool = False, secondary: str = "#ffffff", pattern: str = "solid", shirt_id: str = "shirt") -> str:
    """Return a real inline T-shirt silhouette with a clipped kit pattern."""
    primary = escape(str(color), quote=True)
    accent = escape(str(secondary), quote=True)
    letter = escape(str(initial)[:1].upper())
    clip_id = "shirt-" + "".join(ch for ch in str(shirt_id) if ch.isalnum())
    body = "M30 8 L10 20 L2 42 L18 48 L22 38 L22 92 L78 92 L78 38 L82 48 L98 42 L90 20 L70 8 C66 15 58 19 50 19 C42 19 34 15 30 8 Z"
    if pattern == "stripes":
        layer = f'<path d="M22 8h56v84H22z" fill="{accent}"/><path d="M34 8h10v84H34zM56 8h10v84H56z" fill="{primary}"/>'
    elif pattern == "hoops":
        layer = f'<path d="M18 28h64v12H18zM18 53h64v12H18z" fill="{accent}"/>'
    elif pattern == "halves":
        layer = f'<path d="M50 8h40v84H50z" fill="{accent}"/>'
    elif pattern == "sash":
        layer = f'<path d="M14 10h16l58 76-12 8z" fill="{accent}"/>'
    else:
        layer = ""
    keeper_mark = '<circle cx="14" cy="16" r="5" fill="#22D3EE"/>' if keeper else ""
    return (f'<svg viewBox="0 0 100 100" aria-hidden="true"><defs><clipPath id="{clip_id}"><path d="{body}"/></clipPath></defs>'
            f'<path d="{body}" fill="{primary}"/><g clip-path="url(#{clip_id})">{layer}</g>'
            f'<path d="M2 42 18 48M82 48 98 42" stroke="{accent}" stroke-width="4"/>'
            f'<path d="M30 8 C34 15 42 19 50 19 C58 19 66 15 70 8" fill="none" stroke="{accent}" stroke-width="4"/>'
            f'<text x="50" y="61" text-anchor="middle" font-size="20" font-weight="800" fill="#F2F7FF">{letter}</text>{keeper_mark}</svg>')


def name_plate(name: str, subtitle: str = "") -> str:
    return f'<div class="name-plate"><strong>{escape(str(name))}</strong><small>{escape(str(subtitle))}</small></div>'


def keeper_badge() -> str:
    """Return a small inline gloves badge."""
    return '<span class="keeper-badge" title="Goalkeeper"><svg viewBox="0 0 24 20" aria-hidden="true"><path d="M5 18 2 9l4-3 3 5 1-8 3 1 1 7 2-6 3 2-2 9-5 3z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg> GK</span>'


def chip(text: str, tone: str = "default") -> str:
    safe_tone = escape(str(tone), quote=True)
    return f'<span class="ui-chip {safe_tone}">{escape(str(text))}</span>'


def stat_card(label: str, value: str, caption: str = "", tone: str = "default") -> str:
    return f'<div class="stat-card {escape(str(tone), quote=True)}"><small>{escape(str(label))}</small><strong>{escape(str(value))}</strong><span>{escape(str(caption))}</span></div>'


def progress_ring(percent: float, label: str) -> str:
    bounded = max(0, min(100, float(percent)))
    return f'<div class="progress-ring" style="--progress:{bounded}%"><strong>{bounded:.0f}%</strong><span>{escape(str(label))}</span></div>'


def section_header(kicker: str, title: str, subtitle: str) -> str:
    return f'<div class="section-title"><span class="step-marker">{escape(str(kicker))}</span><h2>{escape(str(title))}</h2><p>{escape(str(subtitle))}</p></div>'


def crest_svg(team_name: str, primary: str, secondary: str, pattern: str = "stripe") -> str:
    initials = "".join(word[:1] for word in str(team_name).split())[:2].upper()
    a, b = escape(primary, quote=True), escape(secondary, quote=True)
    art = '<path d="M10 8v35M20 6v40M30 6v40M40 8v35" stroke="#fff" stroke-width="5" opacity=".45"/>'
    if pattern == "chevron": art = '<path d="M7 19 27 34 47 19" fill="none" stroke="#fff" stroke-width="3"/>'
    if pattern == "star": art = '<path d="m27 9 3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1z" fill="#fff8"/>'
    return f'<svg viewBox="0 0 54 62" aria-label="{escape(team_name)} crest"><path d="M5 6h44v27c0 13-10 22-22 26C15 55 5 46 5 33z" fill="{a}" stroke="{b}" stroke-width="3"/>{art}<text x="27" y="39" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{escape(initials)}</text></svg>'


