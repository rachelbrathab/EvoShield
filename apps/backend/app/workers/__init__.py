"""Background workers (Sprint 5+).

Home for long-running, cross-domain pipelines that must not block the
request path — e.g. scan orchestration, intelligence rollups, prediction
runs. Workers compose domains; domains never call workers.

Until a dedicated worker process exists, this package hosts the pipeline
functions that API routers dispatch to background tasks.
"""
