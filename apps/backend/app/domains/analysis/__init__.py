"""Repository analysis domain (Sprint 4+).

Owns repository-level analysis: structure, metadata, dependency manifests
and the inputs the scanner engine consumes.

Dependency rule: receives normalized repository data from the GitHub domain
(via orchestration) and hands analysis artifacts to the scanners domain.
"""
