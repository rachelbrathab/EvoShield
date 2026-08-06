"""Data-access layer — repositories isolate SQL from business logic.

Repositories are per-domain aggregates, e.g. `app/domains/<domain>/repository.py`
when a domain needs persistence, or shared here when several domains read the
same table. Models in `app/models/` are the only ORM schema; repositories the
only query surface.
"""
