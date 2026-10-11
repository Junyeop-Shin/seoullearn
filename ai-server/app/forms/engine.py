"""양식 엔진: 양식 스키마(forms/<form_id>.json)와 멘토 입력으로 초안을 만든다.

필드의 source에 따라 처리한다.
- user        입력값을 그대로 쓴다 (형식만 검증)
- placeholder [멘티명] 같은 자리표시. 개인정보 칸이므로 입력이 와도 버리고 경고한다
- derived     규칙 함수로 계산한다 (양식별 훅)
- user_text   멘토가 쓴 사실을 LLM이 문장으로 다듬기만 한다
- llm_draft   입력을 바탕으로 LLM이 초안을 쓴다
LLM에는 가드로 가린 글만 보내고, 결과에 입력에 없는 숫자가 있으면 그 문장을 뺀다. 아무것도 저장하지 않는다.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from .. import guard, prompts
from ..config import settings
from ..llm import ChatLLM, LLMUnavailableError
from . import checks

PLACEHOLDERS = {"mentee_name": "[멘티명]", "mentee_grade": "[멘티 학년]", "mentee": "[멘티 학년]", "mentor": "[멘토 성명·소속]"}

SYSTEM = prompts.load("draft_fields")


@lru_cache(maxsize=32)
def load_form(form_id: str) -> dict:
    if not re.fullmatch(r"[a-z0-9_]{1,50}", form_id):
        raise ValueError(f"양식 이름 오류: {form_id}")
    return json.loads((settings.root / "forms" / f"{form_id}.json").read_text(encoding="utf-8"))


@dataclass
class Context:
    """양식 하나를 처리하는 동안의 작업 공간."""
    form: dict
    inputs: dict          # 가드를 거친 입력 (LLM에 보내도 되는 글)
    extra: dict = field(default_factory=dict)  # 필드가 아닌 참고 입력 (메모, 사전 연락 답변, 주차별 계획 등)
    warnings: list[str] = field(default_factory=list)
    reminders: list[str] = field(default_factory=list)
    pii: set[str] = field(default_factory=set)
    safety: bool = False  # 입력에서 아동 안전 신호를 봤다

    def warn(self, msg: str):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def remind(self, msg: str):
        if msg not in self.reminders:
            self.reminders.append(msg)


class Hooks:
    """양식별 특수 처리. 필요한 것만 덮어쓴다."""

    def prepare(self, ctx: Context) -> None:
        """입력을 다듬거나 미리 검사한다."""

    def required(self, f: dict, ctx: Context) -> bool:
        return bool(f.get("required"))

    def derive(self, f: dict, ctx: Context):
        """source가 derived인 필드의 값. 계산할 수 없으면 None."""
        return None

    def fixed(self, f: dict, ctx: Context):
        """LLM에 맡기지 않고 규칙으로 정할 값. 없으면 None."""
        return None

    def finish(self, ctx: Context, result: "DraftResult") -> None:
        """안내 문구 추가, 출력 정리."""


_HOOKS: dict[str, Hooks] = {}


def register(form_id: str):
    def deco(cls):
        _HOOKS[form_id] = cls()
        return cls
    return deco


@dataclass
class DraftResult:
    form_id: str
    draft: dict
    missing_questions: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reminders: list[str] = field(default_factory=list)
    pii_masked: list[str] = field(default_factory=list)
    error: str | None = None  # LLM 출력 형식 오류
    text: str | None = None   # 서식에 붙여 넣기 좋게 정리한 글 (양식에 따라)

    def to_dict(self):
        return asdict(self)


def _mask(value, ctx: Context):
    if isinstance(value, str):
        g = guard.check(value)
        ctx.pii.update(g.pii)
        ctx.safety = ctx.safety or g.safety
        return g.text
    if isinstance(value, list):
        return [_mask(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _mask(v, ctx) for k, v in value.items()}
    return value


def _empty(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def _validate_user(f: dict, value, ctx: Context) -> None:
    rules, label, t = f.get("rules") or {}, f["label"], f.get("type")
    if t == "integer":
        try:
            n = int(str(value).strip())
        except ValueError:
            ctx.warn(f"'{label}'은(는) 숫자로 적어 주세요.")
            return
        if "min" in rules and n < rules["min"] or "max" in rules and n > rules["max"]:
            ctx.warn(f"'{label}'은(는) {rules.get('min')}~{rules.get('max')} 사이여야 합니다.")
    elif t in ("enum", "scale5") and f.get("options") and str(value) not in f["options"]:
        ctx.warn(f"'{label}'은(는) {', '.join(f['options'])} 중에서 골라 주세요.")
    elif t == "date" and checks.parse_date(str(value)) is None:
        ctx.warn(f"'{label}'을(를) 2026-05-25처럼 적어 주세요.")
    elif t == "datetime" and checks.parse_datetime(str(value)) is None:
        ctx.warn(f"'{label}'을(를) 2026-05-25 17:00처럼 적어 주세요.")


def _sources_text(ctx: Context, f: dict) -> str:
    """지어내기 검사의 기준: 입력 전체 + 이 필드의 안내문(자리 이름의 번호 등)."""
    return json.dumps([ctx.inputs, ctx.extra, f.get("label"), f.get("guidance"), f.get("item_slots"), f.get("slot_marks"), f.get("item_format")],
                      ensure_ascii=False)


# 줄 머리의 표시: (1), ①, (과목역량), 17:00~17:10. 다듬을 때는 떼어 두었다가 규칙으로 다시 붙인다 (AI가 형식을 바꾸지 못하게)
_HEAD = re.compile(r"^(\s*(?:\(\d{1,2}\)|[①-⑳]|\([^)\n]{1,15}\)|\d{1,2}:\d{2}~\d{1,2}:\d{2})\s*)(.*)$")


def _split_heads(value) -> list[tuple[str, str]] | None:
    """다듬을 글을 줄마다 (머리 표시, 본문)으로 나눈다. 한 줄이고 머리 표시도 없으면 None (그대로 다듬는다)."""
    lines = [str(x) for x in value] if isinstance(value, list) else str(value).split("\n")
    pairs = []
    for line in lines:
        m = _HEAD.match(line)
        pairs.append((m.group(1), m.group(2)) if m else ("", line))
    return None if len(pairs) == 1 and not pairs[0][0] else pairs


def _ask_llm(todo: list[dict], ctx: Context, llm: ChatLLM, reference: bool = True) -> tuple[dict, str | None]:
    # 다듬기 항목만 물을 때는 참고 입력을 주지 않는다: 멘토가 쓴 글에 인계 내용 같은 다른 자료가 섞이지 않게
    public = {k: v for k, v in ctx.extra.items() if not k.startswith("_")} if reference else {}
    user = (f"[양식]\n{ctx.form['title']}\n\n[참고 입력]\n{json.dumps(public, ensure_ascii=False)}\n\n"
            f"[만들 항목]\n{json.dumps(todo, ensure_ascii=False)}")
    try:
        raw = llm.complete(SYSTEM, user)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError("JSON 없음")
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            raise ValueError("JSON 객체가 아님")
        return data, None
    except LLMUnavailableError:
        raise
    except Exception as e:  # 형식 오류는 기록하고, 입력을 그대로 쓰는 쪽으로 물러난다
        return {}, f"{type(e).__name__}: {e}"


def _lost_tokens(original: str, polished: str) -> list[str]:
    """다듬은 글에서 빠진 숫자와 영문 낱말. 이런 말은 바꿔 쓸 일이 없으므로, 빠졌으면 내용이 빠진 것으로 본다."""
    low = polished.lower()
    return sorted({t for t in re.findall(r"\d+|[A-Za-z]{2,}", original) if t.lower() not in low})


def _polish_item(key: str, label: str, f: dict, value, heads: dict) -> dict:
    """다듬기 항목. 여러 줄이거나 줄 머리에 표시가 있으면 본문만 번호를 붙여 보내고, 표시는 나중에 규칙으로 다시 붙인다.
    번호를 키로 주고받으면 AI가 줄을 합치거나 나눠도 줄마다 맞춰 볼 수 있다. 항목 틀(item_slots)은 주지 않는다."""
    pairs = _split_heads(value)
    if pairs is None:
        return {"key": key, "label": label, "mode": "polish", "type": f.get("type", "text"), "guidance": f.get("guidance"), "input": value}
    heads[key] = (value, pairs)
    numbered = {str(n): body for n, (_, body) in enumerate(pairs, 1) if body.strip()}
    return {"key": key, "label": label, "mode": "polish", "type": "lines", "input": numbered}


def _join_heads(kept: tuple, out, label: str, ctx: Context, sources: str):
    """다듬은 본문에 줄 머리 표시를 다시 붙인다.
    AI가 돌려주지 않은 줄은 멘토가 쓴 글을 그대로 두고, 입력에 없는 숫자가 들어간 줄도 멘토가 쓴 글로 되돌린다.
    빈 글로 돌려준 줄(개인정보뿐이던 줄)은 머리 표시째 뺀다. 형식을 알아볼 수 없으면 전체를 그대로 둔다."""
    original, pairs = kept
    numbers = [str(n) for n, (_, body) in enumerate(pairs, 1) if body.strip()]
    if isinstance(out, list) and len(out) == len(numbers):   # 번호 없이 같은 개수의 목록으로 돌려준 경우: 차례대로 맞춘다
        out = dict(zip(numbers, out))
    if not isinstance(out, dict):
        if not _empty(out):
            ctx.warn(f"'{label}'은(는) AI가 줄 구성을 바꿔서, 다듬은 글을 쓰지 않고 적은 그대로 두었습니다.")
        return original
    lines, invented, lost = [], [], []
    for n, (head, body) in enumerate(pairs, 1):
        if not body.strip():
            lines.append((head, body))
            continue
        new = out.get(str(n))
        new = body if new is None else " ".join(str(new).split())   # 돌려주지 않은 줄은 적은 그대로. 한 줄은 한 줄로 둔다 (줄 머리 표시가 없는 줄이 생기지 않게)
        bad = checks.unsupported_numbers(new, sources)
        if bad:
            invented += bad
            new = body
        elif new and _lost_tokens(body, new):   # 내용이 빠진 줄도 적은 그대로 둔다 (빈 글로 돌아온 줄은 개인정보뿐이던 줄이라 뺀다)
            lost += _lost_tokens(body, new)
            new = body
        if new:
            lines.append((head, new))
    if lost:
        ctx.warn(f"'{label}'의 한 줄은 AI가 다듬으면서 일부 내용({', '.join(sorted(set(lost)))})을 빠뜨려, 그 줄은 적은 그대로 두었습니다.")
    if invented:
        ctx.warn(f"'{label}'의 다듬은 줄에 입력에 없는 숫자({', '.join(sorted(set(invented)))})가 들어가, 그 줄은 적은 그대로 두었습니다.")
    joined = [head + body for head, body in lines]
    return joined if isinstance(original, list) else "\n".join(joined)


def draft(form_id: str, inputs: dict, llm: ChatLLM, extra: dict | None = None) -> DraftResult:
    """inputs: 필드 key별 입력. extra: 필드가 아닌 참고 입력."""
    form = load_form(form_id)
    hooks = _HOOKS.get(form_id, Hooks())
    ctx = Context(form=form, inputs={}, extra={})
    ctx.inputs = _mask({k: v for k, v in (inputs or {}).items()}, ctx)
    ctx.extra = _mask(dict(extra or {}), ctx)
    if ctx.safety:  # 아동 안전 신호: LLM을 부르지 않고 운영사무국(즉시) 안내만 돌려준다
        return DraftResult(form_id=form_id, draft={}, warnings=[guard.SAFETY_DRAFT_NOTICE], pii_masked=sorted(ctx.pii))
    # only: LLM에 맡길 항목의 key 목록. 있으면 나머지 항목은 LLM을 거치지 않고 멘토가 쓴 글(입력 또는 extra.memo)을 그대로 둔다.
    # 빈 목록이면 LLM을 부르지 않는다 (간단 모드, 수정한 항목만 다시 만들기, 한 항목만 다시 만들기에 쓴다)
    only = ctx.extra.pop("only", None)
    only = set(map(str, only)) if isinstance(only, list) else None
    memo = ctx.extra.get("memo") if isinstance(ctx.extra.get("memo"), dict) else {}
    hooks.prepare(ctx)

    result = DraftResult(form_id=form_id, draft={})
    todo: list[dict] = []
    heads: dict[str, tuple] = {}   # 다듬기 항목의 (원래 값, 줄마다의 (머리 표시, 본문))
    by_key = {f["key"]: f for f in form["fields"]}
    for f in form["fields"]:
        key, label, source = f["key"], f["label"], f.get("source")
        value = ctx.inputs.get(key)
        if f.get("pii") or source == "placeholder":
            if not _empty(value):
                ctx.warn(f"'{label}'은(는) 입력받지 않는 개인정보입니다. 입력값을 버렸습니다.")
                ctx.inputs.pop(key, None)
            result.draft[key] = PLACEHOLDERS.get(key, f"[{label}]")
            continue
        if source == "derived":
            result.draft[key] = hooks.derive(f, ctx)
            if _empty(result.draft[key]) and hooks.required(f, ctx):
                result.missing_questions.append({"key": key, "label": label, "question": f"'{label}' 칸을 채울 정보가 부족합니다."})
            continue
        fixed = hooks.fixed(f, ctx)
        if fixed is not None:
            result.draft[key] = fixed
            continue
        if source == "user":
            result.draft[key] = "" if _empty(value) else value
            if _empty(value):
                if hooks.required(f, ctx):
                    result.missing_questions.append({"key": key, "label": label, "question": f"'{label}' 칸을 적어 주세요."})
            else:
                _validate_user(f, value, ctx)
            continue
        if source == "user_text":
            if _empty(value):
                result.draft[key] = [] if f.get("type") == "list" else ""
                if hooks.required(f, ctx):
                    result.missing_questions.append({"key": key, "label": label, "question": f"'{label}'에 쓸 내용을 알려 주세요."})
                continue
            if only is not None and key not in only:
                result.draft[key] = value
                continue
            todo.append(_polish_item(key, label, f, value, heads))
            continue
        # llm_draft
        if only is not None and key not in only:
            kept = memo.get(key) or ("" if _empty(value) else value)
            result.draft[key] = [x.strip() for x in str(kept).split("\n") if x.strip()] if f.get("type") == "list" and isinstance(kept, str) else kept
            continue
        if not _empty(memo.get(key)):
            # 멘토가 적은 글이 있으면 초안을 새로 쓰지 않고 그 글만 다듬는다 (참고 입력의 다른 내용을 섞지 않게)
            todo.append(_polish_item(key, label, f, memo[key], heads))
            continue
        # slot_marks가 있는 항목은 자리마다 한 항목씩 목록으로 받고, 줄 머리 표시((1), (과목역량) 등)는 규칙으로 붙인다
        todo.append({"key": key, "label": label, "mode": "draft", "type": "list" if f.get("slot_marks") else f.get("type", "text"),
                     "guidance": f.get("guidance"), "item_slots": f.get("item_slots"), "item_format": f.get("item_format")})

    # 다듬기 항목과 초안 항목은 따로 묻는다: 다듬기에는 참고 입력을 주지 않는다
    data, errors = {}, []
    for mode, reference in (("polish", False), ("draft", True)):
        group = [t for t in todo if t["mode"] == mode]
        if group:
            got, err = _ask_llm(group, ctx, llm, reference)
            data.update(got)
            if err:
                errors.append(err)
    result.error = "; ".join(errors) or None
    for item in todo:
        key, f = item["key"], by_key[item["key"]]
        out = data.get(key)
        is_list = f.get("type") == "list"
        marks = f.get("slot_marks") if item["mode"] == "draft" else None
        nothing_known = False
        if marks and isinstance(out, list) and len(out) == len(marks):
            lines = [f"{m} {str(x).strip()}" for m, x in zip(marks, out) if str(x or "").strip()]
            nothing_known = not lines   # 근거가 없어 모든 자리를 비운 것은 실패가 아니다 (되묻지 않는다)
            out = lines if is_list else "\n".join(lines)
        if key in heads:
            out = _join_heads(heads[key], out, f["label"], ctx, _sources_text(ctx, f))
        elif nothing_known:
            out = [] if is_list else ""
        elif _empty(out):
            # LLM이 못 채웠으면: 다듬기 항목은 입력을 그대로, 초안 항목은 비우고 되묻는다
            out = item.get("input", [] if is_list else "")
            if item["mode"] == "draft":
                result.missing_questions.append({"key": key, "label": f["label"], "question": f"'{f['label']}' 초안을 만들지 못했습니다. 직접 작성해 주세요."})
        if is_list and isinstance(out, str):
            out = [x.strip() for x in out.split("\n") if x.strip()]
        if not is_list and isinstance(out, list):
            out = " ".join(str(x) for x in out)
        if item["mode"] == "polish" and key not in heads and isinstance(out, str) and isinstance(item.get("input"), str):
            gone = _lost_tokens(item["input"], out)
            if gone:   # 한 줄짜리 다듬기에서도 숫자·영문 낱말이 빠졌으면 적은 그대로 둔다
                ctx.warn(f"'{f['label']}'은(는) AI가 다듬으면서 일부 내용({', '.join(gone)})을 빠뜨려, 적은 그대로 두었습니다.")
                out = item["input"]
        out = _mask(out, ctx)  # LLM이 개인정보를 되살렸을 때를 대비해 한 번 더 가린다
        kept, removed = checks.drop_unsupported(out, _sources_text(ctx, f))
        if removed:
            ctx.warn(f"'{f['label']}'에 입력에 없는 숫자({', '.join(removed)})가 들어가 해당 문장을 뺐습니다. 내용을 확인해 주세요.")
            if _empty(kept) and item["mode"] == "polish":
                kept = heads[key][0] if key in heads else item["input"]  # 다듬은 글을 못 쓰면 멘토가 쓴 글을 그대로 둔다
            out = kept
        result.draft[key] = out

    for chk in form.get("submission_checks", []):
        if chk.get("type") in ("reminder", "deadline"):
            ctx.remind(chk["rule"])
    # 가린 개인정보의 자리표시([이름] 등)는 초안에 남기지 않는다 (AI를 쓰지 않은 항목도 같다)
    for key, value in result.draft.items():
        if isinstance(value, str):
            result.draft[key] = guard.drop_marks(value)
        elif isinstance(value, list):
            result.draft[key] = [guard.drop_marks(x) if isinstance(x, str) else x for x in value]
    hooks.finish(ctx, result)
    result.warnings = ctx.warnings
    result.reminders = ctx.reminders
    result.pii_masked = sorted(ctx.pii)
    return result
