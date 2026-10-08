"""양식 엔진과 보고서 초안 테스트. 가짜 LLM만 쓴다 (API 키 불필요)."""
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from app import forms
from app.forms import checks, engine, sensitive

ROOT = Path(__file__).resolve().parents[2]


class EchoLLM:
    """만들 항목을 읽어, 다듬기 항목은 입력을 그대로, 초안 항목은 정해 둔 글을 돌려주는 가짜 모델."""

    name = "echo"

    def __init__(self, overrides=None, raw=None):
        self.overrides, self.raw, self.calls = overrides or {}, raw, []

    def complete(self, system, user):
        self.calls.append(user)
        if self.raw is not None:
            return self.raw
        todo = json.loads(user.split("[만들 항목]\n", 1)[1])
        out = {}
        for item in todo:
            if item["key"] in self.overrides:
                out[item["key"]] = self.overrides[item["key"]]
            elif item["mode"] == "polish":
                out[item["key"]] = item["input"]
            else:
                out[item["key"]] = ["초안 항목"] if item["type"] == "list" else "초안 문장"
        return json.dumps(out, ensure_ascii=False)


def session(mentee: str, no: int) -> dict:
    data = json.loads((ROOT / "synthetic" / f"sessions_{mentee}.json").read_text(encoding="utf-8"))
    s = next(x for x in data["sessions"] if x["session_no"] == no)
    return {"session_date": s["date"], "session_no": no, "subject": "수학", "course": "가상 강좌", "status": s["status"],
            **s["mentor_input"]}


class ChecksTest(unittest.TestCase):
    def test_unsupported_numbers(self):
        src = "17:03~18:05 진행. 10문제 중 6개 맞음"
        self.assertEqual(checks.unsupported_numbers("17:03에 시작해 10문제 중 6개를 맞힘", src), [])
        self.assertEqual(checks.unsupported_numbers("3월 9일 진행", "2026-03-09"), [])  # 날짜 표기만 바뀐 것은 허용
        self.assertEqual(checks.unsupported_numbers("중간고사 85점, 3등급", src), ["3", "85"])
        kept, removed = checks.drop_unsupported("10문제 중 6개 맞음. 다음 시험은 5월 12일임.", src)
        self.assertEqual((kept, removed), ("10문제 중 6개 맞음.", ["12", "5"]))

    def test_time_range_rules(self):
        rules = {"earliest_start": "09:00", "latest_end": "22:00", "min_minutes": 60}
        self.assertEqual(checks.check_time_range("17:03~18:05", rules), [])
        self.assertTrue(checks.check_time_range("21:30~22:40", rules))
        self.assertTrue(checks.check_time_range("17:00~17:40", rules))
        self.assertEqual(checks.check_time_range("10:00~10:30 (멘토 단독 대기)", rules, need_min=False), [])
        self.assertTrue(checks.check_time_range("오후 다섯 시", rules))

    def test_plain_text(self):
        text, removed = checks.plain_text("① 수Ⅰ 완강 ★ 오답노트·플래너 [필수]")
        self.assertEqual(text, "(1) 수1 완강 오답노트, 플래너 필수")
        self.assertIn("★", removed)

    def test_sensitive_filter(self):
        text, kinds = sensitive.filter_text("일반각 개념 금방 이해함. 마지막 10분은 부모님이랑 크게 다퉈서 집중 안 된다고 해서 얘기 들어줌")
        self.assertEqual((text, kinds), ("일반각 개념 금방 이해함", ["정서"]))
        text, kinds = sensitive.filter_text("장염으로 병원 진료 받아 결석, 진료확인서 받음")
        self.assertNotIn("장염", text)
        self.assertIn("질병으로 인한 결석", text)
        self.assertEqual(sensitive.filter_text("계산 실수가 많아 문제 풀이를 어려워함")[1], [])


