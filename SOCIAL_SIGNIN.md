# Social sign-in setup

Google, Apple and Microsoft sign-up/sign-in use OpenID Connect through Authlib.
The same button creates a new account on first use and signs in on later use.
These integrations are implemented and tested with mocked provider endpoints;
live provider consent is not verified until you supply registered app credentials.
No developer subscription or provider project has been purchased or created.

## Prerequisites

1. Connect the lasting Neon or Supabase PostgreSQL database as `DATABASE_URL`
   in the existing Render service's Environment settings.
2. Set `PUBLIC_BASE_URL=https://reasoning-studio.onrender.com`. If you change
   domain later, update this and each provider's allowed callback URL.
3. Configure a random `OAUTH_SESSION_SECRET` of at least 32 characters. The
   deployment setup can generate this without exposing it. Keep it stable across
   deployments so pending sign-ins can complete. Do not put secrets in Git/chat.
4. Add the credentials for each provider below in Render and save/redeploy.
   Each button remains disabled until both its provider configuration and
   database configuration exist. Guest practice never requires social sign-in.

## Google

In [Google Auth Platform](https://console.cloud.google.com/auth/clients), create
an OAuth client of type **Web application**. Configure the app name, audience and
any testing users required for your app's publishing status. Use:

- Authorized JavaScript origin: `https://reasoning-studio.onrender.com`
- Authorized redirect URI:
  `https://reasoning-studio.onrender.com/api/account/oauth/google/callback`
- Render secrets: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`

The server requests `openid profile`. It does not request offline access or
keep Google access/refresh tokens. Registration does not require a paid compute
service, but review Google's current terms in your account.

## Apple

Apple requires access to its developer identifiers and a primary App ID enabled
for Sign in with Apple. This can require Apple Developer Program membership;
we do not buy or enroll in anything automatically. Configure a web **Services ID**,
associate the domain and callback, then create a Sign in with Apple private key.

- Domain: `reasoning-studio.onrender.com`
- Return URL:
  `https://reasoning-studio.onrender.com/api/account/oauth/apple/callback`
- Render secrets: `APPLE_CLIENT_ID` (Services ID), `APPLE_TEAM_ID`,
  `APPLE_KEY_ID`, and `APPLE_PRIVATE_KEY` (the `.p8` PEM contents)

The app generates a short-lived ES256 client-secret JWT when needed; you do not
have to manually renew a stored six-month JWT. PEM newlines may be real newlines
or literal `\n` sequences. Apple supplies the person's name only on first consent;
that optional form field is used only as a display hint, never proof of identity.

Apple uses a cross-site `form_post` callback. The dedicated OAuth-state cookie is
Secure/HttpOnly/SameSite=None on Render so that callback can carry state. The
main account session cookie remains Secure/HttpOnly/SameSite=Lax. Local HTTP
uses Lax for development; test a real Apple flow on the registered HTTPS domain.

## Microsoft

In [Microsoft Entra app registrations](https://entra.microsoft.com/), create a
Web application. Choose the supported account types you intend to accept and
add this Web redirect URI:

`https://reasoning-studio.onrender.com/api/account/oauth/microsoft/callback`

Set Render secrets `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` (the secret
**value**, not its ID). Optional `MICROSOFT_TENANT_ID` defaults to `common` for
personal and work/school accounts. Use `organizations`, `consumers`, or a specific
tenant UUID to restrict it; the app registration must support the same audience.

The server validates each signed token's issuer against its tenant, and identities
are scoped by provider + issuer + subject so different tenants cannot collide.
No Microsoft Graph permissions, email scope, or offline access are requested.

## Behavior and security

- Authlib validates state, nonce, signature, audience, issuer and expiry. Google
  and Microsoft additionally use PKCE S256. Apple uses its confidential-client
  code exchange and nonce checks.
- Provider/issuer/subject identify an account. Accounts are **not** automatically
  merged by email; username and social accounts remain separate until an explicit
  account-linking feature is implemented. Keep using the same sign-in method.
- The popup returns only a success/error status to the exact application origin.
  The parent checks its origin and window source before refreshing account state.
  Provider tokens never appear in that message or in app URLs/storage.
- Sign-in preserves the working tab's draft, practice answers and manually
  entered Anthropic key. If the browser blocks popups, the app asks you to allow
  the popup instead of navigating away from unsaved work.
- OAuth query codes/state are redacted from Uvicorn access logs. Temporary OAuth
  state is cleared at callback. Provider tokens and email addresses are not saved.
- Account sessions are opaque random tokens, stored only as hashes in PostgreSQL.
  The previous browser token is revoked when a new account session is issued.

## Sources

- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Apple web configuration](https://developer.apple.com/help/account/capabilities/configure-sign-in-with-apple-for-the-web/)
- [Apple private keys](https://developer.apple.com/help/account/keys/create-a-private-key/)
- [Microsoft OpenID Connect](https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc)
- Provider discovery metadata: Google, `https://appleid.apple.com/.well-known/openid-configuration`,
  and `https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration`.

## Verification

`tests/test_social_auth.py` exercises the real Authlib client and JWT verification
against mocked metadata/token/JWKS endpoints, including forged state, nonce,
audience, issuer and expired-token failures, Apple form-post, repeated sign-in,
Microsoft tenant isolation, and no email-based linking. Browser checks exercise
a simulated provider popup plus preservation of the current work. These are not
a claim of a completed real Google/Apple/Microsoft consent flow.
