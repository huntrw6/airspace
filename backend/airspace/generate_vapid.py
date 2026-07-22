"""Print a new VAPID key pair without writing secret files."""

import base64

from cryptography.hazmat.primitives.asymmetric import ec


def encoded_key_pair() -> tuple[str, str]:
    private = ec.generate_private_key(ec.SECP256R1())
    private_number = private.private_numbers().private_value.to_bytes(32, "big")
    public = private.public_key().public_numbers()
    public_bytes = b"\x04" + public.x.to_bytes(32, "big") + public.y.to_bytes(32, "big")

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    return encode(public_bytes), encode(private_number)


if __name__ == "__main__":
    public_key, private_key = encoded_key_pair()
    print(f"AIRSPACE_VAPID_PUBLIC_KEY={public_key}")
    print(f"AIRSPACE_VAPID_PRIVATE_KEY={private_key}")
