# Anonymous profiles

The raw 48-byte random session token is sent only in a Secure, HttpOnly, SameSite=Lax cookie. The
database stores an HMAC-SHA256 value keyed by the server session pepper. Public IDs cannot be used
to authenticate. Every location, sighting, and subscription query is scoped through the resolved
profile. There is intentionally no recovery, email, magic link, QR transfer, or device linking.
