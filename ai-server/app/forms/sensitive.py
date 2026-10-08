"""보고서에 그대로 옮기면 안 되는 내용을 문장 단위로 걸러낸다.

- 정서·가정 이야기: 활동보고서 학습 내용에 넣지 않는다 (멘토가 필요하면 감성케어 칸에 직접 쓴다).
- 건강 정보(질병명 등): '질병으로 인한 결석' 수준으로만 남긴다.
낱말 규칙이라 놓치는 표현이 있을 수 있다. LLM 지시문에도 같은 규칙을 넣어 한 번 더 막는다.
"""
from __future__ import annotations

import re

_EMOTION = re.compile(
    r"다퉈|다퉜|다툼|싸워|싸웠|혼났|혼나|울었|울먹|우울|불안해|속상|자존감|외롭|따돌|왕따|"
    r"부모님이랑|부모님과|엄마랑|아빠랑|가정사|집안\s*사정|이혼|별거|형편|용돈|고민\s*상담|얘기\s*들어|이야기\s*들어|하소연")
_HEALTH = re.compile(
    r"독감|감기|장염|코로나|확진|골절|수술|입원|응급실|병원\s*진료|진료\s*받|통원|복통|두통|발열|고열|몸살|알레르기|천식|"
    r"빈혈|우울증|불면|치과|정형외과|내과|이비인후과|피부과|안과|한의원|약\s*복용|처방")
_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+|(?<=[다요음함됨임])\.\s*")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SPLIT.split(text or "") if p and p.strip()]
    out: list[str] = []
    for p in parts:  # 마침표 없이 쉼표로 이어 쓴 메모도 나눈다
        out.extend(x.strip() for x in re.split(r",\s*", p) if x.strip()) if _EMOTION.search(p) or _HEALTH.search(p) else out.append(p)
    return out


def filter_text(text: str) -> tuple[str, list[str]]:
    """(걸러낸 문장, 걸러낸 종류 목록). 종류: '정서', '건강'."""
    kinds: list[str] = []
    kept: list[str] = []
    for s in split_sentences(text):
        if _HEALTH.search(s):
            kinds.append("건강")
            if "질병으로 인한 결석" not in kept:
                kept.append("질병으로 인한 결석")
        elif _EMOTION.search(s):
            kinds.append("정서")
        else:
            kept.append(s)
    return ". ".join(k.rstrip(".") for k in kept), sorted(set(kinds))
