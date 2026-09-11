"""Bounded independent embedding adapters; errors never expose provider payloads."""
from dataclasses import dataclass
from hashlib import sha256
import logging
import math
import re
from typing import Protocol
import unicodedata

import httpx

from backend.app.core.config import Settings

logger = logging.getLogger(__name__)
MAX_EMBEDDING_CHARACTERS = 8000


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text[:MAX_EMBEDDING_CHARACTERS]).casefold().split())[:MAX_EMBEDDING_CHARACTERS]


def features(text: str) -> tuple[str, ...]:
    tokens = []
    for chunk in re.findall(r"[\u3400-\u9fff]+|[^\W_\u3400-\u9fff]+", normalize(text)):
        if all("\u3400" <= c <= "\u9fff" for c in chunk):
            tokens.extend(chunk)
            tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
        else:
            tokens.append(chunk)
    return tuple(tokens)


class EmbeddingProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingResult:
    vector: tuple[float, ...]
    provider: str
    model: str
    version: str
    dimensions: int
    input_hash: str


class EmbeddingProvider(Protocol):
    provider: str
    model: str
    version: str
    dimensions: int

    def embed(self, text: str) -> EmbeddingResult: ...


def unit_vector(values, dimensions: int) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)) or len(values) != dimensions:
        raise EmbeddingProviderError("embedding unavailable")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        raise EmbeddingProviderError("embedding unavailable")
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingProviderError("embedding unavailable")
    return tuple(x / norm for x in values)


class DeterministicEmbeddingProvider:
    provider = "deterministic-fake"
    model = "sha256-features"
    version = "v1"

    def __init__(self, dimensions: int = 32):
        self.dimensions = dimensions

    def embed(self, text: str) -> EmbeddingResult:
        normalized = normalize(text)
        values = [0.0] * self.dimensions
        for token in features(normalized) or (normalized,):
            digest = sha256(token.encode()).digest()
            values[int.from_bytes(digest[:4], "big") % self.dimensions] += 1 if digest[4] & 1 else -1
        if not any(values):
            values[0] = 1
        return EmbeddingResult(unit_vector(values, self.dimensions), self.provider, self.model, self.version, self.dimensions, sha256(normalized.encode()).hexdigest())


class OpenAICompatibleEmbeddingProvider:
    provider = "openai-compatible"
    version = "v1"

    def __init__(self, *, base_url: str, api_key: str, model: str, auth_mode: str,
                 dimensions: int, timeout_seconds: float, client: httpx.Client | None = None):
        self.model, self.dimensions = model, dimensions
        self._endpoint = base_url.rstrip("/") + "/embeddings"
        self._api_key, self._auth_mode = api_key, auth_mode
        self._timeout, self._client = timeout_seconds, client

    def embed(self, text: str) -> EmbeddingResult:
        normalized = normalize(text)
        headers = {"Content-Type": "application/json"}
        if self._auth_mode == "bearer":
            headers["Authorization"] = "Bearer " + self._api_key
        try:
            body = {"model": self.model, "input": normalized, "dimensions": self.dimensions}
            if self._client is None:
                with httpx.Client() as client:
                    response = client.post(self._endpoint, headers=headers, json=body, timeout=self._timeout)
            else:
                response = self._client.post(self._endpoint, headers=headers, json=body, timeout=self._timeout)
            response.raise_for_status()
            vector = unit_vector(response.json()["data"][0]["embedding"], self.dimensions)
            return EmbeddingResult(vector, self.provider, self.model, self.version, self.dimensions, sha256(normalized.encode()).hexdigest())
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, EmbeddingProviderError):
            logger.warning("Embedding unavailable category=embedding_provider")
            raise EmbeddingProviderError("embedding unavailable") from None


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai_compatible":
        if (settings.embedding_base_url.strip() and settings.embedding_model.strip()
                and (settings.embedding_auth_mode == "none" or settings.embedding_api_key.strip())):
            return OpenAICompatibleEmbeddingProvider(base_url=settings.embedding_base_url.strip(),
                api_key=settings.embedding_api_key.strip(), model=settings.embedding_model.strip(),
                auth_mode=settings.embedding_auth_mode, dimensions=settings.embedding_dimensions,
                timeout_seconds=settings.embedding_timeout_seconds)
        logger.warning("Embedding fallback category=embedding_configuration")
    return DeterministicEmbeddingProvider(settings.embedding_dimensions)
