"""Deterministic remediation guidance — rule-based finding explanations.

Each finding type has a guidance provider that produces:
- A safe explanation (why this matters)
- Remediation steps (what to do)
- Fix availability assessment

All guidance is deterministic. No LLM, no ML, no prediction.
"""

from __future__ import annotations

from app.domains.remediation.enums import FixAvailability


def assess_fix_availability(
    *,
    finding_type: str,
    fixed_version: str | None,
    vulnerability_id: str | None,
    installed_version: str | None,
) -> FixAvailability:
    """Determine fix availability from normalized finding fields."""
    if finding_type == "secret":
        return FixAvailability.NOT_APPLICABLE
    if finding_type in ("license", "configuration"):
        return FixAvailability.UNKNOWN
    if fixed_version:
        return FixAvailability.FIX_AVAILABLE
    if vulnerability_id:
        return FixAvailability.NO_KNOWN_FIX
    return FixAvailability.UNKNOWN


def get_remediation_guidance(
    *,
    finding_type: str,
    scanner: str,
    title: str,
    description: str | None,
    package_name: str | None,
    installed_version: str | None,
    fixed_version: str | None,
    vulnerability_id: str | None,
    location: str | None,
) -> dict:
    """Return deterministic remediation guidance for a finding.

    Returns a dict with keys:
        summary: str       — why this matters
        recommendation: str — what to do
        steps: list[str]   — ordered remediation steps
    """
    if finding_type == "secret":
        return _secret_guidance()
    if finding_type == "vulnerability":
        return _vulnerability_guidance(
            package_name=package_name,
            installed_version=installed_version,
            fixed_version=fixed_version,
            vulnerability_id=vulnerability_id,
            description=description,
        )
    if finding_type == "sast":
        return _sast_guidance(
            title=title,
            description=description,
            location=location,
        )
    if finding_type == "license":
        return _license_guidance(
            package_name=package_name,
            description=description,
        )
    if finding_type == "configuration":
        return _configuration_guidance(
            title=title,
            description=description,
        )
    return _generic_guidance()


def _secret_guidance() -> dict:
    return {
        "summary": (
            "A potential secret or credential was detected in the "
            "repository. Exposed secrets can lead to unauthorized access, "
            "data breaches, and compromised systems."
        ),
        "recommendation": (
            "Revoke the credential immediately, remove it from the "
            "repository, and migrate to a secure secret-management solution."
        ),
        "steps": [
            "Revoke or rotate the detected credential immediately.",
            "Remove the secret from the repository code and git history.",
            "Check for unauthorized access using the exposed credential.",
            "Store future credentials using a secure secret-management "
            "mechanism (e.g., environment variables, vault, sealed secrets).",
            "Add pre-commit hooks to prevent future secret exposure.",
        ],
    }


def _vulnerability_guidance(
    *,
    package_name: str | None,
    installed_version: str | None,
    fixed_version: str | None,
    vulnerability_id: str | None,
    description: str | None,
) -> dict:
    parts: list[str] = []
    if package_name:
        parts.append(f"The dependency '{package_name}'")
    else:
        parts.append("A dependency")
    if installed_version and fixed_version:
        parts.append(
            f" version {installed_version} has a known vulnerability "
            f"that is fixed in version {fixed_version}."
        )
    elif installed_version:
        parts.append(f" version {installed_version} has a known vulnerability.")
    else:
        parts.append(" has a known vulnerability.")
    if vulnerability_id:
        parts.append(f" Tracked as {vulnerability_id}.")

    summary = "".join(parts)
    if description:
        summary += f" {description}"

    steps: list[str] = []
    if fixed_version and package_name:
        steps.append(f"Upgrade {package_name} to version {fixed_version} or later.")
    elif package_name:
        steps.append(f"Check for available updates for {package_name}.")
    else:
        steps.append("Identify and upgrade the affected dependency.")

    steps.append("Verify the upgrade does not introduce regressions.")
    steps.append("Review the vulnerability advisory for additional context.")

    recommendation = steps[0]

    return {
        "summary": summary,
        "recommendation": recommendation,
        "steps": steps,
    }


def _sast_guidance(
    *,
    title: str,
    description: str | None,
    location: str | None,
) -> dict:
    summary = f"A static analysis finding was detected: {title}."
    if description:
        summary += f" {description}"
    if location:
        summary += f" Found in {location}."

    return {
        "summary": summary,
        "recommendation": (
            "Review the flagged code pattern and apply the recommended "
            "security fix. Consult the scanner rule documentation for "
            "detailed remediation guidance."
        ),
        "steps": [
            "Review the flagged code location and understand the issue.",
            "Apply the recommended fix or an equivalent secure pattern.",
            "Verify the fix resolves the finding without side effects.",
            "Consider adding automated checks to prevent recurrence.",
        ],
    }


def _license_guidance(
    *,
    package_name: str | None,
    description: str | None,
) -> dict:
    pkg = package_name or "A dependency"
    summary = f"{pkg} has a license concern."
    if description:
        summary += f" {description}"

    return {
        "summary": summary,
        "recommendation": (
            "Review the license terms for compliance with your "
            "organization's policies. Consider replacing with a "
            "dual-licensed or permissively-licensed alternative if needed."
        ),
        "steps": [
            "Review the license type and terms for the flagged package.",
            "Verify compliance with your organization's licensing policy.",
            "Consider alternative packages with compatible licenses if needed.",
        ],
    }


def _configuration_guidance(
    *,
    title: str,
    description: str | None,
) -> dict:
    summary = f"A configuration issue was detected: {title}."
    if description:
        summary += f" {description}"

    return {
        "summary": summary,
        "recommendation": (
            "Review the flagged configuration and apply the recommended security hardening."
        ),
        "steps": [
            "Review the flagged configuration setting.",
            "Apply the recommended secure configuration.",
            "Verify the change does not break application functionality.",
        ],
    }


def _generic_guidance() -> dict:
    return {
        "summary": (
            "A security finding was detected. Review the finding "
            "details and consult the scanner documentation for "
            "recommended remediation."
        ),
        "recommendation": (
            "Review the finding details and apply appropriate "
            "remediation based on the scanner's recommendations."
        ),
        "steps": [
            "Review the finding details and affected code/dependency.",
            "Consult the scanner documentation for remediation guidance.",
            "Apply the recommended fix and verify the resolution.",
        ],
    }
