"""Business domains — one package per domain of the DevSecOps platform.

Each domain owns its business logic, schemas, and (as sprints land) its
repositories. The dependency rules are strict:

- Domains depend only on shared infrastructure (`core`, `db`, `models`,
  `utils`) and never on each other.
- Cross-domain orchestration (GitHub → analysis → scanners → intelligence →
  prediction → recommendation → reports) lives in the API/worker layer, never
  inside a domain.
- The `health` domain is the reference implementation of this pattern.
"""
