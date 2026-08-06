"""Repository intelligence domain (Sprint 6+).

Owns temporal repository intelligence: how risk drifts over time, trend
features, and the historical dataset the prediction engine trains on.

Dependency rule: consumes scanner findings over time; produces feature
vectors consumed by the prediction domain. Named `intelligence` (not
`repository_intelligence`) to avoid collision with the data-access
`repositories/` layer.
"""
