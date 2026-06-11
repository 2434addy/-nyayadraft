"""Template selection, filling, and the unfilled-placeholder guard.

A meta-prompt template is a ``.txt`` file in ``meta_prompts/`` containing
``<<PLACEHOLDER>>`` markers. ``render_prompt`` selects the right template for a
spec, substitutes every marker from the spec + variation, and then enforces the
*unfilled-placeholder guard*: if any ``<<...>>`` marker survives substitution
the function raises rather than letting an unfilled placeholder leak into a
prompt sent to the model.

This mirrors the project-wide placeholder discipline: ``[PLACEHOLDER]`` markers
for withheld facts are intentional and must reach the model verbatim, but the
template's own ``<<...>>`` markers must always be resolved.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

# Default location of the meta-prompt templates, resolved relative to this file
# so the module works regardless of the caller's working directory.
DEFAULT_META_DIR = Path(__file__).resolve().parent / "meta_prompts"

# Template discriminator -> template file name. ``base`` is the implicit
# default when a spec declares no ``template`` key.
TEMPLATE_FILES = {
    "base": "base.txt",
    "out_of_scope": "base_out_of_scope.txt",
}
DEFAULT_TEMPLATE = "base"

# Marker syntax: <<UPPER_SNAKE_NAME>>.
_PLACEHOLDER_RE = re.compile(r"<<\s*([A-Z0-9_]+)\s*>>")

# Doc type that must never be offered as a "supported" type in refusals.
_OUT_OF_SCOPE_DOC_TYPE = "out_of_scope"

# Literal rendered when an optional value is absent.
_NONE_LITERAL = "none"


class PromptRenderError(RuntimeError):
    """Raised when a prompt cannot be rendered safely.

    Covers unknown template names, missing template files, missing required
    context (such as ``display_names`` for refusals), and any template
    placeholder that survived substitution.
    """


def render_prompt(
    spec: Mapping[str, Any],
    variation: Mapping[str, Any],
    system_prompt: str,
    *,
    meta_dir: Path | str | None = None,
    display_names: Mapping[str, str] | None = None,
) -> str:
    """Render the meta-prompt for one spec + variation.

    Args:
        spec: The document-type spec (``doc_type``, ``template``, ...).
        variation: A variation produced by ``variation.build_variation``.
        system_prompt: The drafting model's system prompt, embedded verbatim.
        meta_dir: Directory holding template files; defaults to the bundled
            ``meta_prompts`` directory.
        display_names: Map of ``doc_type`` -> human display name; required for
            out-of-scope refusals which enumerate the supported types.

    Returns:
        The fully substituted prompt text.

    Raises:
        PromptRenderError: On unknown/missing templates, missing required
            context, or any unfilled ``<<...>>`` placeholder.
    """
    directory = Path(meta_dir) if meta_dir is not None else DEFAULT_META_DIR
    template_name = spec.get("template", DEFAULT_TEMPLATE)
    template_text = _load_template(template_name, directory)

    if template_name == "out_of_scope":
        substitutions = _out_of_scope_substitutions(
            spec, variation, system_prompt, display_names
        )
    else:
        substitutions = _base_substitutions(
            spec, variation, system_prompt, display_names
        )

    rendered = _substitute(template_text, substitutions)
    _assert_no_unfilled(rendered)
    return rendered


def _load_template(template_name: str, directory: Path) -> str:
    """Resolve and read a template file, raising on unknown or missing files."""
    file_name = TEMPLATE_FILES.get(template_name)
    if file_name is None:
        raise PromptRenderError(f"unknown template name {template_name!r}")
    path = directory / file_name
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptRenderError(
            f"template file {file_name!r} not found in {directory}"
        ) from exc


def _base_substitutions(
    spec: Mapping[str, Any],
    variation: Mapping[str, Any],
    system_prompt: str,
    display_names: Mapping[str, str] | None,
) -> dict[str, str]:
    """Build the substitution map for the standard document template."""
    return {
        "DOC_TYPE_NAME": _doc_type_name(spec, display_names),
        "STRUCTURAL_SUMMARY": str(spec.get("structural_summary", "")),
        "SCENARIO_CONTEXT": str(variation.get("scenario_summary", "")),
        "GIVEN_FACTS_JSON": _given_facts_json(variation),
        "WITHHELD_FIELDS": _withheld_block(variation),
        "REGISTER": str(variation.get("register", "")),
        "STATUTORY_REQUIREMENTS": str(spec.get("statutory_requirements", "")),
        "SYSTEM_PROMPT": system_prompt,
    }


def _out_of_scope_substitutions(
    spec: Mapping[str, Any],
    variation: Mapping[str, Any],
    system_prompt: str,
    display_names: Mapping[str, str] | None,
) -> dict[str, str]:
    """Build the substitution map for the refusal template."""
    if not display_names:
        raise PromptRenderError(
            "display_names is required to render an out_of_scope prompt"
        )
    return {
        "SUPPORTED_TYPES": _supported_types_block(display_names),
        "SCENARIO_CONTEXT": str(variation.get("scenario_summary", "")),
        "NEAREST_SUPPORTED": _nearest_supported_name(variation, display_names),
        "GIVEN_FACTS_JSON": _given_facts_json(variation),
        "REGISTER": str(variation.get("register", "")),
        "SYSTEM_PROMPT": system_prompt,
    }


def _doc_type_name(
    spec: Mapping[str, Any], display_names: Mapping[str, str] | None
) -> str:
    """Prefer the caller-supplied display name, else the spec's own."""
    doc_type = spec.get("doc_type")
    if display_names and doc_type in display_names:
        return display_names[doc_type]
    return str(spec.get("display_name", doc_type or ""))


def _given_facts_json(variation: Mapping[str, Any]) -> str:
    """Serialise given facts as human-readable UTF-8 JSON (₹ stays as ₹)."""
    facts = variation.get("given_facts") or {}
    return json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True)


def _withheld_block(variation: Mapping[str, Any]) -> str:
    """Render withheld fields as ``- name: [PLACEHOLDER]`` lines, or a note."""
    withheld = variation.get("withheld_fields") or []
    if not withheld:
        return "(none — every relevant detail was provided)"
    lines = [
        f"- {field['name']}: {field['placeholder']}" for field in withheld
    ]
    return "\n".join(lines)


def _supported_types_block(display_names: Mapping[str, str]) -> str:
    """List supported document display names, excluding out_of_scope."""
    lines = [
        f"- {name}"
        for doc_type, name in display_names.items()
        if doc_type != _OUT_OF_SCOPE_DOC_TYPE
    ]
    return "\n".join(lines)


def _nearest_supported_name(
    variation: Mapping[str, Any], display_names: Mapping[str, str]
) -> str:
    """Resolve nearest_supported to a display name, or the literal ``none``."""
    nearest = variation.get("nearest_supported")
    if not nearest:
        return _NONE_LITERAL
    return display_names.get(nearest, str(nearest))


def _substitute(template: str, substitutions: Mapping[str, str]) -> str:
    """Replace each known ``<<KEY>>`` with its value in a single pass.

    Unknown markers are deliberately left untouched so the guard can report
    them; replacement values are inserted literally and never re-scanned.
    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in substitutions:
            return substitutions[key]
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, template)


def _assert_no_unfilled(rendered: str) -> None:
    """Raise if any ``<<...>>`` placeholder remains after substitution."""
    leftovers = _PLACEHOLDER_RE.findall(rendered)
    if leftovers:
        unique = ", ".join(dict.fromkeys(leftovers))
        raise PromptRenderError(
            f"unfilled template placeholder(s): {unique}"
        )
