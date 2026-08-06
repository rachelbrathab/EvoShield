"""Identity domain — authentication, sessions and user profiles.

Owns registration, login, logout, token verification and profile
provisioning. Depends on the `AuthProvider` port, never on a concrete
provider; orchestration lives in `IdentityService`.

Dependency rule: consumes the auth provider port and the users table;
produces the authenticated session used by every other domain.
"""
