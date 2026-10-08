"""써 보기용 예시 자료(멘티 4명)를 보관함 파일 형식으로 만든다. 가상 데이터(synthetic/)만 쓴다.

  docker compose run --rm ai-server python /project/scripts/make_demo_vault.py
  cp eval/runs/demo_vault.json frontend/public/demo_vault.json

실제 LLM으로 활동보고서 초안 30건과 종합계획서 초안을 만든다 (평가용 캐시를 쓴다).
화면의 내 멘티 > '예시 멘티 불러오기'가 이 파일을 브라우저 보관함으로 가져온다.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai-server"))

from app import forms  # noqa: E402
from app.config import settings  # noqa: E402
from app.forms import weekly_plan  # noqa: E402
from app.llm import get_eval_model  # noqa: E402

SYN = settings.root / "synthetic"
load = lambda name: json.loads((SYN / name).read_text(encoding="utf-8"))  # noqa: E731
COURSES = {c["id"]: c for c in load("courses.json")["courses"]}
# 별칭, 기본 정보. 이름·학년·학교·연락처는 넣지 않는다
MENTEES = {
    "M1": {"alias": "수학 A (회기 마무리)", "sessions": "sessions_M1.json", "profile": {
        "subject": "수학", "mode": "온라인", "duration": "60", "weekday": "월", "start_datetime": "2026-03-09T17:00",
        "goal": "시발점 수1 완강, 기말고사 수학 3등급, 오답노트 습관", "level": "인강 의존도가 높고 오답 정리를 미루는 편"}},
    "M2": {"alias": "영어 B (멘토 교체 예정)", "sessions": "sessions_M2.json", "profile": {
        "subject": "영어", "mode": "오프라인", "duration": "60", "weekday": "수", "start_datetime": "2026-03-11T19:00",
        "goal": "문법 기본 다지기, 단어 암기 습관", "level": "문법 인강은 꾸준히 듣고 단어 과제를 자주 덜 해 옴"}},
    "M3": {"alias": "국어 C (매칭 직후)", "sessions": None, "profile": {
        "subject": "국어", "mode": "온라인", "duration": "60", "weekday": "월", "start_datetime": "2026-10-12T20:00",
        "goal": "문학 감 잡기, 인강 끝까지 듣기", "level": "문학이 특히 약하다고 함. 강좌는 신청만 하고 아직 안 들음"}},
    "M4": {"alias": "수학 D (결석이 있는 회기)", "sessions": "sessions_M4.json", "profile": {
        "subject": "수학", "mode": "오프라인", "duration": "60", "weekday": "토", "start_datetime": "2026-08-29T10:00",
        "goal": "다음 검정고시 합격", "level": "아르바이트로 지각과 결석이 있었음"}},
}
seq = 0


def item(alias: str, form_id: str, title: str, saved: date, draft: dict, inputs: dict | None = None, extra: dict | None = None, session_no=None) -> dict:
    global seq
    seq += 1
    return {"id": f"demo-{seq:03d}", "alias": alias, "formId": form_id, "title": title, "sessionNo": session_no,
            "savedAt": f"{saved.isoformat()}T12:00:00.000Z", "inputs": inputs or {}, "extra": extra or {}, "draft": draft}


def main():
    llm = get_eval_model("answer")
    info = {m["id"]: m for m in load("mentees.json")["mentees"]}
    items = []
    for mid, cfg in MENTEES.items():
        alias, course = cfg["alias"], COURSES[info[mid]["course_id"]]
        course_name = f"{course['site']} {course['title']}"
        profile = {**cfg["profile"], "course": course_name}
        start = date.fromisoformat(profile["start_datetime"][:10])
        items.append(item(alias, "mentee_profile", "멘티 정보", start - timedelta(days=5), profile))
        lectures = [{"no": u["no"], "title": u["title"], "unit": None, "minutes": None} for u in course["units"]]
        items.append(item("내 강좌", "course_outline", course_name, start - timedelta(days=5), {"lectures": lectures}))
        if not cfg["sessions"]:
            continue   # 매칭 직후: 기본 정보만 있다
        sessions = load(cfg["sessions"])["sessions"]
        # 종합계획서①
        plan = weekly_plan.write_lines(weekly_plan.allocate(course["units"], start_date=start), llm, {"과목": profile["subject"], "목표": profile["goal"]})
        decisions = {"duration": profile["duration"], "weekday": profile["weekday"], "start_datetime": profile["start_datetime"].replace("T", " ")}
        pre = {"subject_confirm": f"{profile['subject']}, {profile['mode']}", "site_course": course_name, "goal": profile["goal"], "level": profile["level"]}
        r = forms.draft("plan_initial", decisions, llm, {"pre_contact": pre, "weekly_plan": plan["sessions"], "mode": profile["mode"]})
        items.append(item(alias, "plan_initial", "종합계획서①", start - timedelta(days=2), r.draft, decisions, {"weekly_plan": plan["sessions"]}))
        print(f"{mid} 종합계획서① error={r.error}", flush=True)
        for s in sessions:
            inp = {"session_date": s["date"], "session_no": str(s["session_no"]), "subject": profile["subject"], "course": course_name,
                   "status": s["status"], **{k: v for k, v in s["mentor_input"].items() if k != "notes"},
                   "session_content": s["mentor_input"].get("notes", "")}
            r = forms.draft("activity_report", dict(inp), llm)
            # 보관함에 남는 입력도 가린 것으로 둔다 (예시 자료에 가짜 이름·전화번호가 그대로 남지 않게)
            from app import guard
            masked = {k: (guard.check(v).text if isinstance(v, str) else v) for k, v in inp.items()}
            items.append(item(alias, "activity_report", f"활동보고서 {s['session_no']}회차", date.fromisoformat(s["date"]) + timedelta(days=2),
                              r.draft, masked, session_no=s["session_no"]))
            print(f"{mid} {s['session_no']}회차 error={r.error} warnings={len(r.warnings)}", flush=True)
    out = {"format": "seoullearn-mentor-vault", "version": 1, "exportedAt": "2026-10-08T00:00:00.000Z", "sample": True, "items": items}
    path = settings.root / "eval" / "runs" / "demo_vault.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {path} ({len(items)}건)")


if __name__ == "__main__":
    main()