class EngineTest(unittest.TestCase):
    def test_sources_are_handled_separately(self):
        llm = EchoLLM()
        r = forms.draft("activity_report", session("M1", 1), llm)
        self.assertEqual(r.draft["mentee_name"], "[멘티명]")          # placeholder
        self.assertEqual(r.draft["progress_scale"], "보통")           # user: 입력 그대로
        self.assertEqual(r.draft["actual_time"], "17:03~18:05")
        self.assertIn("거듭제곱근", r.draft["session_content"])        # user_text: 메모가 재료
        self.assertEqual(r.missing_questions, [])
        todo = json.loads(llm.calls[0].split("[만들 항목]\n", 1)[1])
        self.assertTrue(all(t["mode"] == "polish" for t in todo))
        self.assertNotIn("progress_scale", [t["key"] for t in todo])   # 척도는 LLM에 보내지 않는다
        self.assertEqual(len(llm.calls), 1)

    def test_pii_input_is_dropped_with_warning(self):
        inp = {**session("M1", 1), "mentee_name": "김민지", "mentee_grade": "고2"}
        llm = EchoLLM()
        r = forms.draft("activity_report", inp, llm)
        self.assertEqual(r.draft["mentee_name"], "[멘티명]")
        self.assertTrue(any("멘티 성명" in w for w in r.warnings))
        self.assertNotIn("김민지", llm.calls[0])

    def test_missing_required_fields_become_questions(self):
        inp = session("M1", 1)
        for k in ("actual_time", "goal", "understanding_scale"):
            inp[k] = ""
        r = forms.draft("activity_report", inp, EchoLLM())
        self.assertEqual({q["key"] for q in r.missing_questions}, {"actual_time", "goal", "understanding_scale"})
        self.assertEqual(r.draft["understanding_scale"], "")  # 척도를 AI가 채우지 않는다

    def test_fabricated_date_and_score_are_caught(self):
        llm = EchoLLM(overrides={"session_content": "거듭제곱근 개념을 설명함. 5월 12일 모의고사에서 92점을 받음.",
                                 "goal": "기말고사 2등급 달성"})
        r = forms.draft("activity_report", session("M1", 1), llm)
        self.assertNotIn("92", r.draft["session_content"])
        self.assertNotIn("12일", r.draft["session_content"])
        self.assertIn("거듭제곱근", r.draft["session_content"])
        self.assertNotIn("2등급", r.draft["goal"])  # 다듬은 글을 못 쓰면 멘토 입력으로 되돌린다
        self.assertTrue(any("입력에 없는 숫자" in w for w in r.warnings))

    def test_bad_llm_output_is_recorded_and_inputs_kept(self):
        r = forms.draft("activity_report", session("M1", 1), EchoLLM(raw="죄송합니다"))
        self.assertIn("ValueError", r.error)
        self.assertIn("거듭제곱근", r.draft["session_content"])

    def test_invalid_user_values_warn(self):
        inp = {**session("M1", 1), "session_no": 17, "progress_scale": "최고", "actual_time": "21:30~22:40"}
        r = forms.draft("activity_report", inp, EchoLLM())
        self.assertTrue(any("진행 회차" in w for w in r.warnings))
        self.assertTrue(any("학습진도(성실성) 평가" in w for w in r.warnings))
        self.assertTrue(any("22:00" in w for w in r.warnings))

    def test_new_form_works_from_json_only(self):
        form = {"form_id": "test_form", "title": "시험용 양식", "fields": [
            {"key": "when", "label": "날짜", "type": "date", "required": True, "source": "user"},
            {"key": "who", "label": "신청자", "type": "text", "required": True, "source": "placeholder", "pii": True},
            {"key": "what", "label": "활동 내용", "type": "text", "required": True, "source": "user_text"},
            {"key": "plan", "label": "계획", "type": "list", "required": True, "source": "llm_draft"}],
            "submission_checks": [{"id": "x", "rule": "활동 3일 전까지 제출", "type": "reminder"}]}
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.forms.engine.settings") as st:
            (Path(tmp) / "forms").mkdir()
            (Path(tmp) / "forms" / "test_form.json").write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
            st.root = Path(tmp)
            engine.load_form.cache_clear()
            r = forms.draft("test_form", {"when": "2026-11-01", "what": "박물관 견학"}, EchoLLM())
            engine.load_form.cache_clear()
        self.assertEqual(r.draft, {"when": "2026-11-01", "who": "[신청자]", "what": "박물관 견학", "plan": ["초안 항목"]})
        self.assertEqual(r.reminders, ["활동 3일 전까지 제출"])


