"""LLM 호출 전 안전장치.

1. 아동 안전 신호: 매뉴얼 p.25에 따라 답변을 만들지 않고 즉시 운영사무국 보고로 안내한다.
2. 개인정보 가리기: 전화번호·이메일·주민번호·학교명·'OOO 학생' 형태의 이름을 감지해 가린다.
   무료 LLM 등급에는 개인정보를 보내면 안 되므로, 감지되면 가린 문장만 보낸다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SAFETY_PATTERNS = [
    r"맞(았|는|아|고)\s*(다|대|요|왔)", r"때(렸|린|려)", r"학대", r"폭행", r"폭언", r"협박", r"성추행", r"성폭",
    r"자해", r"자살", r"죽고\s*싶", r"죽어\s*버리", r"가출", r"방임", r"굶(고|어|었)",
]
_SAFETY = re.compile("|".join(SAFETY_PATTERNS))

SAFETY_ANSWER = (
    "아동 보호·안전과 관련된 우려가 있다면 직접 판단하거나 혼자 대응하지 말고, 즉시 멘토링 운영사무국(02-3274-9212)에 "
    "보고한 뒤 안내받은 절차에 따라 주세요(활동가이드 p.25). 지금 당장 위험한 상황이라면 112에 먼저 신고해 주세요."
)

_PII = [
    ("전화번호", re.compile(r"01[016789][- .]?\d{3,4}[- .]?\d{4}"), "[전화번호]"),
    ("전화번호", re.compile(r"0\d{1,2}-\d{3,4}-\d{4}"), "[전화번호]"),
    ("이메일", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[이메일]"),
    ("주민등록번호", re.compile(r"\d{6}-?[1-4]\d{6}"), "[주민등록번호]"),
    ("학교명", re.compile(r"[가-힣]{2,8}(?:초등학교|중학교|고등학교|대학교)"), "[학교명]"),
    ("학교명", re.compile(r"(?<![가-힣])[가-힣]{2,4}(?:초|중|고)(?=\s|$|[^가-힣0-9])"), "[학교명]"),
]
_NAME = re.compile(r"(?<![가-힣])([가-힣]{2,4})(?=\s?(?:학생|어머님|아버님|어머니|아버지|군|양)(?:[^가-힣]|$|이|은|는|이가|의|한테|께))")
_NOT_NAME = {"멘티", "멘토", "해당", "우리", "그", "이", "저", "고등", "중학", "초등", "다른", "모든", "같은", "새로운",
             "학교", "대학", "여자", "남자", "고1", "고2", "고3", "어린", "신규", "기존", "담당", "이전", "다음", "한", "두"}
# 학교명 패턴이 일반 단어를 잡지 않도록 제외
_NOT_SCHOOL = {"중간", "최고", "지난고", "통과", "필수고", "여중", "남중", "여고", "남고"}


@dataclass
class GuardResult:
    text: str
    safety: bool = False
    pii: list[str] = field(default_factory=list)


def check(text: str) -> GuardResult:
    res = GuardResult(text=text, safety=bool(_SAFETY.search(text)))
    masked = text
    for label, pat, repl in _PII:
        def sub(m, label=label, repl=repl):
            if label == "학교명" and m.group(0) in _NOT_SCHOOL:
                return m.group(0)
            res.pii.append(label)
            return repl
        masked = pat.sub(sub, masked)

    def name_sub(m):
        if m.group(1) in _NOT_NAME:
            return m.group(0)
        res.pii.append("이름")
        return "[이름]"

    masked = _NAME.sub(name_sub, masked)
    res.text = masked
    res.pii = sorted(set(res.pii))
    return res
