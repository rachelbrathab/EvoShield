"""Prediction engine domain (Sprint 7+).

Owns future-risk estimation: feature engineering, model training/evaluation
(pandas, NumPy, scikit-learn), and 90-day risk forecasts with confidence
intervals.

Dependency rule: consumes intelligence features; produces predictions
consumed by the recommendation and reports domains.
"""
