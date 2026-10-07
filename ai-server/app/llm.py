"""LLM과 임베딩 제공자.

- ChatLLM.complete(system, user) -> str 하나만 쓰면 되도록 감쌌다.
- 실제 제공자는 LangChain init_chat_model로 만든다. 제공사·모델은 .env로 바꾼다.
- 요청 한도(429)에 걸리면 기다렸다 재시도하고, 같은 요청은 디스크 캐시로 재사용한다.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Protocol

import numpy as np

from .config import settings


class ChatLLM(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


class _Throttle:
    def __init__(self, rpm: float):
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self.last = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            gap = self.last + self.interval - time.monotonic()
            if gap > 0:
                time.sleep(gap)
            self.last = time.monotonic()


class DiskCache:
    """프롬프트 해시 → 응답. 평가를 다시 돌릴 때 무료 한도를 아끼기 위한 캐시."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["k"]] = rec["v"]
        self.lock = threading.Lock()

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def get(self, k: str) -> str | None:
        return self.data.get(k)

    def put(self, k: str, v: str):
        with self.lock:
            self.data[k] = v
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"k": k, "v": v}, ensure_ascii=False) + "\n")


class LangChainLLM:
    def __init__(self, provider: str, model: str, temperature: float = 0.0, use_cache: bool = True):
        from langchain.chat_models import init_chat_model  # 지연 import: 오프라인 테스트에는 불필요

        self.name = f"{provider}:{model}"
        self.model = init_chat_model(model, model_provider=provider, temperature=temperature)
        self.throttle = _Throttle(settings.llm_rpm)
        self.cache = DiskCache(settings.cache_dir / "llm_cache.jsonl") if use_cache else None

    def complete(self, system: str, user: str) -> str:
        k = DiskCache.key(self.name, system, user)
        if self.cache and (hit := self.cache.get(k)) is not None:
            return hit
        delay = 10.0
        for attempt in range(settings.llm_max_retries + 1):
            self.throttle.wait()
            try:
                msg = self.model.invoke([("system", system), ("human", user)])
                text = msg.content if isinstance(msg.content, str) else "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in msg.content
                )
                if self.cache:
                    self.cache.put(k, text)
                return text
            except Exception as e:  # 제공사별 예외 타입이 달라 문자열로 판별
                msg = str(e)
                retryable = any(s in msg for s in ("429", "RESOURCE_EXHAUSTED", "rate", "503", "UNAVAILABLE", "timeout"))
                if not retryable or attempt == settings.llm_max_retries:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 120)
        raise RuntimeError("unreachable")


def get_chat_model(role: str = "answer") -> ChatLLM:
    if role == "judge":
        return LangChainLLM(settings.judge_provider, settings.judge_model)
    return LangChainLLM(settings.llm_provider, settings.llm_model)


# ---------------------------------------------------------------- embeddings
class Embedder(Protocol):
    """embed()는 문서용, embed_query()는 질문용. e5 계열처럼 둘을 다르게 다루는 모델이 있다."""

    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def _normalize(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


class HashEmbedder:
    """문자 1~3-gram 해시 벡터. 의미 검색은 못 하지만 의존성 없이 돈다 (테스트·비교용)."""

    def __init__(self, dim: int = 4096):
        self.dim = dim
        self.name = f"hash-{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        m = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            t = "".join(t.split())
            for n in (1, 2, 3):
                for j in range(len(t) - n + 1):
                    h = int(hashlib.md5(t[j : j + n].encode("utf-8")).hexdigest()[:8], 16)
                    m[i, h % self.dim] += 1.0 if n > 1 else 0.3
        return _normalize(m)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


E5_INSTRUCT_TASK = "Given a question from a Seoul Learn mentor, retrieve manual or notice passages that answer it"


def e5_prefixes(model: str) -> tuple[str, str]:
    """e5 계열은 모델이 학습한 형식대로 앞말을 붙여야 제 성능이 난다.
    - instruct 모델: 질문에만 'Instruct: <작업 설명>\nQuery: ', 문서에는 없음
    - 일반 e5: 질문 'query: ', 문서 'passage: '"""
    name = model.lower().split("/")[-1]
    if "e5" in name and "instruct" in name:
        return f"Instruct: {E5_INSTRUCT_TASK}\nQuery: ", ""
    if "e5" in name:
        return "query: ", "passage: "
    return "", ""


class LocalEmbedder:
    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.name = f"local:{model}"
        self.query_prefix, self.passage_prefix = e5_prefixes(model)
        self.model = SentenceTransformer(model)

    def _encode(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._encode([self.passage_prefix + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([self.query_prefix + text])[0]


class GeminiEmbedder:
    def __init__(self, model: str):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self.name = f"gemini:{model}"
        self.model = GoogleGenerativeAIEmbeddings(model=model if model.startswith("models/") else f"models/{model}")
        self.throttle = _Throttle(settings.llm_rpm * 4)

    def embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 32):
            self.throttle.wait()
            out.extend(self.model.embed_documents(texts[i : i + 32]))
        return _normalize(np.asarray(out, dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        self.throttle.wait()
        return _normalize(np.asarray([self.model.embed_query(text)], dtype=np.float32))[0]


def get_embedder(provider: str | None = None, model: str | None = None) -> Embedder:
    provider = provider or settings.embedding_provider
    model = model or settings.embedding_model
    if provider == "hash":
        return HashEmbedder()
    if provider == "gemini":
        return GeminiEmbedder(model)
    return LocalEmbedder(model)
