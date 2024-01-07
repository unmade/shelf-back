# The MIT License (MIT)

# Copyright (c) 2020 to present Samuel Colvin

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import base64
import hashlib
import hmac
from binascii import hexlify
from datetime import UTC, datetime
from functools import reduce
from typing import TYPE_CHECKING, AsyncGenerator, Generator, Literal, TypeAlias
from urllib.parse import quote as url_quote

from httpx import URL, Auth, RequestNotRead

if TYPE_CHECKING:
    from httpx import Request, Response

_AWS_AUTH_REQUEST = "aws4_request"
_CONTENT_TYPE = "application/x-www-form-urlencoded"
_AUTH_ALGORITHM = "AWS4-HMAC-SHA256"

HttpMethod: TypeAlias = Literal["DELETE", "GET", "HEAD", "PATCH", "POST", "PUT"]


class AWSv4Auth:
    __slots__ = ("aws_secret_key", "aws_access_key", "region", "service")

    def __init__(
        self,
        aws_secret_key: str,
        aws_access_key: str,
        region: str,
        service: str,
    ) -> None:
        self.aws_secret_key = aws_secret_key
        self.aws_access_key = aws_access_key
        self.region = region
        self.service = service

    def auth_headers(
        self,
        method: HttpMethod,
        url: URL,
        *,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> dict[str, str]:
        now = datetime.now(UTC)
        data = data or b""
        content_type = content_type or _CONTENT_TYPE

        # WARNING! order is important here, headers need to be in alphabetical order
        headers = {
            "content-md5": base64.b64encode(hashlib.md5(data).digest()).decode(),
            "content-type": content_type,
            "host": url.host,
            "x-amz-date": _aws4_x_amz_date(now),
        }

        payload_sha256_hash = hashlib.sha256(data).hexdigest()
        signed_headers, signature = self.aws4_signature(
            now, method, url, headers, payload_sha256_hash
        )
        credential = self.aws4_credential(now)
        authorization_header = f"{_AUTH_ALGORITHM} Credential={credential},SignedHeaders={signed_headers},Signature={signature}"  # noqa: E501
        headers.update(
            {
                "authorization": authorization_header,
                "x-amz-content-sha256": payload_sha256_hash,
            }
        )
        return headers

    def aws4_signature(
        self,
        dt: datetime,
        method: HttpMethod,
        url: URL,
        headers: dict[str, str],
        payload_hash: str,
    ) -> tuple[str, str]:
        header_keys = sorted(headers)
        signed_headers = ";".join(header_keys)
        canonical_request_parts = (
            method,
            url_quote(url.path),
            url.query.decode(),
            "".join(f"{k}:{headers[k]}\n" for k in header_keys),
            signed_headers,
            payload_hash,
        )
        canonical_request = "\n".join(canonical_request_parts)
        string_to_sign_parts = (
            _AUTH_ALGORITHM,
            _aws4_x_amz_date(dt),
            self._aws4_scope(dt),
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        )
        string_to_sign = "\n".join(string_to_sign_parts)
        return signed_headers, self.aws4_sign_string(string_to_sign, dt)

    def aws4_sign_string(self, string_to_sign: str, dt: datetime) -> str:
        key_parts = (
            b"AWS4" + self.aws_secret_key.encode(),
            _aws4_date_stamp(dt),
            self.region,
            self.service,
            _AWS_AUTH_REQUEST,
            string_to_sign,
        )
        signature_bytes: bytes = reduce(
            _aws4_reduce_signature,  # type: ignore
            key_parts,
        )
        return hexlify(signature_bytes).decode()

    def _aws4_scope(self, dt: datetime) -> str:
        return (
            f"{_aws4_date_stamp(dt)}/{self.region}/{self.service}/{_AWS_AUTH_REQUEST}"
        )

    def aws4_credential(self, dt: datetime) -> str:
        return f"{self.aws_access_key}/{self._aws4_scope(dt)}"


class AWSV4AuthFlow(Auth):
    __slots__ = ("_authorizer",)

    def __init__(
        self,
        aws_secret_key: str,
        aws_access_key: str,
        region: str,
        service: str,
    ) -> None:
        self._authorizer = AWSv4Auth(
            aws_secret_key=aws_secret_key,
            aws_access_key=aws_access_key,
            region=region,
            service=service,
        )

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        try:
            content = request.content
        except RequestNotRead:
            content = request.read()

        self._set_auth_headers(request, content)
        yield request

    async def async_auth_flow(
        self, request: Request
    ) -> AsyncGenerator[Request, Response]:
        try:
            content = request.content
        except RequestNotRead:
            content = await request.aread()

        self._set_auth_headers(request, content)
        yield request

    def _set_auth_headers(self, request: Request, content: bytes) -> None:
        auth_headers = self._authorizer.auth_headers(
            method=request.method.upper(),  # type: ignore
            url=request.url,
            data=content,
            content_type=request.headers.get("Content-Type"),
        )
        request.headers.update(auth_headers)


def _aws4_date_stamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _aws4_x_amz_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _aws4_reduce_signature(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()
