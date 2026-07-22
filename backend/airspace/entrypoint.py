"""Prepare persistent runtime secrets, then replace this process with Uvicorn."""

import json
import os
from pathlib import Path

from .generate_vapid import encoded_key_pair

DEFAULT_KEY_FILE = Path("/app/data/vapid-keys.json")


def ensure_vapid_keys(key_file: Path | None = None) -> tuple[str, str]:
    public = os.environ.get("AIRSPACE_VAPID_PUBLIC_KEY", "").strip()
    private = os.environ.get("AIRSPACE_VAPID_PRIVATE_KEY", "").strip()
    if bool(public) != bool(private):
        raise RuntimeError(
            "Set both AIRSPACE_VAPID_PUBLIC_KEY and AIRSPACE_VAPID_PRIVATE_KEY, or neither."
        )
    if public and private:
        return public, private

    path = key_file or Path(os.environ.get("AIRSPACE_VAPID_KEY_FILE", DEFAULT_KEY_FILE))
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        public, private = str(payload["public_key"]), str(payload["private_key"])
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        public, private = encoded_key_pair()
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"public_key": public, "private_key": private}), encoding="utf-8"
        )
        temporary.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)

    os.environ["AIRSPACE_VAPID_PUBLIC_KEY"] = public
    os.environ["AIRSPACE_VAPID_PRIVATE_KEY"] = private
    return public, private


def main() -> None:
    ensure_vapid_keys()
    os.execvp(
        "uvicorn",
        ["uvicorn", "airspace.main:app", "--host", "0.0.0.0", "--port", "7373"],
    )


if __name__ == "__main__":
    main()
