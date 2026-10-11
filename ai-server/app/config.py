"""환경 설정. 모델·제공사 교체는 .env만 바꾸면 된다 (코드 수정 없음)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv 없으면 환경변수만 사용
    pass


def _root() -> Path:
    if os.getenv("PROJECT_ROOT"):
        return Path(os.environ["PROJECT_ROOT"])
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path = field(default_factory=_root)

    # 답변 생성 LLM. provider는 LangChain init_chat_model의 model_provider 값
    # (google_genai, openai 등). API 키는 GOOGLE_API_KEY / OPENAI_API_KEY 환경변수.
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")   # 처리방침(frontend/src/lib/privacy.js)의 이전받는 자와 같아야 한다
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14")

    # 평가 채점 LLM. 개선 전후를 비교하는 동안에는 바꾸지 않는다.
    judge_provider: str = os.getenv("JUDGE_PROVIDER", "google_genai")
    judge_model: str = os.getenv("JUDGE_MODEL", "gemini-3.8-flash")

    # 임베딩. local = sentence-transformers 로컬 모델 (기본, 바꾸면 재색인 필요)
    #         gemini = Gemini 임베딩 API / hash = 문자 n-gram 해시 (오프라인 테스트용)
    # 기본은 한국어 검색용으로 다듬은 경량 모델(1.2억 파라미터). bge-m3(5.7억)는 비교 기준선.
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "dragonkue/multilingual-e5-small-ko-v2")

    # 리랭커(cross-encoder). 하이브리드 상위 후보를 질문과 함께 다시 읽어 순위를 매긴다.
    reranker_model: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    rerank_pool: int = int(os.getenv("RERANK_POOL", "20"))

    # 벡터 색인 위치. file = .cache/index_*.npy (테스트·평가용), pgvector = PostgreSQL (API 서버용)
    vector_backend: str = os.getenv("VECTOR_BACKEND", "file")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://seoullearn:seoullearn_dev@db:5432/seoullearn")

    top_k: int = int(os.getenv("TOP_K", "5"))
    # 분당 요청 수 상한. Gemini 무료 등급으로 돌릴 때만 .env에서 8로 낮춘다.
    llm_rpm: float = float(os.getenv("LLM_RPM", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "5"))
    # 평가 실행의 LLM 응답 캐시. API 서버는 이 값과 상관없이 캐시를 쓰지 않는다.
    llm_cache: bool = os.getenv("LLM_CACHE", "on").lower() != "off"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def cache_dir(self) -> Path:
        d = self.root / ".cache"
        d.mkdir(exist_ok=True)
        return d


settings = Settings()
