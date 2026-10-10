"""답 못 한 질문 모음: 매뉴얼로 답하지 못한(no·partial) 질문을 모아 운영 측의 매뉴얼 보완 자료로 쓴다.

저장하는 것은 가드로 가린 질문 문장, 분류(no·partial), 문의처, 날짜(일 단위)뿐이다.
누가 물었는지(아이디, 접속 주소, 시각)는 저장하지 않는다.
아동 안전 신호가 있거나, 정서·가정·건강·성적 이야기가 들었거나, 상황을 길게 풀어 쓴 질문은 저장하지 않는다
(멘티 개인의 사정일 가능성이 높다). 매뉴얼에 대한 짧은 질문만 모은다.
UNANSWERED_LOG=off면 아무것도 저장하지 않는다.
"""
from __future__ import annotations

import logging
import os
import re

from . import guard
from .config import settings
from .forms import sensitive

log = logging.getLogger("ai-server")
MAX_LEN = 150   # 이보다 긴 글은 상황 설명일 가능성이 높아 저장하지 않는다
_ACADEMIC = re.compile(r"성적|등급|점수|\d+\s*점|석차|등수")


def enabled() -> bool:
    return os.getenv("UNANSWERED_LOG", "off").lower() == "on"


def to_store(question: str, answerable: str, safety: bool = False) -> str | None:
    """저장할 문장(가린 것). 저장하면 안 되는 질문이면 None."""
    if safety or answerable not in ("no", "partial"):
        return None
    g = guard.check(question)
    if g.safety:
        return None
    if sensitive.filter_text(g.text)[1]:   # 정서·가정·건강 이야기가 섞인 질문은 남기지 않는다
        return None
    text = " ".join(g.text.split())
    if len(text) < 2 or len(text) > MAX_LEN or _ACADEMIC.search(text):
        return None
    return text


def _insert(question: str, answerable: str, route: str | None) -> None:
    import psycopg  # 지연 import

    # 테이블은 backend가 시작할 때 만든다 (backend/src/main/resources/schema.sql)
    with psycopg.connect(settings.database_url, autocommit=True, connect_timeout=3) as conn:
        conn.execute("INSERT INTO unanswered_question (question, answerable, route, created_on) VALUES (%s, %s, %s, CURRENT_DATE)",
                     (question, answerable, route))


def record(question: str, answerable: str, route: str | None, safety: bool = False) -> bool:
    """저장했으면 True. 저장 실패는 답변에 영향을 주지 않는다 (내용 없이 실패 사실만 로그에 남긴다)."""
    if not enabled():
        return False
    text = to_store(question, answerable, safety)
    if text is None:
        return False
    try:
        _insert(text, answerable, route)
        return True
    except Exception as e:
        log.warning("unanswered_store_failed type=%s", type(e).__name__)
        return False
