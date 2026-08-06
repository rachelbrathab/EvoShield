"""Shared Pydantic schemas (request/response contracts).

Domain-specific schemas live with their owning domain in
`app/domains/<domain>/schemas.py`. This package holds only contracts shared
across multiple domains (e.g. a unified `Finding` once scanners land).
"""