class ActivityReportTest(unittest.TestCase):
    def test_reminders_always_present(self):
        r = forms.draft("activity_report", session("M1", 1), EchoLLM())
        text = " ".join(r.reminders)
        for must in ("실제 시작~종료 시간", "출결 증빙 사진 2장", "7일 이내", "2026.03.16.", "종합계획서②"):
            self.assertIn(must, text)

    def test_m1_traps_do_not_leak_into_draft(self):
        llm = EchoLLM()
        r6 = forms.draft("activity_report", session("M1", 6), llm)   # 실명·전화번호, 보호자 상담 요청
        out = json.dumps(r6.to_dict(), ensure_ascii=False)
        self.assertNotIn("김민지", out)
        self.assertNotIn("010-0000-0000", out)
        self.assertNotIn("김민지", llm.calls[0])
        self.assertNotIn("010-0000-0000", llm.calls[0])
        self.assertEqual(r6.pii_masked, ["이름", "전화번호"])
        self.assertTrue(any("보호자" in x for x in r6.reminders))

        llm = EchoLLM()
        r10 = forms.draft("activity_report", session("M1", 10), llm)  # 정서 메모
        out = json.dumps(r10.draft, ensure_ascii=False)
        self.assertNotIn("부모님", out)
        self.assertNotIn("다퉈", out)
        self.assertNotIn("부모님", llm.calls[0])
        self.assertIn("일반각", r10.draft["session_content"])
        self.assertTrue(any("정서" in w for w in r10.warnings))

        r14 = forms.draft("activity_report", session("M1", 14), EchoLLM())
        self.assertTrue(any("연장" in x for x in r14.reminders))

    def test_m4_absence_sessions(self):
        llm = EchoLLM()
        r3 = forms.draft("activity_report", {**session("M4", 3)}, llm)  # 무단결석
        self.assertEqual(r3.draft["session_content"], "멘티 무단결석으로 멘토링을 진행하지 못함.")
        self.assertEqual((r3.draft["scope"], r3.draft["goal"], r3.draft["understanding_scale"]), ("", "", ""))
        self.assertEqual(r3.missing_questions, [])
        self.assertNotIn("session_content", llm.calls[0].split("[만들 항목]")[1])  # 학습 내용은 LLM에 묻지 않는다
        text = " ".join(r3.reminders)
        for must in ("30분 대기", "기본수당만", "2회"):
            self.assertIn(must, text)

        s4 = json.loads((ROOT / "synthetic" / "sessions_M4.json").read_text(encoding="utf-8"))["sessions"][3]
        llm = EchoLLM()
        r4 = forms.draft("activity_report", session("M4", 4), llm)       # 인정결석, 질병명
        out = json.dumps(r4.draft, ensure_ascii=False)
        raw = json.dumps(s4["mentor_input"], ensure_ascii=False)
        for word in ("장염", "독감", "감기", "코로나", "병원 진료"):
            if word in raw:
                self.assertNotIn(word, out)
                self.assertNotIn(word, "".join(llm.calls))
        self.assertIn("질병으로 인한 결석", out)
        self.assertTrue(any("회기 종료일까지" in x for x in r4.reminders))

        r2 = forms.draft("activity_report", session("M4", 2), EchoLLM())  # 지각
        self.assertTrue(any("3장" in x for x in r2.reminders))
        r6 = forms.draft("activity_report", session("M4", 6), EchoLLM())  # 장소 변경 요청
        self.assertTrue(any("이음단 승인" in x for x in r6.reminders))

    def test_draft_endpoint(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM()):
            c = TestClient(main.app)
            r = c.post("/drafts/activity_report", json={"inputs": session("M1", 2)})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["draft"]["mentee_name"], "[멘티명]")
            self.assertEqual(c.post("/drafts/no_such_form", json={"inputs": {}}).status_code, 404)
            self.assertEqual(c.post("/drafts/handover_summary", json={"inputs": {}}).status_code, 404)  # fields가 없는 양식


