"""프롬프트와 문구 템플릿을 파일에서 읽는다 (prompts/, templates/). 코드에 박아 두지 않아 문구만 따로 고칠 수 있다."""
from __future__ import annotations

import re
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=64)
def load(name: str, folder: str = "prompts") -> str:
    if not re.fullmatch(r"[a-z0-9_]{1,50}", name):
        raise ValueError(f"파일 이름 오류: {name}")
    return (settings.root / folder / f"{name}.md").read_text(encoding="utf-8").strip()


def render(name: str, **values) -> str:
    """templates/<name>.md의 {자리}를 채운다. 값이 빈 줄(그 줄의 자리가 모두 빈 값)은 뺀다."""
    out = []
    for line in load(name, "templates").split("\n"):
        keys = re.findall(r"\{(\w+)\}", line)
        if keys and not any(str(values.get(k, "")).strip() for k in keys):
            continue
        out.append(re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), "")), line))
    return "\n".join(out)
