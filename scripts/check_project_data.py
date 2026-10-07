"""양식 스키마와 가상 데이터 검사.

- forms/*.json: 필수 속성, source 값, checklist 번호, 인계 allowlist가 실제 필드를 가리키는지
- synthetic/*: 회차 번호·날짜 순서, 실제 진행시간이 09:00~22:00 안인지, 강좌 존재,
  출석 회차에 활동보고서 필수 입력이 다 있는지
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
SOURCES = {"user", "user_text", "llm_draft", "derived", "placeholder"}
CHECKLIST = {f"1-{i}" for i in range(1, 8)} | {f"2-{i}" for i in range(1, 7)} | {f"3-{i}" for i in range(1, 6)}
# 멘토 입력 화면의 칸 이름 → 활동보고서 필드 (자유 메모가 '학습이해도 - 멘토링 학습 내용'의 재료)
INPUT_ALIAS = {"session_content": "notes"}
TIME = re.compile(r"^(\d{2}):(\d{2})~(\d{2}):(\d{2})$")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    errors = []
    forms = {}
    for f in sorted((ROOT / "forms").glob("*.json")):
        d = load(f)
        forms[d["form_id"]] = d
        for fld in d.get("fields", []):
            for k in ("key", "label", "type", "required", "source"):
                if k not in fld:
                    errors.append(f"{f.name}:{fld.get('key')} 속성 누락 {k}")
            if fld.get("source") not in SOURCES:
                errors.append(f"{f.name}:{fld.get('key')} source 값 오류 {fld.get('source')}")
            for c in fld.get("checklist", []):
                if c not in CHECKLIST:
                    errors.append(f"{f.name}:{fld['key']} 체크리스트 번호 오류 {c}")
            if fld.get("pii") and fld.get("source") != "placeholder":
                errors.append(f"{f.name}:{fld['key']} 개인정보인데 placeholder 아님")
    keys = {fid: {x["key"] for x in d.get("fields", [])} for fid, d in forms.items()}
    ho = forms.get("handover_summary", {})
    for part in ho.get("allow", []) + ho.get("deny", []):
        for ref in part.get("from", []):
            fid, _, key = ref.partition(".")
            if key not in keys.get(fid, set()):
                errors.append(f"handover_summary: 없는 필드 참조 {ref}")
    allow_src = {ref for p in ho.get("allow", []) for ref in p["from"]}
    for key in keys.get("activity_report", set()):
        fld = next(x for x in forms["activity_report"]["fields"] if x["key"] == key)
        if fld.get("handover") == "deny" and f"activity_report.{key}" in allow_src:
            errors.append(f"handover_summary: deny 필드를 allow에서 사용 {key}")

    courses = {c["id"]: c for c in load(ROOT / "synthetic/courses.json")["courses"]}
    mentees = {m["id"]: m for m in load(ROOT / "synthetic/mentees.json")["mentees"]}
    for m in mentees.values():
        if m["course_id"] not in courses:
            errors.append(f"{m['id']}: 없는 강좌 {m['course_id']}")
    required = [x["key"] for x in forms["activity_report"]["fields"] if x["required"] and x["source"] in ("user", "user_text") and x["key"] not in ("session_date", "session_no", "subject", "course")]
    total = 0
    for f in sorted((ROOT / "synthetic").glob("sessions_*.json")):
        d = load(f)
        prev_no, prev_date = 0, None
        for s in d["sessions"]:
            total += 1
            tag = f"{d['mentee_id']}-{s['session_no']}"
            if s["session_no"] != prev_no + 1:
                errors.append(f"{tag}: 회차 번호 건너뜀")
            dt = date.fromisoformat(s["date"])
            if prev_date and dt <= prev_date:
                errors.append(f"{tag}: 날짜 순서 오류")
            prev_no, prev_date = s["session_no"], dt
            mi = s["mentor_input"]
            if s["status"] in ("출석", "지각"):
                m = TIME.match(mi["actual_time"])
                if not m:
                    errors.append(f"{tag}: 시간 형식 오류 {mi['actual_time']}")
                else:
                    h1, m1, h2, m2 = map(int, m.groups())
                    start, end = h1 * 60 + m1, h2 * 60 + m2
                    if start < 9 * 60 or end > 22 * 60:
                        errors.append(f"{tag}: 09:00~22:00 밖 {mi['actual_time']}")
                    if end - start < 60:
                        errors.append(f"{tag}: 60분 미만 {mi['actual_time']}")
                for k in required:
                    if not mi.get(INPUT_ALIAS.get(k, k)):
                        errors.append(f"{tag}: 필수 입력 비어 있음 {k}")
    m3 = load(ROOT / "synthetic/pre_contact_M3.json")
    if m3["course_id"] not in courses:
        errors.append("M3: 없는 강좌")

    print(f"양식 {len(forms)}개, 가상 멘티 {len(mentees)}명, 회차 기록 {total}건, 강좌 {len(courses)}개")
    for e in errors:
        print("ERROR", e)
    print("OK" if not errors else f"{len(errors)}개 오류")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
