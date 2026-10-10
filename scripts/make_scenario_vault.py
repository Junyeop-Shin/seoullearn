"""AI 다듬기 확인용 멘티 자료를 만든다 (docs/ai_polish_check.md의 시나리오를 바로 따라 할 수 있게).

지어낸 멘티 다섯 명을 시나리오가 시작하는 지점에 맞춰 둔다. LLM을 부르지 않고, 실제 인물 정보는 없다.
결과: frontend/public/scenario_vault.json (내 멘티 화면의 '확인용 멘티 불러오기'가 읽는다)

  python scripts/make_scenario_vault.py
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRUCTURE = ["{0}:00~{0}:10 온라인 강의 수강(필수) 확인 및 퀴즈", "{0}:10~{0}:30 개념학습", "{0}:30~{0}:40 개념 테스트", "{0}:40~{0}:50 오답 풀이", "{0}:50~{1}:00 상담 및 다음 회차 안내"]
RULES = ["멘토링 시간 준수하기", "일정 변경은 최소 3일 전에 논의하기", "인강은 계획대로 규칙적으로 수강하고 인증 사진 보내기", "과제는 답지를 보지 않고 스스로 풀기", "개념은 확실히 이해하고 오답 노트 반드시 작성하기"]
HANDOVER = """안녕하세요, 이전 멘토입니다. 인계 내용 정리해서 보내드립니다.
[출석 패턴] 대체로 정시에 출석함. 시험 기간에 일정 변경 요청이 두 번 있었음.
[과제 수행] 인강은 꾸준히 듣지만 문제 풀이 과제는 자주 덜 해 옴.
[학업 수준] 지난 중간고사 수학 58점, 함수 단원 이해가 많이 부족함.
[학습 태도] 집중 시간이 짧아 30분쯤 지나면 쉬는 시간을 한 번 주는 편이 좋았음.
[상담 내용] 부모님과 진로 문제로 갈등이 있다고 여러 번 이야기함.
[수강 강의와 진도] 메가스터디 시발점 수1, 12강까지 수강함."""
items: list[dict] = []


def add(alias: str, form_id: str, title: str, saved: str, draft: dict, inputs: dict | None = None, extra: dict | None = None, session_no=None) -> None:
    items.append({"id": f"scn-{len(items) + 1:03d}", "alias": alias, "formId": form_id, "title": title, "sessionNo": session_no,
                  "savedAt": f"{saved}T12:00:00.000Z", "inputs": inputs or {}, "extra": extra or {}, "draft": draft})


def profile(name: str, grade: str, subject: str, district: str, mode: str, start: str, stage: str, **over) -> dict:
    hh = start[11:16]
    p = {"name": name, "grade": grade, "subject": subject, "subjectEtc": "", "district": district, "mode": mode, "duration": "60", "course": "",
         "start_datetime": start, "venue": "", "goal": "", "level": "", "weekday": "", "regularSchedule": [{"weekday": "일월화수목금토"[(date.fromisoformat(start[:10]).weekday() + 1) % 7], "startTime": hh}],
         "term": 1, "currentRound": 1, "stage": stage, "archived": False, "lastHomework": None}
    p.update(over)
    return p


def rows(start: str, contents: list[tuple[str, str, str]], n: int = 16) -> list[dict]:
    """커리큘럼 표 n주. contents: 주차별 (학습 내용, 온라인 강의, 멘토링 내용)"""
    d0, hh = date.fromisoformat(start[:10]), start[11:16]
    out = []
    for i in range(n):
        c, o, m = contents[i] if i < len(contents) else ("", "", "")
        out.append({"week": i + 1, "date": (d0 + timedelta(days=7 * i)).isoformat(), "time": hh, "edited": False, "content": c, "online": o, "mentoring": m, "course": 0})
    return out


def plan_initial(alias: str, start: str, goal: str, diag: str, weeks: list[tuple[str, str, str]], saved: str) -> list[dict]:
    hour = int(start[11:13])
    structure = "\n".join(x.format(hour, hour + 1) for x in STRUCTURE)
    r = rows(start, weeks)
    lines = [f"{x['week']}주차({int(x['date'][5:7])}/{int(x['date'][8:10])} {x['time']}) {x['content']}" for x in r if x["content"]]
    inputs = {"duration": "60", "weekday": "일월화수목금토"[(date.fromisoformat(start[:10]).weekday() + 1) % 7], "start_datetime": start.replace("T", " ")}
    memo = {"learning_goal": goal, "diagnosis": diag, "structure": structure, "rules": "\n".join(RULES)}
    add(alias, "plan_initial", "종합계획서①", saved, {**inputs, **memo, "curriculum": lines}, inputs, {"memo": memo, "rows": r})
    return r


# 1. 정가상: 인계받은 멘티, 종합계획서①을 아직 쓰지 않음 (시나리오 1~8)
add("정가상", "mentee_profile", "멘티 정보", "2026-10-09", profile("정가상", "고1", "수학", "성북구", "온라인", "2026-11-02T17:00", "PLAN"))
add("정가상", "handover_summary", "인계 요약", "2026-10-09", {
    "attendance_pattern": "대체로 정시에 출석함. 시험 기간에 일정 변경 요청이 두 번 있었음.", "homework_pattern": "인강은 꾸준히 듣지만 문제 풀이 과제는 자주 덜 해 옴.",
    "attitude": "집중 시간이 짧아 30분쯤 지나면 쉬는 시간을 한 번 주는 편이 좋았음.", "course_progress": "메가스터디 시발점 수1, 12강까지 수강함.", "text": HANDOVER})

# 2. 한가상: 종합계획서①을 저장했고 1회차를 마침. 종합계획서②를 쓸 차례 (시나리오 9)
START2 = "2026-10-06T19:00"
add("한가상", "mentee_profile", "멘티 정보", "2026-10-01", profile("한가상", "중2", "영어", "관악구", "온라인", START2, "PLAN", course="밀크T 중2 영어 문법 기본",
                                                           goal="(1) 밀크T 중2 영어 문법 기본 완강\n(2) 2학기 기말고사 문법 문제 다 맞기", level="(과목역량) 단어는 아는 편이나 문장 구조를 어려워함\n(학습습관 및 태도) 인강은 꾸준히 듣는 편임"))
plan_initial("한가상", START2, "(1) 밀크T 중2 영어 문법 기본 완강\n(2) 2학기 기말고사 문법 문제 다 맞기", "(과목역량) 단어는 아는 편이나 문장 구조를 어려워함\n(학습습관 및 태도) 인강은 꾸준히 듣는 편임",
             [("오리엔테이션, 현재 수준 진단", "", ""), ("to부정사 - 개념", "", ""), ("to부정사 - 문제 풀이", "", ""), ("동명사 - 개념", "", "")], "2026-10-02")

# 3. 오가상: 2회차까지 활동보고서를 썼고 3회차를 쓸 차례 (시나리오 10)
START3 = "2026-09-28T17:00"
WEEKS3 = [("오리엔테이션, 현재 수준 진단", "1~2강", "오리엔테이션(OT), 유리수와 순환소수 개념"), ("유리수와 순환소수", "3~4강", "순환소수를 분수로 나타내기"),
          ("식의 계산", "5~6강", "지수법칙 개념과 문제 풀이"), ("식의 계산", "7~8강", "단항식의 곱셈과 나눗셈")]
add("오가상", "mentee_profile", "멘티 정보", "2026-09-22", profile("오가상", "중2", "수학", "노원구", "온라인", START3, "ACTIVITY", currentRound=3, course="밀크T 중2 수학 개념 기본",
                                                           goal="① 밀크T 중2 수학 개념 기본 완강\n② 2학기 중간고사 대비 1학기 내용 복습", level="(과목역량) 계산은 빠르나 부호 실수가 잦음"))
r3 = plan_initial("오가상", START3, "(1) 밀크T 중2 수학 개념 기본 완강\n(2) 2학기 중간고사 대비 1학기 내용 복습", "(과목역량) 계산은 빠르나 부호 실수가 잦음", WEEKS3, "2026-09-24")
add("오가상", "plan_file", "종합계획서②", "2026-09-30", {
    "period": "2026.09.28.~2027.01.11.", "mentee": "[멘티 학년]", "mentor": "[멘토 성명·소속]", "subject_time": "수학 / 밀크T 중2 수학 개념 기본(가상 강사) / 매주 월 17:00~18:00",
    "learning_goal": ["① 밀크T 중2 수학 개념 기본 완강", "② 2학기 중간고사 대비 1학기 내용 복습"], "diagnosis": ["(과목역량) 계산은 빠르나 부호 실수가 잦음"],
    "curriculum": [f"{x['week']}주차({int(x['date'][5:7])}/{int(x['date'][8:10])} {x['time']})\n(온라인강의) 중2 수학 개념 기본(가상 강사), {x['online']}\n(멘토링 내용) {x['mentoring']}" for x in r3 if x["online"]],
    "structure": [x.format(17, 18).replace(" 및 ", " & ") for x in STRUCTURE], "rules": RULES},
    {"subject_time": "수학 / 밀크T 중2 수학 개념 기본(가상 강사) / 매주 월 17:00~18:00"},
    {"courses": [{"platform": "밀크T", "lecture": "중2 수학 개념 기본", "instructor": "가상 강사", "done": "", "lectures": []}], "common": {"subject": "수학", "schedule": "매주 월 17:00~18:00"},
     "alloc": {"mode": "weekly", "perWeek": 2, "target": ""}, "value": {"learning_goal": "① 밀크T 중2 수학 개념 기본 완강\n② 2학기 중간고사 대비 1학기 내용 복습", "diagnosis": "(과목역량) 계산은 빠르나 부호 실수가 잦음",
                                                                      "structure": "\n".join(x.format(17, 18) for x in STRUCTURE), "rules": "\n".join(RULES)},
     "changed": {"learning_goal": False, "diagnosis": False, "structure": False, "rules": False}, "rows": r3})
for no, (day, scope, goal, content, hw) in enumerate([
        ("2026-09-28", "1~2강 유리수와 순환소수", "유리수와 순환소수 개념 이해", "유리수와 순환소수의 뜻을 설명하고 예제를 함께 풂.", {"lecture": "3~4강", "task": "3강 예제 풀기"}),
        ("2026-10-05", "3~4강 순환소수를 분수로 나타내기", "순환소수를 분수로 바꾸기", "순환소수를 분수로 나타내는 방법을 연습함. 예제는 혼자 풀었음.", {"lecture": "5~6강", "task": "5강 예제 풀기"})], 1):
    inp = {"status": "출석", "session_date": day, "session_no": str(no), "subject": "수학", "course": "밀크T 중2 수학 개념 기본", "actual_time": "17:02~18:03", "scope": scope, "goal": goal,
           "progress_scale": "잘함", "understanding_scale": "보통", "attendance": "정시 출석", "lecture_progress": "지난 회차 인강: 다 들음" if no > 1 else "", "homework": "지난 회차 과제: 함" if no > 1 else "",
           "session_content": content, "etc": "", "requests": ""}
    add("오가상", "activity_report", f"활동보고서 {no}회차", day, {"mentee_name": "[멘티명]", "mentee_grade": "[멘티 학년]", "mentor": "[멘토 성명·소속]", **{k: v for k, v in inp.items() if k != "status"}},
        inp, {"assignedHomework": hw}, no)

# 4. 이가상: 1회기를 마치고 2회기를 시작함. 지난 회기 요약이 있다 (시나리오 11)
add("이가상", "mentee_profile", "멘티 정보", "2026-10-08", profile("이가상", "고1", "수학", "송파구", "온라인", "2026-11-03T20:00", "PLAN", term=2, course="메가스터디 시발점 수2",
                                                           goal="", level=""))
add("이가상", "term_summary", "1회기 요약", "2026-10-08", {
    "term": 1, "rounds": 16, "course": "메가스터디 시발점 수1", "goal": ["① 메가스터디 시발점 수1 완강", "② 기말고사 수학 3등급"], "last_scope": "30강 수열의 합 총정리",
    "next_homework": {"lecture": "시발점 수2 1~2강", "task": "수1 오답 노트 다시 풀기"}, "next_course": "메가스터디 시발점 수2",
    "content": ["지수와 로그, 삼각함수, 수열 단원의 개념을 인강과 함께 정리하고 단원마다 오답 노트를 만듦."], "achievement": ["시발점 수1 30강을 모두 수강함. 오답 노트 작성은 후반부에 자리 잡음."]})

# 6. 서가상(60분, 16주)·팔가상(120분, 8주): 종합계획서②를 끝까지 적어 저장해 둠. 멘티를 열면 ② 탭이 뜨고, 바로 '서식 파일로 내보내기'를 눌러 볼 수 있다
UNITS16 = ["지수", "지수", "로그", "로그", "상용로그", "지수함수", "지수함수의 활용", "로그함수", "로그함수의 활용", "일반각과 호도법", "삼각함수의 뜻", "삼각함수의 그래프", "삼각방정식과 부등식", "사인법칙과 코사인법칙", "등차수열과 등비수열", "수열의 합"]
UNITS8 = ["다항식의 연산", "나머지정리와 인수분해", "복소수", "이차방정식", "이차방정식과 이차함수", "여러 가지 방정식", "연립부등식", "이차부등식"]


def plan_file(alias: str, grade: str, start: str, minutes: int, course: dict, goal: list[str], diag: list[str], units: list[str]) -> None:
    n = len(units)
    hour = int(start[11:13])
    wd = "일월화수목금토"[(date.fromisoformat(start[:10]).weekday() + 1) % 7]
    schedule = f"매주({wd}) {hour}:00~{hour + minutes // 60}:00"
    add(alias, "mentee_profile", "멘티 정보", "2026-10-05", profile(alias, grade, "수학", "강남구", "온라인", start, "PLAN", duration=str(minutes), course=f"{course['platform']} {course['lecture']}", goal="\n".join(goal)))
    weeks = [(u, f"{2 * i + 1}~{2 * i + 2}강", ("오리엔테이션(OT), " if i == 0 else "") + f"{u} 개념학습 및 확인 테스트") for i, u in enumerate(units)]
    plain = "\n".join(g.replace("①", "(1)").replace("②", "(2)").replace("③", "(3)").replace("④", "(4)") for g in goal)
    r = plan_initial(alias, start, plain, "\n".join(diag), weeks, "2026-10-06")[:n]
    # 120분이면 서식 예시의 시간 배분을 두 배로
    u = minutes // 6
    marks = [0, u, 3 * u, 4 * u, 5 * u, 6 * u]
    clock = lambda m: f"{hour + m // 60}:{m % 60:02d}"
    names = ["온라인 강의 수강(필수) 확인 & 퀴즈", "개념학습", "개념 테스트", "오답 풀이", "상담 및 다음 회차 안내"]
    structure = [f"{clock(marks[i])}~{clock(marks[i + 1])} {names[i]}" for i in range(5)]
    name = f"{course['lecture']}({course['instructor']})"
    subject_time = f"수학 / {course['platform']} {name} / {schedule}"
    cells = [f"{x['week']}주차({int(x['date'][5:7])}/{int(x['date'][8:10])} {x['time']})\n(온라인강의) {name}, {x['online']}\n(멘토링 내용) {x['mentoring']}" for x in r]
    last = date.fromisoformat(r[-1]["date"])
    draft = {"period": f"{start[:10].replace('-', '.')}.~{last.isoformat().replace('-', '.')}.", "mentee": "[멘티 학년]", "mentor": "[멘토 성명·소속]", "subject_time": subject_time,
             "learning_goal": goal, "diagnosis": diag, "curriculum": cells, "structure": structure, "rules": RULES}
    value = {"learning_goal": "\n".join(goal), "diagnosis": "\n".join(diag), "structure": "\n".join(structure), "rules": "\n".join(RULES)}
    add(alias, "plan_file", "종합계획서②", "2026-10-08", draft, {"subject_time": subject_time},
        {"courses": [{**course, "lectures": [], "done": ""}], "common": {"subject": "수학", "schedule": schedule}, "alloc": {"mode": "weekly", "perWeek": 2, "target": ""},
         "value": value, "defaults": {"structure": value["structure"]}, "rows": r})


plan_file("서가상", "고2", "2026-10-12T17:00", 60, {"platform": "메가스터디", "lecture": "수학의 시작, 시발점 - 대수", "instructor": "가상 강사"},
          ["① 메가스터디 수학의 시작, 시발점 - 대수 완강", "② 대수 1회독 완료, 기말고사 수학 3등급", "③ 매일 학습플래너 작성하기, 인강은 하루에 2강씩 규칙적으로 듣기", "④ 목표 대학 입시 정보 찾아보기"],
          ["(과목역량) 수학의 기본기는 갖추고 있으나 고득점 문제의 해결 능력은 낮음", "(학습수준 및 희망진로) 내신은 평균 4등급이며 희망 전공은 경찰행정학과", "(입시준비) 대학별 입학 전형과 입시 정보가 거의 없음", "(학습습관 및 태도) 학원과 인강 의존도가 높고 자율학습 수준은 낮은 편임"], UNITS16)
plan_file("팔가상", "고1", "2026-10-14T18:00", 120, {"platform": "이투스", "lecture": "공통수학1 개념 완성", "instructor": "가상 강사"},
          ["① 이투스 공통수학1 개념 완성 완강", "② 공통수학1 교과서 문제 1회독", "③ 오답 노트를 회차마다 작성하기"],
          ["(과목역량) 계산은 정확하나 서술형 풀이 과정을 자주 건너뜀", "(학습습관 및 태도) 과제는 꾸준히 해 오는 편이며 질문이 많음"], UNITS8)

# 5. 마가상: 오프라인 멘티. 오프라인 일정·장소 화면 확인용
add("마가상", "mentee_profile", "멘티 정보", "2026-09-10", profile("마가상", "중3", "영어", "마포구", "오프라인", "2026-09-14T17:00", "ACTIVITY", currentRound=5, course="밀크T 중3 영어 문법"))

out = {"format": "seoullearn-mentor-vault", "version": 1, "exportedAt": "2026-10-11T00:00:00.000Z", "sample": True,
       "mentor": {"name": "이멘토", "phone": "010-0000-0000", "mentoringType": "시급형", "university": "가상대학교", "major": "수학교육과"}, "items": items}
path = ROOT / "frontend" / "public" / "scenario_vault.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"저장: {path} ({len(items)}건, 멘티 {len({x['alias'] for x in items})}명)")
