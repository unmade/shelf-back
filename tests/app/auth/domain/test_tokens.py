from __future__ import annotations

import pytest

from app.app.auth.domain.tokens import Encodable, InvalidToken


class TestEncodable:
    class Token(Encodable):
        def __init__(self, sub):
            self.sub = sub

        def dict(self):
            return {"sub": self.sub}

    def test_encode_decode(self):
        token = self.Token(sub="my-token")
        encoded_token = token.encode()
        decoded_token = self.Token.decode(encoded_token)
        assert decoded_token.sub == token.sub

    def test_decode_invalid_token(self):
        with pytest.raises(InvalidToken):
            self.Token.decode("invalid-token")
