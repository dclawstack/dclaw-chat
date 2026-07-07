# ADR 0001: Per-workspace SSO via Logto enterprise connectors

- **Status:** Accepted
- **Date:** 2026-07-07
- **Issue:** [#28](https://github.com/dclawstack/dclaw-chat/issues/28)

## Context

Enterprise customers need their members to sign in through their own IdP
(Okta, Microsoft Entra, Google Workspace), configured per workspace. The
backend already delegates authentication to Logto: it verifies Logto-issued
RS256 JWTs against a JWKS endpoint and never handles credentials itself. A
standing constraint is that the product is self-hosted — the backend never
deploys to cloud — so any auth component must be self-hostable too.

Options considered:

1. **Logto enterprise SSO connectors** — keep Logto as the auth front door;
   use its built-in enterprise SSO (SAML/OIDC connectors) and organizations,
   mapping one workspace to one Logto organization.
2. **Direct OIDC/SAML in the backend** — the app owns the IdP handshake:
   SAML metadata exchange, certificate rotation, clock-skew handling, and the
   ongoing CVE exposure of hand-rolled SAML.
3. **Migrate to Keycloak/Dex** — a mature self-hostable broker, but requires
   migrating every existing Logto auth flow for capabilities Logto already
   provides.

## Decision

Adopt **option 1: Logto enterprise SSO connectors**.

- Logto remains the only component that talks to IdPs; the backend keeps its
  existing trust model (verify Logto JWTs via JWKS) unchanged.
- Each workspace maps to a Logto organization. A workspace admin registers
  their IdP (SAML or OIDC connector) against that organization.
- Logto is open source and self-hostable, so the deployment story stays
  consistent with the local-first constraint.

## Consequences

- App-side work is limited to the workspace ↔ Logto organization mapping and
  admin UX for initiating IdP setup — no new protocol surface in the backend.
- We take a dependency on Logto's enterprise-SSO feature being available in
  the self-hosted OSS edition we ship. **Verifying this is the first step of
  the implementation issue; if it turns out to be cloud-only or paywalled,
  the recorded fallback is option 3 (Keycloak), not option 2.**
- SCIM provisioning (#31) builds on the same workspace-organization mapping.
- Hand-rolled SAML in the backend (option 2) is explicitly rejected: the
  security surface is not worth owning at this team size.