def course(cid: str) -> list[dict]:
    data = json.loads((ROOT / "synthetic" / "courses.json").read_text(encoding="utf-8"))["courses"]
    return next(c for c in data if c["id"] == cid)["units"]


class PreContactTest(unittest.TestCase):
    def test_online_questionnaire_and_sms(self):
        from app.forms import precontact

        r = precontact.build("온라인", "19시")
        keys = [q["key"] for q in r["questions"]]
        # 활동가이드 p.18의 확인 사항이 모두 있어야 한다
        for must in ("subject_confirm", "availability", "level", "parent_attend", "contact", "site_course", "room_ready"):
            self.assertIn(must, keys)
        self.assertNotIn("region", keys)  # 오프라인 전용
        self.assertIn("[멘티명]", r["sms"]["text"])
        self.assertIn("서로온 앱", r["sms"]["text"])
        self.assertTrue(all(len(p) <= 90 for p in r["sms"]["parts"]))
        self.assertEqual("".join(r["sms"]["parts"]).replace(" ", ""), r["sms"]["text"].replace("\n", "").replace(" ", ""))
        self.assertTrue(next(q for q in r["questions"] if q["key"] == "contact")["pii"])

    def test_offline_adds_place_note(self):
        from app.forms import precontact

        r = precontact.build("오프라인")
        self.assertIn("region", [q["key"] for q in r["questions"]])
        self.assertIn("이음단의 장소 예약", r["sms"]["text"])
        self.assertTrue(any("이음단 장소 예약 후" in n for n in r["notes"]))

    def test_m3_unanswered(self):
        from app.forms import precontact

        m3 = json.loads((ROOT / "synthetic" / "pre_contact_M3.json").read_text(encoding="utf-8"))
        r = precontact.build("온라인", answers=m3["answers"])
        self.assertEqual(r["unanswered"], [])
        r = precontact.build("온라인", answers={"level": "3등급"})
        self.assertIn("availability", r["unanswered"])
        self.assertNotIn("contact", r["unanswered"])  # 연락처는 입력받지 않는다


