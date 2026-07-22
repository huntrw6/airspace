# Security

Input models bound coordinates, radii, bearings, FOV, altitude, labels, and cooldowns. Sessions use
keyed hashes and protected cookies; admin endpoints use constant-time credential comparison and
should also be proxy-restricted. Responses include CSP, frame denial, MIME sniffing prevention,
referrer and permissions policies. SQLAlchemy parameterizes database access. Secrets are environment
only and `.env`/database files are ignored. Remaining hardening: CSRF tokens for unsafe cookie-auth
requests, durable rate limiting, encryption-at-rest for push material, admin credential hashing/UI,
trusted-proxy allow-listing, dependency audit, and a formal threat-model review before public launch.
Unsafe browser requests with a supplied `Origin` are rejected unless its authority matches the
configured public URL. Push subscription JSON is encrypted at rest and sensitive values are absent
from notification payloads and provider diagnostics.
