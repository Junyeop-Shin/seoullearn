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

from .. import guard
from ..config import settings
from ..llm import ChatLLM, LLMUnavailableError
from . import checks

PLACEHOLDERS = {"mentee_name": "[멘티명]", "mentee_grade": "[멘티 학년]", "mentee": "[멘티 학년]", "mentor": "[멘토 성명·소속]"}

SYSTEM = """너는 서울런 멘토가 양식을 채우도록 돕는다. [만들 항목]의 각 항목을 아래 규칙대로 쓴다.

1. mode가 "polish"인 항목: input에 적힌 사실을 보고서 문장으로 다듬기만 한다. 내용을 보태거나 평가를 덧붙이지 않는다.
2. mode가 "draft"인 항목: [참고 입력]과 guidance를 바탕으로 초안을 쓴다.
3. 입력에 없는 사실(날짜, 점수, 등급, 진도, 강 번호, 진로, 상담 내용)을 만들지 않는다. 모르는 것은 쓰지 않는다.
4. 멘티·멘토의 이름, 학교, 연락처는 쓰지 않는다. 필요하면 '멘티'라고 쓴다.
5. 가정 형편, 가족 갈등, 정서 상담, 질병명은 쓰지 않는다.
6. 문체는 '~함', '~했음' 같은 보고서 문체로 간결하게 쓴다. 항목 이름(label)을 문장에 되풀이하지 않는다.
   input이 낱말이나 짧은 구절이면 문장으로 늘리지 말고 거의 그대로 둔다.
7. type이 "list"인 항목은 문자열 배열로, 나머지는 문자열 하나로 쓴다. item_slots가 있으면 그 순서대로 한 항목씩 쓴다.

반드시 [만들 항목]의 key를 그대로 쓴 JSON 객체 하나만 출력한다. 코드블록 표시는 쓰지 않는다."""


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

    def to_dict(self):
        return asdict(self)


def _mask(value, ctx: Context):
    if isinstance(value, str):
        g = guard.check(value)
        ctx.pii.update(g.pii)
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
    return json.dumps([ctx.inputs, ctx.extra, f.get("label"), f.get("guidance"), f.get("item_slots"), f.get("item_format")],
                      ensure_ascii=False)


def _ask_llm(todo: list[dict], ctx: Context, llm: ChatLLM) -> tuple[dict, str | None]:
    user = (f"[양식]\n{ctx.form['title']}\n\n[참고 입력]\n{json.dumps(ctx.extra, ensure_ascii=False)}\n\n"
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


def draft(form_id: str, inputs: dict, llm: ChatLLM, extra: dict | None = None) -> DraftResult:
    """inputs: 필드 key별 입력. extra: 필드가 아닌 참고 입력."""
    form = load_form(form_id)
    hooks = _HOOKS.get(form_id, Hooks())
    ctx = Context(form=form, inputs={}, extra={})
    ctx.inputs = _mask({k: v for k, v in (inputs or {}).items()}, ctx)
    ctx.extra = _mask(dict(extra or {}), ctx)
    hooks.prepare(ctx)

    result = DraftResult(form_id=form_id, draft={})
    todo: list[dict] = []
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
                result.missing_questions.append({"key": key, "label": label, "question": f"'{label}'을(를) 계산할 정보가 부족합니다."})
            continue
        fixed = hooks.fixed(f, ctx)
        if fixed is not None:
            result.draft[key] = fixed
            continue
        if source == "user":
            result.draft[key] = "" if _empty(value) else value
            if _empty(value):
                if hooks.required(f, ctx):
                    result.missing_questions.append({"key": key, "label": label, "question": f"'{label}'을(를) 알려 주세요."})
            else:
                _validate_user(f, value, ctx)
            continue
        if source == "user_text":
            if _empty(value):
                result.draft[key] = [] if f.get("type") == "list" else ""
                if hooks.required(f, ctx):
                    result.missing_questions.append({"key": key, "label": label, "question": f"'{label}'에 쓸 내용을 알려 주세요."})
                continue
            todo.append({"key": key, "label": label, "mode": "polish", "type": f.get("type", "text"),
                         "guidance": f.get("guidance"), "item_slots": f.get("item_slots"), "input": value})
            continue
        # llm_draft
        todo.append({"key": key, "label": label, "mode": "draft", "type": f.get("type", "text"),
                     "guidance": f.get("guidance"), "item_slots": f.get("item_slots"), "item_format": f.get("item_format")})

    data, result.error = _ask_llm(todo, ctx, llm) if todo else ({}, None)
    for item in todo:
        key, f = item["key"], by_key[item["key"]]
        out = data.get(key)
        is_list = f.get("type") == "list"
        if _empty(out):
            # LLM이 못 채웠으면: 다듬기 항목은 입력을 그대로, 초안 항목은 비우고 되묻는다
            out = item.get("input", [] if is_list else "")
            if item["mode"] == "draft":
                result.missing_questions.append({"key": key, "label": f["label"], "question": f"'{f['label']}' 초안을 만들지 못했습니다. 직접 작성해 주세요."})
        if is_list and isinstance(out, str):
            out = [x.strip() for x in out.split("\n") if x.strip()]
        if not is_list and isinstance(out, list):
            out = " ".join(str(x) for x in out)
        out = _mask(out, ctx)  # LLM이 개인정보를 되살렸을 때를 대비해 한 번 더 가린다
        kept, removed = checks.drop_unsupported(out, _sources_text(ctx, f))
        if removed:
            ctx.warn(f"'{f['label']}'에 입력에 없는 숫자({', '.join(removed)})가 들어가 해당 문장을 뺐습니다. 내용을 확인해 주세요.")
            if _empty(kept) and item["mode"] == "polish":
                kept = item["input"]  # 다듬은 글을 못 쓰면 멘토가 쓴 글을 그대로 둔다
            out = kept
        result.draft[key] = out

    for chk in form.get("submission_checks", []):
        if chk.get("type") in ("reminder", "deadline"):
            ctx.remind(chk["rule"])
    hooks.finish(ctx, result)
    result.warnings = ctx.warnings
    result.reminders = ctx.reminders
    result.pii_masked = sorted(ctx.pii)
    return result
