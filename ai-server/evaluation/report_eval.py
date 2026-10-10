"""보고서 초안 품질 평가 (활동보고서, 종합계획서①).

  python -m evaluation.report_eval            실제 LLM으로 초안을 만들어 규칙으로 잰다
  python -m evaluation.report_eval --judge    문장 내용의 지어내기를 LLM 채점으로 한 번 더 본다
  python -m evaluation.report_eval --fake     가짜 LLM (흐름 확인용)
결과: eval/runs/report_eval.json, eval/reports/report_eval.md

지표
- 필수 항목 채움률: 채워져야 하는 필수 칸 중 실제로 채워진 비율 (되물은 칸, 결석 회차의 학습 칸, 자리표시 칸 제외)
- 지어내기: 초안의 숫자·날짜·강 번호 중 입력에 없는 것 (규칙 검사)
- 개인정보 노출: 초안에 나오면 안 되는 말(이름, 전화번호, 학교명, 정서·건강 내용)이 나온 건수
- 플랫폼 입력 오류 위험: 종합계획서①에 남은 특수문자, 300자를 넘는 칸
- 되묻기 정확도: 되물어야 할 항목과 실제로 되물은 항목이 같은 사례의 비율
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app import forms
from app.config import settings
from app.forms import checks, weekly_plan
from app.llm import get_eval_model

ROOT = settings.root
JUDGE = """멘토가 넣은 [입력]을 AI가 보고서 문장으로 옮긴 [초안]을 검사한다.
[초안]의 각 문장이 [입력]의 어느 부분에서 왔는지 하나씩 대조한다.
[입력] 어디에도 근거가 없는 새로운 사실(사건, 평가, 수치, 일정, 진로, 상담 내용)만 골라낸다.
[입력]에 있는 내용을 문장으로 풀어 쓰거나, 줄이거나, 말투를 바꾼 것은 문제가 아니다.
JSON 한 개만 출력: {"unsupported": ["초안에서 문제인 구절", ...]}  (없으면 빈 배열)"""


class FakeLLM:
    name = "fake"

    def complete(self, system: str, user: str) -> str:
        if "[만들 항목]" not in user:
            return "{}"
        out = {}
        for item in json.loads(user.split("[만들 항목]\n", 1)[1]):
            out[item["key"]] = item.get("input") or (["(가짜 초안)"] if item["type"] == "list" else "(가짜 초안)")
        return json.dumps(out, ensure_ascii=False)


def _load(name: str) -> dict:
    return json.loads((ROOT / "synthetic" / name).read_text(encoding="utf-8"))


def activity_input(case: dict) -> dict:
    mentee, no = case["source"].split("#")
    info = next(m for m in _load("mentees.json")["mentees"] if m["id"] == mentee)
    course = next(c for c in _load("courses.json")["courses"] if c["id"] == info["course_id"])
    s = next(x for x in _load(f"sessions_{mentee}.json")["sessions"] if x["session_no"] == int(no))
    inp = {"session_date": s["date"], "session_no": s["session_no"], "subject": info["subject"], "course": course["title"],
           "status": s["status"], **s["mentor_input"]}
    for k in case.get("blank", []):
        inp[k] = ""
    return inp


def plan_input(case: dict, llm) -> tuple[dict, dict]:
    mentee = case["source"]
    info = next(m for m in _load("mentees.json")["mentees"] if m["id"] == mentee)
    course = next(c for c in _load("courses.json")["courses"] if c["id"] == info["course_id"])
    if mentee == "M3":
        m3 = _load("pre_contact_M3.json")
        inputs, answers, done, handover = dict(m3["mentor_decisions"]), dict(m3["answers"]), 0, None
    else:  # M2: 멘토 교체
        expected = _load("sessions_M2.json")["expected_handover"]
        handover = {k: v for k, v in expected.items() if k != "must_not_include"}
        handover.update(case.get("handover_extra", {}))
        inputs = {"duration": "60", "weekday": "수", "start_datetime": "2026-10-14 19:00"}
        answers, done = {"subject_confirm": "영어, 오프라인 맞음", "goal": "문법 기본 다지기"}, 8
    for k in case.get("blank", []):
        inputs[k] = ""
    for k in case.get("blank_answers", []):
        answers[k] = ""
    extra = {"pre_contact": answers, "mode": info["mode"]}
    if handover:
        extra["handover"] = handover
    if not case.get("no_weekly_plan"):
        extra["weekly_plan"] = weekly_plan.write_lines(weekly_plan.allocate(course["units"], done), None)["sessions"]
    return inputs, extra


def _texts(draft: dict) -> list[tuple[str, str]]:
    out = []
    for k, v in draft.items():
        for item in (v if isinstance(v, list) else [v]):
            out.append((k, str(item)))
    return out


def score(form_id: str, case: dict, inputs: dict, extra: dict, res) -> dict:
    form = forms.engine.load_form(form_id)
    draft = res.draft
    asked = {q["key"] for q in res.missing_questions}
    expect_missing = set(case.get("expect_missing", []))
    absent = inputs.get("status") in ("무단결석", "인정결석")
    need = [f["key"] for f in form["fields"] if f.get("required") and f.get("source") != "placeholder" and not f.get("pii")
            and f["key"] not in expect_missing and not (absent and f["key"] != "session_content" and f["key"] in
                                                          ("scope", "goal", "lecture_progress", "homework", "progress_scale",
                                                           "understanding_scale", "actual_time"))]
    filled = [k for k in need if str(draft.get(k) or "").strip() and draft.get(k) != []]
    # 줄 머리 표시((1), (2) …)는 양식이 정한 형식이고 규칙으로 붙이는 것이라 지어낸 숫자로 보지 않는다
    sources = json.dumps([inputs, extra, [f.get("slot_marks") for f in form["fields"]]], ensure_ascii=False)
    llm_keys = {f["key"] for f in form["fields"] if f.get("source") in ("user_text", "llm_draft")}
    if form_id == "plan_initial":
        llm_keys -= {"structure", "rules", "curriculum"}  # 규칙으로 만든 칸은 지어내기 검사 대상이 아니다
    fabricated = [(k, n) for k, t in _texts(draft) if k in llm_keys for n in checks.unsupported_numbers(t, sources)]
    blob = json.dumps(res.to_dict(), ensure_ascii=False)
    exposed = [w for w in case.get("forbidden", []) if w in blob]
    exposed += [m for m in re.findall(r"01[016789][- .]?\d{3,4}[- .]?\d{4}", json.dumps(draft, ensure_ascii=False))]
    risk = []
    if form_id == "plan_initial":
        for k, t in _texts(draft):
            if t.startswith("["):
                continue
            if checks.plain_text(t)[0] != t:
                risk.append(f"{k}: 특수문자")
            if len(t) > 300:
                risk.append(f"{k}: {len(t)}자")
    not_empty = [k for k in case.get("expect_empty", []) if str(draft.get(k) or "").strip()]
    reminders = " ".join(res.reminders)
    return {"id": case["id"], "note": case.get("note"), "required": len(need), "filled": len(filled),
            "unfilled": sorted(set(need) - set(filled)), "fabricated": fabricated, "exposed": exposed, "platform_risk": risk,
            "reask_ok": asked == expect_missing, "asked": sorted(asked), "expect_missing": sorted(expect_missing),
            "should_be_empty_but_filled": not_empty,
            "missing_reminders": [w for w in case.get("expect_reminder", []) if w not in reminders],
            "format_error": bool(res.error), "warnings": len(res.warnings)}


def judge_draft(judge, form_id: str, inputs: dict, extra: dict, res) -> list[str]:
    """LLM이 쓴 칸만 채점한다. 자리표시, 멘토가 고른 값, 규칙으로 만든 칸(구성, 커리큘럼, 결석 문구)은 뺀다."""
    form = forms.engine.load_form(form_id)
    keys = [f["key"] for f in form["fields"] if f.get("source") in ("user_text", "llm_draft")]
    if form_id == "plan_initial":
        keys = [k for k in keys if k not in ("structure", "rules", "curriculum")]
    if inputs.get("status") in ("무단결석", "인정결석"):
        keys = [k for k in keys if k != "session_content"]
    written = {k: res.draft[k] for k in keys if str(res.draft.get(k) or "").strip() and res.draft[k] != forms.hooks_plan.LATER}
    if not written:
        return []
    given = {k: v for k, v in {**inputs, **{k: v for k, v in extra.items() if k != "weekly_plan"}}.items() if v not in ("", None)}
    user = f"[입력]\n{json.dumps(given, ensure_ascii=False, indent=1)}\n\n[초안]\n{json.dumps(written, ensure_ascii=False, indent=1)}"
    raw = judge.complete(JUDGE, user)
    try:
        return [str(x) for x in json.loads(re.search(r"\{.*\}", raw, re.S).group(0)).get("unsupported", [])]
    except Exception as e:  # 채점 형식 오류도 기록한다
        return [f"(채점 형식 오류: {type(e).__name__})"]


def run(llm, judge=None, cases_path: Path | None = None) -> dict:
    cases = json.loads((cases_path or ROOT / "eval" / "report_eval" / "cases.json").read_text(encoding="utf-8"))
    out = {"forms": {}}
    for form_id in ("activity_report", "plan_initial"):
        rows = []
        for case in cases[form_id]:
            inputs, extra = (activity_input(case), {}) if form_id == "activity_report" else plan_input(case, llm)
            res = forms.draft(form_id, inputs, llm, extra)
            row = score(form_id, case, inputs, extra, res)
            if judge is not None:
                row["judge_unsupported"] = judge_draft(judge, form_id, inputs, extra, res)
            rows.append(row)
        req, fil = sum(r["required"] for r in rows), sum(r["filled"] for r in rows)
        out["forms"][form_id] = {
            "n": len(rows), "fill_rate": round(100 * fil / max(req, 1), 1), "required": req, "filled": fil,
            "fabricated": sum(len(r["fabricated"]) for r in rows), "exposed": sum(len(r["exposed"]) for r in rows),
            "platform_risk": sum(len(r["platform_risk"]) for r in rows),
            "reask_accuracy": round(100 * sum(r["reask_ok"] for r in rows) / len(rows), 1),
            "should_be_empty_but_filled": sum(len(r["should_be_empty_but_filled"]) for r in rows),
            "missing_reminders": sum(len(r["missing_reminders"]) for r in rows),
            "format_errors": sum(r["format_error"] for r in rows),
            "judge_unsupported": sum(len(r.get("judge_unsupported", [])) for r in rows) if judge is not None else None,
            "cases": rows}
    return out


def to_markdown(s: dict, llm_name: str, judge_name: str | None) -> str:
    lines = ["# 보고서 초안 평가 (1-D-8)", "", f"- 초안 모델: `{llm_name}`" + (f", 채점 모델: `{judge_name}`" if judge_name else ""),
             "- 사례: `eval/report_eval/cases.json` (가상 데이터)", "",
             "| 양식 | 사례 | 필수 항목 채움률 | 지어내기(숫자·날짜) | 개인정보·민감 내용 노출 | 플랫폼 입력 위험 | 되묻기 정확도 | 비워야 할 칸을 채움 | 빠진 안내 | 형식 오류 | LLM 채점: 근거 없는 내용 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    names = {"activity_report": "활동보고서", "plan_initial": "종합계획서①"}
    for fid, f in s["forms"].items():
        j = "-" if f["judge_unsupported"] is None else f"{f['judge_unsupported']}건"
        lines.append(f"| {names[fid]} | {f['n']}건 | {f['fill_rate']}% ({f['filled']}/{f['required']}) | {f['fabricated']}건 | {f['exposed']}건 | "
                     f"{f['platform_risk']}건 | {f['reask_accuracy']}% | {f['should_be_empty_but_filled']}건 | {f['missing_reminders']}건 | "
                     f"{f['format_errors']}건 | {j} |")
    lines += ["", "## 사례별", "", "| 사례 | 내용 | 채움 | 문제 |", "| --- | --- | --- | --- |"]
    for f in s["forms"].values():
        for r in f["cases"]:
            issues = []
            for key, label in (("unfilled", "안 채움"), ("fabricated", "지어낸 숫자"), ("exposed", "노출"), ("platform_risk", "플랫폼 위험"),
                               ("should_be_empty_but_filled", "비워야 할 칸"), ("missing_reminders", "빠진 안내"),
                               ("judge_unsupported", "채점 지적")):
                if r.get(key):
                    issues.append(f"{label}: {r[key]}")
            if not r["reask_ok"]:
                issues.append(f"되묻기 다름: 기대 {r['expect_missing']}, 실제 {r['asked']}")
            lines.append(f"| {r['id']} | {r['note']} | {r['filled']}/{r['required']} | {'; '.join(issues) or '없음'} |")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fake", action="store_true")
    p.add_argument("--judge", action="store_true")
    a = p.parse_args()
    llm = FakeLLM() if a.fake else get_eval_model("answer")
    judge = get_eval_model("judge") if a.judge and not a.fake else None
    s = run(llm, judge)
    (ROOT / "eval" / "runs").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / "runs" / "report_eval.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    md = to_markdown(s, llm.name, judge.name if judge else None)
    if not a.fake:
        (ROOT / "eval" / "reports" / "report_eval.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
