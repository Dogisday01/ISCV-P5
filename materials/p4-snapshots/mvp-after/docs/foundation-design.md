# Universal MVP foundation

## Structural diagram

```mermaid
flowchart LR
    Client["User / Staff / Admin"] --> API["FastAPI API"]
    API --> Auth["Auth + RBAC"]
    API --> Workflow["WorkflowItem service"]
    API --> Audit["Audit service"]
    Auth --> DB[(Database)]
    Workflow --> DB
    Audit --> DB
```

## Reusable business flow

```mermaid
flowchart TD
    Start["Authenticated user"] --> Create["Create workflow item"]
    Create --> Validate["Validate input and ownership context"]
    Validate --> Save["Store item in DB"]
    Save --> AuditCreate["Write audit record"]
    AuditCreate --> Review["Staff reviews item"]
    Review --> Decision{"Allowed transition?"}
    Decision -- Yes --> Update["Update status"]
    Update --> AuditStatus["Write audit record"]
    Decision -- No --> Reject["Return 403/409"]
```

## Data model

- `users`
  - identities, password hash, role, lockout state
- `workflow_items`
  - core business object with owner, assignee, status, optional amount and payload
- `refresh_tokens`
  - hashed refresh tokens, rotation, expiry, revocation
- `audit_logs`
  - security-relevant action history without secrets

## Security controls already included

- input validation with Pydantic
- server-side RBAC and object-level checks
- hashed passwords with Argon2/Bcrypt support
- short-lived access tokens
- refresh-token rotation and revocation
- neutral error messages for auth failures
- audit logging for critical actions
- request size guard
- secrets from environment instead of source code
- dependency and static analysis tooling