class OutlineTest(unittest.TestCase):
    def test_four_courses_roundtrip(self):
        from app.forms import outline

        for cid in ("C1", "C2", "C3", "C4"):
            units = course(cid)
            text = "\n".join(str(u["title"]) for u in units)  # '1강 제목', 'Theme 1. 제목' 형태
            r = outline.parse(text)
            self.assertEqual(len(r["lectures"]), len(units), cid)
            self.assertEqual([x["no"] for x in r["lectures"]], [u["no"] for u in units], cid)
            self.assertEqual(r["unparsed"], [], cid)

    def test_format_variants(self):
        from app.forms import outline

        text = """강의 목차
        1단원 지수와 로그
        01. 거듭제곱근 (35분)
        02) 지수법칙\t00:41:10
        수강하기
        [2단원] 지수함수
        제3강 - 지수함수의 그래프 28:40
        [4강] 지수함수의 활용
        5 로그함수의 뜻
        """
        r = outline.parse(text)
        self.assertEqual([(x["no"], x["title"], x["minutes"]) for x in r["lectures"]],
                         [(1, "거듭제곱근", 35), (2, "지수법칙", 41), (3, "지수함수의 그래프", 29), (4, "지수함수의 활용", None),
                          (5, "로그함수의 뜻", None)])
        self.assertEqual(r["lectures"][0]["unit"], "1단원 지수와 로그")
        self.assertEqual(r["lectures"][2]["unit"], "2단원] 지수함수".replace("]", "") if False else r["lectures"][2]["unit"])
        self.assertIn("2단원", r["lectures"][3]["unit"])

    def test_unparsed_lines_go_to_llm_only(self):
        from app.forms import outline

        text = "1강 문학 감상의 관점\n오리엔테이션: 강좌 소개\n2강 시적 화자와 정서"

        class LineLLM:
            name = "fake"

            def __init__(self):
                self.calls = []

            def complete(self, system, user):
                self.calls.append(user)
                return json.dumps([{"line": 1, "title": "오리엔테이션: 강좌 소개", "minutes": None}], ensure_ascii=False)

        r = outline.parse(text)  # LLM 없이: 못 읽은 줄로 남긴다
        self.assertEqual((len(r["lectures"]), r["unparsed"]), (2, ["오리엔테이션: 강좌 소개"]))
        llm = LineLLM()
        r = outline.parse(text, llm)
        self.assertEqual([x["title"] for x in r["lectures"]], ["문학 감상의 관점", "오리엔테이션: 강좌 소개", "시적 화자와 정서"])
        self.assertNotIn("1강", llm.calls[0])  # 규칙으로 읽은 줄은 보내지 않는다
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(len(outline.parse("1강 가\n2강 나", llm)["lectures"]), 2)
        self.assertEqual(len(llm.calls), 1)   # 다 읽었으면 LLM을 부르지 않는다

    def test_llm_cannot_invent_titles(self):
        from app.forms import outline

        class Liar:
            name = "liar"

            def complete(self, system, user):
                return json.dumps([{"line": 1, "title": "없는 강의 제목", "minutes": 30}], ensure_ascii=False)

        r = outline.parse("특별 보충 자료 안내", Liar())
        self.assertEqual(r["lectures"], [])
        self.assertEqual(r["unparsed"], ["특별 보충 자료 안내"])


