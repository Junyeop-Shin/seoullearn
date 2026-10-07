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
    llm_provider: str = os.getenv("LLM_PROVIDER", "google_genai")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-3.6-flash")

    # 평가 채점 LLM. 개선 전후를 비교하는 동안에는 바꾸지 않는다.
    judge_provider: str = os.getenv("JUDGE_PROVIDER", "google_genai")
    judge_model: str = os.getenv("JUDGE_MODEL", "gemini-3.8-flash")

    # 임베딩. local = sentence-transformers 로컬 모델 (기본, 바꾸면 재색인 필요)
    #         gemini = Gemini 임베딩 API / hash = 문자 n-gram 해시 (오프라인 테스트용)
    # 기본은 한국어 검색용으로 다듬은 경량 모델(1.2억 파라미터). bge-m3(5.7억)는 비교 기준선.
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "dragonkue/multilingual-e5-small-ko-v2")

    top_k: int = int(os.getenv("TOP_K", "5"))
    # 무료 등급 요청 한도 대응. 분당 요청 수 상한.
    llm_rpm: float = float(os.getenv("LLM_RPM", "8"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "5"))

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def cache_dir(self) -> Path:
        d = self.root / ".cache"
        d.mkdir(exist_ok=True)
        return d


settings = Settings()
