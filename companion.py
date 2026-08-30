"""Authentication primitives shared by the optional owned-server companion."""
import hashlib
import hmac


class TokenStore:
    def __init__(self, digest):
        self.digest = digest

    @classmethod
    def from_token(cls, token):
        return cls(hashlib.sha256(str(token).encode("utf-8")).digest())

    def verify(self, token):
        candidate = hashlib.sha256(str(token).encode("utf-8")).digest()
        return hmac.compare_digest(self.digest, candidate)
