# Notifications

The browser service worker accepts Web Push payloads with a title, body, stable tag, and same-origin
deep link. Onboarding requests permission only after a user gesture, registers through PushManager,
and sends the subscription to the profile-scoped API. Endpoints are indexed only by SHA-256; the
full subscription is encrypted with a dedicated Fernet key or a key derived from the session pepper.

The tracker persists a uniquely constrained delivery intent before side effects. The dispatcher
uses environment-provided VAPID keys, bounds retries, disables HTTP 404/410 subscriptions, records
delivery status, respects location quiet hours and cooldowns, and never creates intents from stale
observations. A user-facing test button exercises the same persisted delivery path. Payloads include
flight facts and an Airspace deep link but never coordinates, endpoints, or encryption keys.
