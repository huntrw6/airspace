# AirSpace PWA installation verification

## Automated and local checks

- Platform, installed-mode, storage, native-event, and prompt component tests: completed.
- Production TypeScript/Vite build: completed.
- Manifest JSON fields and icon references: completed.
- Service-worker JavaScript syntax: completed.
- Approved icon dimensions and alpha-capable PNG formats: completed.
- HTTPS, browser install UI, and operating-system notification behavior: require the deployed site.

## Manual browser matrix

| Environment | Check | Status |
| --- | --- | --- |
| iPhone Safari tab | Original menu → Share → Add to Home Screen guide; no fake native button | Physical device required |
| iPhone Home Screen app | Install prompt hidden; notification action available | Physical device required |
| iPad Safari | iPad and desktop-style iPad detection | Physical device required |
| Android Chrome | Real captured native prompt; notification permission remains separate | Physical device required |
| Android without install event | Browser-menu fallback; no fake Install button | Device/browser required |
| Windows Chrome/Edge | Native install event and one-use prompt | Deployed browser required |
| macOS Chrome/Edge | Native install event and one-use prompt | Deployed browser required |
| macOS Safari | No broken native action; Settings information remains available | Deployed browser required |
| Embedded browser | Open-in-browser guidance, Copy link, and Web Share when available | Device/app required |

## iPhone verification

1. Open the deployed HTTPS AirSpace URL in Safari, not from the Home Screen.
2. Complete location setup or open **Privacy and profile settings** and choose **Install AirSpace**.
3. Confirm the guide shows the ··· menu, Share, Add to Home Screen, Add, and the AirSpace icon.
4. Dismiss it and reload; confirm it stays hidden for the cooldown period.
5. Open Settings and choose **Install AirSpace** again; confirm this bypasses the cooldown.
6. Follow the guide, add AirSpace, and launch it from the new Home Screen icon.
7. Confirm **Use my current location** can request location from the installed app.
8. Confirm the installation prompt is absent and choose **Enable Plane Notifications**.
9. Grant permission from that user gesture and send a test notification from Settings.

## Android verification

1. Open the deployed HTTPS AirSpace URL in Chrome and complete location setup.
2. On the dashboard, wait for the AirSpace install card.
3. Confirm **Install AirSpace** appears only when Chrome supplied its native install event.
4. Tap it and confirm Chrome’s real installation dialog opens exactly once.
5. Dismiss the browser dialog; reload and confirm the seven-day cooldown is respected.
6. Use **Privacy and profile settings → Install AirSpace** to bypass the cooldown.
7. Accept installation and confirm the AirSpace card closes and stays hidden in the installed app.
8. Separately choose **Enable Plane Notifications**, grant permission, and send a test notification.