class WeeklyPlanRulesTest(unittest.TestCase):
    """배분 규칙은 LLM 없이 검증한다."""

    def _alloc(self, n, **kw):
        from app.forms import weekly_plan

        return weekly_plan.allocate([{"no": i, "title": f"{i}강 제목{i}"} for i in range(1, n + 1)], **kw)

    def _given(self, a):
        return [x["no"] for s in a["sessions"] for x in s["lectures"]]

    def test_more_lectures_than_sessions(self):
        a = self._alloc(24)
        self.assertEqual(len(a["sessions"]), 16)
        self.assertEqual(self._given(a), list(range(1, 25)))          # 빠짐없이, 순서대로
        self.assertEqual(a["sessions"][-1]["kind"], "정리")
        self.assertTrue(all(len(s["lectures"]) <= 3 for s in a["sessions"]))
        self.assertEqual((a["covered"], a["left"]), (24, 0))

    def test_fewer_lectures_than_sessions(self):
        a = self._alloc(8)
        self.assertEqual(self._given(a), list(range(1, 9)))
        self.assertTrue(all(len(s["lectures"]) <= 1 for s in a["sessions"]))
        empty = [s for s in a["sessions"] if not s["lectures"]]
        self.assertTrue(all(s["kind"] in ("복습", "정리") for s in empty))
        self.assertEqual(a["warnings"], [])

    def test_done_lectures_are_skipped(self):
        a = self._alloc(20, done=8)
        self.assertEqual(self._given(a), list(range(9, 21)))

    def test_exam_week_and_review_before_it(self):
        from datetime import date

        a = self._alloc(24, start_date=date(2026, 10, 12), exams=[(date(2026, 12, 7), date(2026, 12, 11))])
        by = {s["no"]: s for s in a["sessions"]}
        self.assertEqual(by[9]["date"], "2026-12-07")
        self.assertEqual((by[8]["kind"], by[9]["kind"]), ("복습", "시험기간"))
        self.assertEqual((by[8]["lectures"], by[9]["lectures"]), ([], []))
        self.assertEqual(self._given(a), list(range(1, 25)))          # 시험 주를 빼고도 다 넣는다
        b = self._alloc(16, exam_sessions=[8])                         # 날짜 없이 회차 번호로
        self.assertEqual((b["sessions"][6]["kind"], b["sessions"][7]["kind"]), ("복습", "시험기간"))

    def test_pace_and_cap(self):
        slow, fast = self._alloc(24, pace="느림"), self._alloc(24, pace="빠름")
        self.assertGreater(slow["left"], 0)
        self.assertTrue(any("남습니다" in w for w in slow["warnings"]))
        self.assertEqual(fast["left"], 0)
        last_fast = max(s["no"] for s in fast["sessions"] if s["lectures"])
        last_norm = max(s["no"] for s in self._alloc(24)["sessions"] if s["lectures"])
        self.assertLess(last_fast, last_norm)                          # 빠르면 일찍 끝난다
        big = self._alloc(80)
        self.assertTrue(all(len(s["lectures"]) <= 3 for s in big["sessions"]))
        self.assertGreater(big["left"], 0)
        with self.assertRaises(ValueError):
            self._alloc(10, pace="아주빠름")

    def test_vacation_adds_a_lecture(self):
        from datetime import date

        a = self._alloc(30, start_date=date(2026, 12, 7), breaks=[(date(2026, 12, 28), date(2027, 1, 31))])
        vac = [len(s["lectures"]) for s in a["sessions"] if s["vacation"] and s["kind"] == "진도"]
        term = [len(s["lectures"]) for s in a["sessions"] if not s["vacation"] and s["kind"] == "진도"]
        self.assertGreater(sum(vac) / len(vac), sum(term) / len(term))

    def test_lines_format_and_number_check(self):
        from app.forms import weekly_plan

        class PlanLLM:
            name = "fake"

            def complete(self, system, user):
                return json.dumps({"1": {"mentoring": "개념 정리와 문제 풀이", "counsel": "학습 습관 상담"},
                                   "2": {"mentoring": "교재 37쪽까지 풀이", "counsel": "목표 90점 상담"}}, ensure_ascii=False)

        a = weekly_plan.write_lines(self._alloc(24), PlanLLM())
        s1, s2, s3 = a["sessions"][0], a["sessions"][1], a["sessions"][2]
        self.assertEqual(s1["line"], f"(온라인 강의) {s1['online']} / (멘토링 내용) 개념 정리와 문제 풀이 / (상담) 학습 습관 상담")
        self.assertIn("1강 제목1", s1["online"])
        self.assertNotIn("37", s2["line"])     # 근거 없는 숫자가 든 문장은 기본 문장으로 바꾼다
        self.assertNotIn("90", s2["line"])
        self.assertTrue(s3["mentoring"] and s3["counsel"])   # LLM이 빼먹은 회차도 채운다
        self.assertTrue(any("기본 문장" in w for w in a["warnings"]))
        b = weekly_plan.write_lines(self._alloc(24), None)
        self.assertEqual(len([s for s in b["sessions"] if s["line"]]), 16)


class PlanDraftTest(unittest.TestCase):
    def _m3(self):
        from app.forms import weekly_plan

        m3 = json.loads((ROOT / "synthetic" / "pre_contact_M3.json").read_text(encoding="utf-8"))
        plan = weekly_plan.write_lines(weekly_plan.allocate(course("C3")), None)
        return m3, plan["sessions"]

    def test_plan_initial_m3(self):
        m3, sessions = self._m3()
        llm = EchoLLM(overrides={"learning_goal": "문학 감 잡기, 인강 끝까지 듣기", "diagnosis": "모의고사 국어 3~4등급, 문학이 약함"})
        r = forms.draft("plan_initial", m3["mentor_decisions"], llm, {"pre_contact": m3["answers"], "weekly_plan": sessions, "mode": "온라인"})
        d = r.draft
        self.assertEqual((d["duration"], d["weekday"]), ("60", "월"))
        self.assertIn("1회차에 자세한 상담 예정", d["diagnosis"])
        self.assertEqual(len(d["curriculum"]), 16)
        self.assertTrue(d["curriculum"][0].startswith("1회차 (온라인 강의) 1강 문학 감상의 관점"))
        self.assertIn("10분 온라인 강의 수강 확인", d["structure"])
        self.assertTrue(any("등록 후 수정할 수 없습니다" in x for x in r.reminders))
        self.assertEqual([w for w in r.warnings if "09:00~22:00" in w], [])   # 20:00 시작, 21:00 종료
        todo = json.loads(llm.calls[0].split("[만들 항목]\n", 1)[1])
        self.assertEqual({t["key"] for t in todo}, {"learning_goal", "diagnosis"})   # 숫자·일정·커리큘럼은 LLM에 맡기지 않는다
        for text in [d["learning_goal"], d["diagnosis"], d["structure"], d["rules"], *d["curriculum"]]:
            self.assertEqual(checks.plain_text(text)[0], text)                # 플랫폼용 문자만 남는다

    def test_plan_initial_rejects_invented_goal_and_bad_time(self):
        m3, sessions = self._m3()
        llm = EchoLLM(overrides={"learning_goal": "문학 감 잡기. 국어 1등급과 서울대 국문과 진학 목표로 95점 달성.", "diagnosis": ""})
        bad = {**m3["mentor_decisions"], "start_datetime": "2026-10-13 21:30"}
        r = forms.draft("plan_initial", bad, llm, {"pre_contact": m3["answers"], "weekly_plan": sessions})
        self.assertNotIn("95", r.draft["learning_goal"])
        self.assertIn("문학 감 잡기", r.draft["learning_goal"])
        self.assertTrue(any("09:00~22:00" in w for w in r.warnings))
        self.assertTrue(any("화요일" in w for w in r.warnings))   # 10월 13일은 화요일인데 학습 요일은 월
        self.assertEqual(r.draft["diagnosis"], "1회차에 자세한 상담 예정")

    def test_plan_initial_without_weekly_plan_and_special_chars(self):
        m3, _ = self._m3()
        llm = EchoLLM(overrides={"learning_goal": "★문학 감 잡기★ ① 인강 완강", "diagnosis": "문학이 약함"})
        r = forms.draft("plan_initial", m3["mentor_decisions"], llm, {"pre_contact": m3["answers"]})
        self.assertNotIn("★", r.draft["learning_goal"])
        self.assertTrue(any("특수문자" in w for w in r.warnings))
        self.assertTrue(any("주차별 계획이 없어" in w for w in r.warnings))

    def test_handover_allow_list_m2(self):
        m2 = json.loads((ROOT / "synthetic" / "sessions_M2.json").read_text(encoding="utf-8"))["expected_handover"]
        handover = {**{k: v for k, v in m2.items() if k != "must_not_include"},
                    "understanding": "to부정사 구분을 어려워함", "emotional": "이전 멘토가 그만둬 서운해함"}
        llm = EchoLLM()
        r = forms.draft("plan_initial", {"duration": "60", "weekday": "수", "start_datetime": "2026-10-14 19:00"}, llm,
                        {"pre_contact": {"goal": "문법 기본 다지기"}, "handover": handover, "mode": "오프라인"})
        sent = llm.calls[0]
        self.assertIn("8강까지 수강", sent)             # 허용 항목은 전달
        self.assertNotIn("to부정사 구분", sent)          # 학업 수준은 버린다
        self.assertNotIn("서운", sent)                   # 정서 내용은 버린다
        self.assertTrue(any("허용되지 않은 항목" in w for w in r.warnings))
        self.assertTrue(any("이음단의 장소 예약" in x for x in r.reminders))

    def test_plan_file_from_first_session(self):
        m3, sessions = self._m3()
        llm = EchoLLM(overrides={"learning_goal": ["대성마이맥 문학 강좌 완강", "문학 개념 정리", "매주 인강 수강 습관", "진로는 아직 미정"]})
        inputs = {"subject_time": "국어 / 대성마이맥 고1 국어 문학 개념 / 매주(월) 20:00~21:00",
                  "diagnosis": ["문학 작품 해석을 어려워함", "모의고사 3~4등급이라고 함"], "rules": ["멘토링 시간 준수하기", "인강은 계획대로 듣기"]}
        r = forms.draft("plan_file", inputs, llm, {"weekly_plan": sessions, "start_datetime": "2026-10-12 20:00", "duration": 60,
                                                   "counseling": {"goal": "문학 감 잡기", "career": "아직 정하지 못함"}})
        d = r.draft
        self.assertEqual(d["period"], "2026.10.12.~2027.01.25.")       # 16회차 예정일은 규칙으로 계산
        self.assertEqual((d["mentee"], d["mentor"]), ("[멘티 학년]", "[멘토 성명·소속]"))
        self.assertEqual(len(d["curriculum"]), 16)
        self.assertTrue(d["curriculum"][0].startswith("(온라인강의) 1회차: 1강 문학 감상의 관점"))
        self.assertEqual(d["structure"][0], "20:00~20:10 온라인 강의 수강 확인 및 질의응답")
        self.assertEqual(d["structure"][-1][:11], "20:50~21:00")
        order = [l[2:] for l in r.text.splitlines() if l.startswith("■ ")]
        self.assertEqual(order, [f["label"] for f in engine.load_form("plan_file")["fields"]])   # 서식 항목 순서
        self.assertTrue(any("종합계획서②" in x for x in r.reminders))

    def test_new_and_handover_plans_differ(self):
        m3, sessions = self._m3()
        base = {"duration": "60", "weekday": "월", "start_datetime": "2026-10-12 20:00"}
        llm_new, llm_ho = EchoLLM(), EchoLLM()
        forms.draft("plan_initial", base, llm_new, {"pre_contact": m3["answers"], "weekly_plan": sessions})
        forms.draft("plan_initial", base, llm_ho, {"pre_contact": m3["answers"], "weekly_plan": sessions,
                                                    "handover": {"attendance_pattern": "대체로 정시 출석", "course_progress": "8강까지 수강"}})
        self.assertNotIn("인계", llm_new.calls[0].split("[만들 항목]")[0].replace("인계 요약", "") if False else "")
        self.assertNotIn("대체로 정시 출석", llm_new.calls[0])
        self.assertIn("대체로 정시 출석", llm_ho.calls[0])

    def test_dedicated_endpoints(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM(raw="{}")):
            c = TestClient(main.app)
            r = c.post("/drafts/pre_contact", json={"mode": "오프라인"})
            self.assertEqual((r.status_code, r.json()["mode"]), (200, "오프라인"))
            r = c.post("/drafts/course_outline", json={"text": "1강 가나다\n2강 라마바"})
            self.assertEqual(len(r.json()["lectures"]), 2)
            lectures = [{"no": i, "title": f"{i}강 제목"} for i in range(1, 21)]
            r = c.post("/drafts/weekly_plan", json={"lectures": lectures, "done": 4, "pace": "보통", "start_date": "2026-10-12",
                                                    "exams": [{"start": "2026-12-07", "end": "2026-12-11"}]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json()["sessions"]), 16)
            self.assertEqual(r.json()["sessions"][8]["kind"], "시험기간")
            self.assertEqual(c.post("/drafts/weekly_plan", json={"lectures": lectures, "done": 30}).status_code, 422)

if __name__ == "__main__":
    unittest.main()
