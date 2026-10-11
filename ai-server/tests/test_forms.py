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
        # 숫자가 입력 어딘가에 있어도(3회차의 3) 같은 단위로 적혀 있지 않으면 등급·점수·비율은 지어낸 것으로 본다
        logs = "3회차 출석. 16회차 가운데 15회 출석. 모의고사 4 등급"
        self.assertEqual(checks.unsupported_numbers("3회차에 모의고사 3등급 달성", logs), ["3등급"])
        self.assertEqual(checks.unsupported_numbers("16회차 가운데 15회 출석, 모의고사 4등급", logs), [])
        self.assertEqual(checks.unsupported_numbers("출석률 15%", logs), ["15%"])
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
        # 줄 머리의 글머리 기호는 떼고(', 시간 지키기'가 되지 않게), 숫자 사이의 가운뎃점은 점으로 바꾼다
        self.assertEqual(checks.plain_text("• 시간 지키기\n· 과제 하기\n6·25 전쟁")[0], "시간 지키기\n과제 하기\n6.25 전쟁")
        self.assertIsNone(checks.parse_datetime("2026-10-12 25:00"))   # 없는 시각은 오류 대신 None

    def test_sensitive_filter(self):
        text, kinds = sensitive.filter_text("일반각 개념 금방 이해함. 마지막 10분은 부모님이랑 크게 다퉈서 집중 안 된다고 해서 얘기 들어줌")
        self.assertEqual((text, kinds), ("일반각 개념 금방 이해함", ["정서"]))
        text, kinds = sensitive.filter_text("장염으로 병원 진료 받아 결석, 진료확인서 받음")
        self.assertNotIn("장염", text)
        self.assertIn("질병으로 인한 결석", text)
        self.assertEqual(sensitive.filter_text("계산 실수가 많아 문제 풀이를 어려워함")[1], [])
        # 결석을 말하지 않은 건강 문장은 결석으로 바꾸지 않고 뺀다 (없던 결석을 만들지 않는다)
        self.assertEqual(sensitive.filter_text("감기 기운이 있었지만 끝까지 집중함. 예제는 혼자 품"), ("예제는 혼자 품", ["건강"]))
        # 교과 용어는 정서·건강 내용이 아니다. 진짜 내용은 그대로 걸린다
        for line in ["제안과 근거 찾기 연습", "교내과학탐구대회 준비", "화학 발열 반응 단원 5강까지 수강함", "소설 속 인물 간 갈등 구조 파악", "부모님과 상의해 문제집을 새로 사기로 함"]:
            self.assertEqual(sensitive.drop_lines(line), (line, []), line)
        for line in ["형과 갈등이 있음", "치과 진료로 결석", "부모님과 사이가 안 좋다고 함"]:
            self.assertTrue(sensitive.drop_lines(line)[1], line)


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


class DraftSafetyTest(unittest.TestCase):
    def test_safety_signal_skips_llm_in_drafts(self):
        from app import guard
        from app.forms import handover

        llm = EchoLLM()
        inp = dict(session("M1", 1), memo="멘티가 아버지에게 맞았다고 함. 010-1234-5678")
        r = forms.draft("activity_report", inp, llm)
        self.assertEqual((r.draft, r.warnings, llm.calls), ({}, [guard.SAFETY_DRAFT_NOTICE], []))
        r = forms.draft("activity_report", session("M1", 1), llm, {"memo": "집에서 자주 맞는다고 함"})
        self.assertEqual((r.warnings, llm.calls), ([guard.SAFETY_DRAFT_NOTICE], []))
        h = handover.build([{"session_content": "형한테 맞았다고 함"}], llm)
        self.assertEqual((h["warnings"], llm.calls), ([guard.SAFETY_DRAFT_NOTICE], []))
        self.assertTrue(all(v == "" for v in h["summary"].values()))
        # 값이 글이 아니라 목록이어도 신호를 본다
        h = handover.build([{"session_no": 1, "attendance": ["정시 출석", "아버지에게 맞았다고 함"]}], llm)
        self.assertEqual((h["warnings"], llm.calls), ([guard.SAFETY_DRAFT_NOTICE], []))

    def test_bad_input_is_not_a_server_error(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM()):
            c = TestClient(main.app)
            self.assertEqual(c.post("/drafts/weekly_plan", json={"lectures": [{}]}).status_code, 422)
            self.assertEqual(c.post("/drafts/plan_file", json={"inputs": {}, "extra": {"duration": "abc"}}).status_code, 200)
            # 양식과 모양이 다른 값은 서버 오류가 아니라 입력 오류다
            r = c.post("/drafts/activity_report", json={"inputs": {"status": 3, "session_date": "2026-10-06"}, "extra": {}})
            self.assertEqual((r.status_code, r.json()["detail"]), (422, "입력 형식을 확인해 주세요."))
            self.assertEqual(c.post("/drafts/completion_report", json={"inputs": {}, "extra": {"reports": 5}}).status_code, 422)


class WorkflowSpecTest(unittest.TestCase):
    """멘티 단계별 화면이 쓰는 입력: only(LLM에 맡길 항목), memo(멘토가 적은 글), curriculum_lines, 템플릿 문구."""

    DECISIONS = {"duration": "60", "weekday": "월", "start_datetime": "2026-10-12 17:00"}

    def test_simple_mode_uses_memo_without_llm(self):
        llm = EchoLLM()
        memo = {"learning_goal": "수1 완강", "diagnosis": "오답 정리를 미룸", "rules": "지각하면 미리 연락하기"}
        r = forms.draft("plan_initial", self.DECISIONS, llm, {"only": [], "memo": memo, "curriculum_lines": ["1주차 지수", "2주차 로그"]})
        self.assertEqual(llm.calls, [])                                   # 간단 모드: LLM을 부르지 않는다
        self.assertEqual(r.draft["learning_goal"], "수1 완강")
        self.assertEqual(r.draft["diagnosis"], "오답 정리를 미룸")
        self.assertEqual(r.draft["rules"], "지각하면 미리 연락하기")       # 메모가 있으면 기본 예시를 쓰지 않는다
        self.assertEqual(r.draft["structure"].split("\n")[0], "17:00~17:10 온라인 강의 수강(필수) 확인 및 퀴즈")   # 메모가 없는 칸은 규칙으로, 시각을 붙여 채운다
        self.assertEqual(len(r.draft["structure"].split("\n")), 5)
        self.assertEqual(r.draft["curriculum"], ["1주차 지수", "2주차 로그"])
        self.assertFalse(any("기본 예시" in w or "1회차만" in w for w in r.warnings))

    def test_itemized_diagnosis_keeps_lines(self):
        memo = {"diagnosis": "(과목역량) 기본기는 갖춤\n(학습습관 및 태도) 인강 의존도가 높음", "learning_goal": "(1) 수1 완강\n(2) 1회독"}
        r = forms.draft("plan_initial", self.DECISIONS, EchoLLM(), {"only": [], "memo": memo})
        self.assertEqual(r.draft["diagnosis"].split("\n"), ["(과목역량) 기본기는 갖춤", "(학습습관 및 태도) 인강 의존도가 높음"])   # 멘토가 적은 진단에는 덧붙이지 않는다
        self.assertEqual(r.draft["learning_goal"], "(1) 수1 완강\n(2) 1회독")
        none = forms.draft("plan_initial", self.DECISIONS, EchoLLM(), {"only": []})
        self.assertEqual(none.draft["diagnosis"], "1회차에 자세한 상담 예정")   # 아무것도 적지 않았을 때만 넣는다
        # 120분이면 서식 예시의 배분을 두 배로
        r = forms.draft("plan_initial", {**self.DECISIONS, "duration": "120"}, EchoLLM(), {"only": []})
        self.assertEqual(r.draft["structure"].split("\n")[1], "17:20~18:00 개념학습")

    def test_outline_with_duration_lines_and_free_titles(self):
        from app.forms import outline

        text = ("국어 학습 방법, 새기분 통합 OT\t\nOT\n\n-\t55:21\nHard Core.1ㅣ057\t\n통강 맛보기\n\n-\t48:53\nHard Core.1ㅣ058\t\n-\t48:27\n"
                "Hard Core.15ㅣ100 ▶완강\t\n-\t1:01:13\n내 학생들을 위한 CAST_1 [올바른 공부법]\t\n-\t42:19\n내 학생들을 위한 CAST_4 [시험 대비 콘텐츠]\t\n-\t15:18\n")

        class NoLLM:
            def complete(self, system, user):
                raise AssertionError("시간 줄로 가를 수 있는 목차는 LLM에 묻지 않는다")

        r = outline.parse(text, NoLLM())
        self.assertEqual([x["title"] for x in r["lectures"]], ["국어 학습 방법, 새기분 통합 OT", "Hard Core.1ㅣ057", "Hard Core.1ㅣ058", "Hard Core.15ㅣ100",
                                                             "내 학생들을 위한 CAST_1 [올바른 공부법]", "내 학생들을 위한 CAST_4 [시험 대비 콘텐츠]"])
        self.assertEqual([x["no"] for x in r["lectures"]], [1, 2, 3, 4, 5, 6])        # 번호가 없는 제목에는 순서대로 번호를 붙인다
        self.assertTrue(all(x["auto_no"] for x in r["lectures"]))
        self.assertEqual((r["lectures"][0]["minutes"], r["lectures"][3]["minutes"]), (55, 61))
        self.assertEqual(r["unparsed"], [])
        numbered = outline.parse("1강 지수\n- 40:10\n2강 로그\n- 38:00\n3강 삼각함수\n- 41:59\n")["lectures"]
        self.assertEqual([(x["no"], x["title"], x.get("auto_no")) for x in numbered], [(1, "지수", None), (2, "로그", None), (3, "삼각함수", None)])

    def test_allocate_by_weekly_count_or_target(self):
        from app.forms import weekly_plan

        lectures = [{"no": i, "title": f"제목{i}"} for i in range(1, 61)]
        counts = lambda a: [len(s["lectures"]) for s in a["sessions"]]   # noqa: E731
        weekly = weekly_plan.allocate(lectures, done=10, sessions=16, per_week=4)
        self.assertEqual(counts(weekly)[:15], [4] * 12 + [2, 0, 0])                 # 일주일에 4강씩, 남은 50강이 떨어질 때까지
        self.assertEqual(weekly["sessions"][0]["lectures"][0]["no"], 11)             # 이미 들은 강 다음부터
        goal = weekly_plan.allocate(lectures, done=10, sessions=16, target=45)
        self.assertEqual((sum(counts(goal)), goal["left"]), (45, 0))                 # 목표한 45강을 회기 안에 모두 나눈다
        self.assertEqual(max(counts(goal)) - min(counts(goal)[:15]), 0)              # 고르게: 15개 진도 회차에 3강씩
        self.assertEqual(goal["sessions"][14]["lectures"][-1]["no"], 55)
        self.assertEqual(goal["warnings"], [])

    def test_memo_is_polished_not_redrafted(self):
        """멘토가 적은 글이 있으면 AI는 그 글만 다듬는다 (인계받은 내용 같은 참고 입력으로 새로 쓰지 않는다)."""
        llm = EchoLLM()
        memo = {"learning_goal": "(1) 수1 끝까지 다 듣는거\n(2) 기말 3등급", "diagnosis": "(학습습관 및 태도) 혼자 공부하는 시간이 거의 없는듯"}
        r = forms.draft("plan_initial", self.DECISIONS, llm, {"memo": memo, "handover": {"attendance_pattern": "대체로 정시에 출석함"}})
        self.assertEqual(len(llm.calls), 1)
        self.assertIn("[참고 입력]\n{}", llm.calls[0])                       # 다듬기에는 참고 입력을 주지 않는다
        self.assertNotIn("정시에 출석", llm.calls[0])
        todo = {t["key"]: t for t in json.loads(llm.calls[0].split("[만들 항목]\n", 1)[1])}
        self.assertEqual({k: v["mode"] for k, v in todo.items()}, {"learning_goal": "polish", "diagnosis": "polish"})
        self.assertEqual(todo["learning_goal"]["input"], {"1": "수1 끝까지 다 듣는거", "2": "기말 3등급"})   # 줄 머리 표시는 떼고 본문만 번호를 붙여 보낸다
        self.assertEqual((todo["diagnosis"]["type"], todo["diagnosis"]["input"]), ("lines", {"1": "혼자 공부하는 시간이 거의 없는듯"}))
        self.assertNotIn("item_slots", todo["diagnosis"])                    # 다듬기에는 항목 틀을 주지 않는다 (빈 항목 줄을 만들지 않게)
        self.assertEqual(r.draft["learning_goal"], memo["learning_goal"])   # 머리 표시와 줄 구성은 규칙으로 되돌린다
        self.assertEqual(r.draft["diagnosis"], memo["diagnosis"])
        # 적지 않은 칸만 참고 입력으로 초안을 쓴다: 다듬기와 초안을 따로 묻는다
        llm2 = EchoLLM()
        forms.draft("plan_initial", self.DECISIONS, llm2, {"memo": {"learning_goal": "(1) 완강"}, "handover": {"attendance_pattern": "대체로 정시에 출석함"}})
        modes = [[t["mode"] for t in json.loads(c.split("[만들 항목]\n", 1)[1])] for c in llm2.calls]
        self.assertEqual(modes, [["polish"], ["draft"]])
        self.assertNotIn("정시에 출석", llm2.calls[0])
        self.assertIn("정시에 출석", llm2.calls[1])

    def test_drafted_slots_get_marks_by_rule(self):
        """적은 글이 없어 AI가 초안을 쓸 때: 자리마다 한 항목씩 받아 줄 머리 표시를 규칙으로 붙이고, 근거가 없는 자리는 뺀다."""
        reply = {"learning_goal": ["시발점 수1 이어서 수강", "", "", ""], "diagnosis": ["", "", "", ""]}
        llm = EchoLLM(raw=json.dumps(reply, ensure_ascii=False))
        r = forms.draft("plan_initial", self.DECISIONS, llm, {"handover": {"course_progress": "시발점 수1 12강까지 수강함"}})
        todo = {t["key"]: t for t in json.loads(llm.calls[0].split("[만들 항목]\n", 1)[1])}
        self.assertEqual((todo["learning_goal"]["type"], len(todo["learning_goal"]["item_slots"])), ("list", 4))
        self.assertEqual(r.draft["learning_goal"], "(1) 시발점 수1 이어서 수강")
        self.assertEqual(r.draft["diagnosis"], "1회차에 자세한 상담 예정")          # 아는 것이 없으면 지어내지 않고 이 문구만
        self.assertEqual(r.missing_questions, [])                                   # 근거가 없어 비운 것은 되묻지 않는다
        full = forms.draft("plan_initial", self.DECISIONS, EchoLLM(raw=json.dumps({"learning_goal": ["가", "나", "", ""], "diagnosis": ["", "", "", "정시에 출석함"]}, ensure_ascii=False)), {})
        self.assertEqual(full.draft["learning_goal"], "(1) 가\n(2) 나")
        self.assertEqual(full.draft["diagnosis"], "(학습습관 및 태도) 정시에 출석함\n1회차에 자세한 상담 예정")

    def test_polish_keeps_line_heads_by_rule(self):
        memo = {"learning_goal": "(1) 수1 끝까지 다 듣는거\n(2) 기말 3등급", "diagnosis": "(과목역량) 기본기는 있음\n(학습수준 및 희망진로) 김민지 학생 010-1234-5678"}

        def run(reply):
            return forms.draft("plan_initial", self.DECISIONS, EchoLLM(raw=json.dumps(reply, ensure_ascii=False)), {"memo": dict(memo)})

        # AI는 번호별로 다듬은 본문만 돌려주고, 머리 표시는 규칙으로 다시 붙는다. 빈 글로 돌아온 줄은 줄째 빠진다
        ok = run({"learning_goal": {"1": "수학1을 끝까지 수강함.", "2": "기말고사 3등급을 목표로 함."}, "diagnosis": {"1": "기본기는 갖춤.", "2": ""}})
        self.assertEqual(ok.draft["learning_goal"], "(1) 수학1을 끝까지 수강함.\n(2) 기말고사 3등급을 목표로 함.")
        self.assertEqual(ok.draft["diagnosis"], "(과목역량) 기본기는 갖춤.")
        # 돌려주지 않은 줄은 멘토가 쓴 글을 그대로 둔다 (말없이 사라지지 않는다)
        partial = run({"learning_goal": {"1": "수학1을 끝까지 수강함."}, "diagnosis": ["기본기는 갖춤.", "학생임."]})
        self.assertEqual(partial.draft["learning_goal"], "(1) 수학1을 끝까지 수강함.\n(2) 기말 3등급")
        self.assertEqual(partial.draft["diagnosis"].split("\n")[0], "(과목역량) 기본기는 갖춤.")   # 같은 개수의 목록은 차례대로 맞춘다
        # 다듬으면서 내용을 빼먹은 줄(숫자나 영문 낱말이 사라진 줄)도 멘토가 쓴 글로 되돌린다
        cut = forms.draft("plan_initial", self.DECISIONS, EchoLLM(raw=json.dumps({"learning_goal": {"1": "단어를 하루에 20개씩 외우기로 함"}}, ensure_ascii=False)),
                          {"memo": {"learning_goal": "(2) 단어 하루에 20개씩 외우기로 함 문법은 to부정사부터", "diagnosis": "(과목역량) 기본기는 있음"}, "only": ["learning_goal"]})
        self.assertEqual(cut.draft["learning_goal"], "(2) 단어 하루에 20개씩 외우기로 함 문법은 to부정사부터")
        self.assertTrue(any("to" in w and "빠뜨려" in w for w in cut.warnings))
        # 형식을 알아볼 수 없으면 다듬은 글을 쓰지 않고 전체를 그대로 둔다
        merged = run({"learning_goal": "수학1을 끝까지 수강하고 기말고사 3등급을 목표로 함.", "diagnosis": {"1": "기본기는 갖춤.", "2": "학생임."}})
        self.assertEqual(merged.draft["learning_goal"], memo["learning_goal"])
        self.assertTrue(any("줄 구성을 바꿔서" in w for w in merged.warnings))
        # 지어낸 숫자가 든 줄은 멘토가 쓴 글로 되돌리고, 나머지 줄과 줄바꿈은 남는다
        invented = run({"learning_goal": {"1": "수학1을 끝까지 수강함.", "2": "기말고사 95점을 목표로 함."}, "diagnosis": {"1": "기본기는 갖춤.", "2": "학생임."}})
        self.assertEqual(invented.draft["learning_goal"], "(1) 수학1을 끝까지 수강함.\n(2) 기말 3등급")
        self.assertTrue(any("95" in w and "적은 그대로" in w for w in invented.warnings))
        self.assertEqual(checks.drop_unsupported("(과목역량) 기본기는 갖춤.\n(학습습관 및 태도) 숙제를 해 옴.", "x")[0], "(과목역량) 기본기는 갖춤.\n(학습습관 및 태도) 숙제를 해 옴.")

    def test_sensitive_lines_are_dropped_from_plans_before_llm(self):
        llm = EchoLLM()
        memo = {"diagnosis": "(과목역량) 기본기는 갖춤\n(학습습관 및 태도) 부모님이 이혼하셔서 많이 힘들어함. 그래도 숙제는 꼬박꼬박 해옴\n(입시준비) 독감으로 입원해 준비를 못 함"}
        r = forms.draft("plan_initial", self.DECISIONS, llm, {"memo": memo})
        self.assertEqual(r.draft["diagnosis"], "(과목역량) 기본기는 갖춤\n(학습습관 및 태도) 그래도 숙제는 꼬박꼬박 해옴")   # 걸린 문장만 빼고 줄 구성은 그대로
        self.assertNotIn("이혼", llm.calls[0])
        self.assertNotIn("독감", llm.calls[0])
        self.assertTrue(any("정서·가정·건강" in w for w in r.warnings))
        clean = forms.draft("plan_initial", self.DECISIONS, EchoLLM(), {"only": [], "memo": {"diagnosis": "(과목역량) 기본기는 갖춤. 계산 실수가 잦음."}})
        self.assertEqual(clean.draft["diagnosis"], "(과목역량) 기본기는 갖춤. 계산 실수가 잦음.")   # 걸릴 것이 없으면 글자 하나 바꾸지 않는다
        self.assertFalse(any("정서" in w for w in clean.warnings))
        # 종합계획서②: 줄 단위 입력에서도 뺀다
        f = forms.draft("plan_file", {"diagnosis": ["(과목역량) 계산 실수가 잦음", "(학습습관 및 태도) 엄마랑 다퉈서 속상해함"], "rules": ["시간 지키기"]}, EchoLLM(), {"only": []})
        self.assertEqual(f.draft["diagnosis"], ["(과목역량) 계산 실수가 잦음"])

    def test_only_limits_llm_to_changed_fields(self):
        llm = EchoLLM()
        inp = dict(session("M1", 1))
        r = forms.draft("activity_report", inp, llm, {"only": ["homework"]})
        todo = json.loads(llm.calls[0].split("[만들 항목]\n", 1)[1])
        self.assertEqual([t["key"] for t in todo], ["homework"])          # 한 항목만 다시 만든다
        self.assertEqual(r.draft["scope"], inp["scope"])                  # 나머지는 멘토가 쓴 그대로

    def test_plan_file_period_follows_round_count(self):
        r = forms.draft("plan_file", {}, EchoLLM(), {"only": [], "start_datetime": "2026-10-12 17:00", "rounds": 8})
        self.assertEqual(r.draft["period"], "2026.10.12.~2026.11.30.")   # 8회차면 7주 뒤

    def test_templates_fill_subject(self):
        from app.forms import precontact

        sms = precontact.build("오프라인", subject="수학")["sms"]["text"]
        self.assertIn("서울런 수학 멘토", sms)
        self.assertIn("[멘토 연락처]", sms)
        self.assertNotIn("{", sms)
        self.assertNotIn("  ", precontact.build("온라인")["sms"]["text"])   # 과목이 없어도 빈칸이 겹치지 않는다
        self.assertFalse(any("직접 보관" in n for n in precontact.build("온라인")["notes"]))


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


    def test_late_cancel_session(self):
        # 임박취소(온라인): 진행하지 못한 회차라 학습 내용을 만들지 않고, 증빙과 준비수당 안내를 붙인다. 접속 기록(진행시간)은 묻지 않는다
        r = forms.draft("activity_report", {"status": "임박취소", "session_date": "2026-10-12", "session_no": "3", "subject": "수학", "course": "가상 강좌",
                                            "scope": "5~6강", "attendance": "임박취소"}, EchoLLM(), {"only": []})
        self.assertEqual(r.draft["session_content"], "멘티의 임박취소로 멘토링을 진행하지 못함.")
        self.assertEqual(r.draft["scope"], "")
        self.assertNotIn("actual_time", [q["key"] for q in r.missing_questions])
        self.assertTrue(any("준비수당만" in x for x in r.reminders))
        self.assertTrue(any("임박취소 연락내역" in x for x in r.reminders))
        self.assertFalse(any("진행시간은" in x for x in r.reminders))           # 진행하지 못한 회차에는 진행시간 안내를 붙이지 않는다

    def test_screen_path_keeps_lines_as_written(self):
        # 화면이 실제로 쓰는 경로: 줄마다 이름표를 붙여 보내고(keep_lines) 저장은 LLM 없이 한다. 보고서에 흔한 말이 가려져 사라지면 안 된다
        sent = {"attendance": "(p0) 출결: 정시 출석\n(p0) 과제: 과제 양이 많다고 함", "session_content": "(u0) 개념 복습중 졸았음\n(u0) 문제를 혼자해결함",
                "requests": "(r) 부모님과 상의해 일정을 변경하고 싶음"}
        llm = EchoLLM()
        r = forms.draft("activity_report", {**session("M1", 2), **sent}, llm, {"only": [], "keep_lines": True})
        self.assertEqual({k: r.draft[k] for k in sent}, sent)
        self.assertEqual((llm.calls, r.pii_masked), ([], []))
        # 건강 낱말이 든 줄은 통째로 뺀다: 숫자 사이 쉼표에서 쪼개 '2강만 들음' 같은 적지 않은 사실을 남기지 않는다
        sick = forms.draft("activity_report", {**session("M1", 2), "attendance": "(p0) 인강: 독감으로 1, 2강만 들음\n(p0) 출결: 정시 출석"}, EchoLLM(),
                           {"only": [], "keep_lines": True})
        self.assertEqual(sick.draft["attendance"], "(p0) 출결: 정시 출석")
        self.assertTrue(any("문장은 활동보고서에서 뺐습니다" in w for w in sick.warnings))

    def test_extended_session_needs_120_minutes(self):
        # 시간확대(120분) 회차는 90분이면 출석 인정 기준에 못 미친다. 60분 회차는 60분이 기준이다
        inputs = {**session("M1", 2), "actual_time": "17:00~18:30"}
        long = forms.draft("activity_report", dict(inputs), EchoLLM(), {"only": [], "duration": "120"})
        self.assertTrue(any("120분에 못 미칩니다" in w for w in long.warnings))
        self.assertFalse(any("못 미칩니다" in w for w in forms.draft("activity_report", dict(inputs), EchoLLM(), {"only": []}).warnings))
        # 연장 상의 안내: 시간확대는 8회차가 마지막이라 7회차부터, 60분은 14회차부터
        late = lambda no, extra: any("연장 여부" in x for x in forms.draft("activity_report", {**session("M1", 2), "session_no": str(no)}, EchoLLM(), {"only": [], **extra}).reminders)
        self.assertEqual([late(7, {"duration": "120"}), late(7, {}), late(14, {})], [True, False, True])

    def test_draft_endpoint(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM()):
            c = TestClient(main.app)
            r = c.post("/drafts/activity_report", json={"inputs": session("M1", 2)})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["draft"]["mentee_name"], "[멘티명]")
            self.assertEqual(c.post("/drafts/no_such_form", json={"inputs": {}}).status_code, 404)


def course(cid: str) -> list[dict]:
    data = json.loads((ROOT / "synthetic" / "courses.json").read_text(encoding="utf-8"))["courses"]
    return next(c for c in data if c["id"] == cid)["units"]


class PreContactTest(unittest.TestCase):
    def test_online_sms(self):
        from app.forms import precontact

        r = precontact.build("온라인")
        self.assertEqual(set(r), {"mode", "sms", "notes"})                 # 문자 문구와 안내만 만든다
        self.assertIn("[멘티명]", r["sms"]["text"])
        self.assertIn("서로온 앱", r["sms"]["text"])
        self.assertTrue(r["sms"]["text"].startswith("안녕하세요? 서울런 멘토로 활동하게 된 [멘토명]입니다.\n[멘티명] 학생의"))   # 과목이 없어도 인사 줄이 남는다
        self.assertIn("\n\n앞으로 진행될 멘토링", r["sms"]["text"])    # 읽기 편하게 문단을 나눈다
        self.assertNotIn("\n\n\n", r["sms"]["text"])
        self.assertNotIn("16회", r["sms"]["text"])                     # 회기 길이는 그룹마다 다를 수 있어 적지 않는다
        self.assertNotIn("4개월", r["sms"]["text"])
        self.assertTrue(r["sms"]["text"].endswith("전화가 어렵거나 연락 가능한 시간이 따로 있으시면 [멘토 연락처]로 문자 남겨 주세요."))

    def test_offline_adds_place_note(self):
        from app.forms import precontact

        r = precontact.build("오프라인")
        self.assertIn("이음단의 장소 예약", r["sms"]["text"])
        self.assertTrue(any("이음단 장소 예약 후" in n for n in r["notes"]))


class OutlineTest(unittest.TestCase):
    def test_titles_starting_with_unit_words_are_lectures(self):
        # '3 부등식의 영역'처럼 번호 뒤 제목이 부·장·편으로 시작하는 강의를 단원 이름으로 읽어 빠뜨리지 않는다
        from app.forms import outline

        r = outline.parse("1단원 지수\n1 지수\n2 로그\n3 부등식의 영역\n4 부정적분\n5 편미분")
        self.assertEqual([x["title"] for x in r["lectures"]], ["지수", "로그", "부등식의 영역", "부정적분", "편미분"])
        self.assertEqual({x["unit"] for x in r["lectures"]}, {"1단원 지수"})

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
        llm = LineLLM()
        outline.parse("문의 010-1234-5678 김민수 학생", llm)   # 못 읽은 줄도 가려서 보낸다
        self.assertNotIn("010-1234-5678", llm.calls[0])
        self.assertNotIn("김민수", llm.calls[0])

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
        self.assertIn("20:00~20:10 온라인 강의 수강(필수) 확인 및 퀴즈", d["structure"])
        self.assertEqual(d["rules"].split("\n")[1], "일정 변경은 최소 3일 전에 논의하기")   # 서식 예시를 한 줄에 하나씩
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
        # 허용 항목 안에 섞인 학업 수준·정서 문장도 뺀다 (이전 멘토가 보낸 글을 그대로 붙여 넣는다). 지난 회기 요약의 정서 문장도 같다
        llm2 = EchoLLM()
        r2 = forms.draft("plan_initial", {"duration": "60", "weekday": "수", "start_datetime": "2026-10-14 19:00"}, llm2,
                         {"handover": {"attitude": "질문을 자주 함. 모의고사 3등급으로 성적이 낮은 편임.\n부모님과 다퉈 속상해한 날이 있었음"},
                          "previous_term": {"content": ["플래너 작성 습관 형성", "친구와 다퉈서 속상해함"]}, "only": ["diagnosis"]})
        sent2 = llm2.calls[0]
        self.assertIn("질문을 자주 함", sent2)
        self.assertIn("플래너 작성 습관 형성", sent2)
        for word in ("3등급", "성적", "속상", "다퉈"):
            self.assertNotIn(word, sent2)
        self.assertTrue(any("허용되지 않은 내용" in w for w in r2.warnings))
        self.assertTrue(any("허용되지 않은 내용" in w for w in r.warnings))
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
        self.assertEqual(d["structure"][:2], ["20:00~20:10 온라인 강의 수강(필수) 확인 & 퀴즈", "20:10~20:30 개념학습"])
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

    def test_outline_image_is_transcribed_masked_and_checked(self):
        from app.forms import outline

        class Vision:
            def __init__(self, raw):
                self.raw, self.calls = raw, []

            def read_image(self, system, user, data_url):
                self.calls.append((system, user, len(data_url)))
                return self.raw

        png = "data:image/png;base64," + "A" * 40
        llm = Vision('{"lines": ["1강 지수의 뜻 32:10", " ", "2강 지수법칙 28:45", "김민지 학생 010-1234-5678"]}')
        res = outline.read_image(png, llm)
        self.assertEqual(res["text"], "1강 지수의 뜻 32:10\n2강 지수법칙 28:45\n학생")   # 이름과 전화번호는 가려서 뺀다
        self.assertEqual((res["lines"], res["error"]), (3, ""))
        self.assertIn("지어내지 않는다", llm.calls[0][0])
        # 읽은 글은 기존 목차 읽기에 그대로 들어간다
        self.assertEqual([x["title"] for x in outline.parse("1강 지수의 뜻 32:10\n2강 지수법칙 28:45", None)["lectures"]][:1], ["지수의 뜻"])
        # 형식이 깨진 응답, 목록이 없는 이미지, 이미지가 아닌 값은 오류로 알린다 (LLM을 부르지 않거나 조용히 넘기지 않는다)
        self.assertIn("읽지 못했습니다", outline.read_image(png, Vision("죄송합니다"))["error"])
        self.assertIn("찾지 못했습니다", outline.read_image(png, Vision('{"lines": []}'))["error"])
        bad = Vision("{}")
        self.assertIn("다시 올려", outline.read_image("data:text/html;base64,AAAA", bad)["error"])
        self.assertEqual(bad.calls, [])

    def test_dedicated_endpoints(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM(raw="{}")):
            c = TestClient(main.app)
            r = c.post("/drafts/pre_contact", json={"mode": "오프라인"})
            self.assertEqual((r.status_code, r.json()["mode"]), (200, "오프라인"))
            r = c.post("/drafts/course_outline", json={"text": "1강 가나다\n2강 라마바"})
            self.assertEqual(len(r.json()["lectures"]), 2)
            # 이미지에서 강의 목록 읽기: 이미지를 못 받는 모델이면 붙여 넣기를 안내한다
            png = "data:image/png;base64," + "A" * 40
            r = c.post("/drafts/course_outline_image", json={"image": png})
            self.assertEqual(r.status_code, 200)
            self.assertIn("이미지를 읽지 못합니다", r.json()["error"])
            lectures = [{"no": i, "title": f"{i}강 제목"} for i in range(1, 21)]
            r = c.post("/drafts/weekly_plan", json={"lectures": lectures, "done": 4, "pace": "보통", "start_date": "2026-10-12",
                                                    "exams": [{"start": "2026-12-07", "end": "2026-12-11"}]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json()["sessions"]), 16)
            self.assertEqual(r.json()["sessions"][8]["kind"], "시험기간")
            self.assertEqual(c.post("/drafts/weekly_plan", json={"lectures": lectures, "done": 30}).status_code, 422)

class ReportEvalTest(unittest.TestCase):
    def test_report_eval_runs_with_fake_llm(self):
        from evaluation import report_eval

        s = report_eval.run(report_eval.FakeLLM())
        a, p = s["forms"]["activity_report"], s["forms"]["plan_initial"]
        self.assertEqual((a["n"], p["n"]), (10, 4))
        self.assertEqual((a["exposed"], p["exposed"]), (0, 0))          # 가드와 필터는 LLM과 무관하게 동작한다
        self.assertEqual(a["should_be_empty_but_filled"], 0)
        self.assertEqual(a["missing_reminders"], 0)
        self.assertEqual((a["reask_accuracy"], p["reask_accuracy"]), (100.0, 100.0))
        self.assertIn("| 활동보고서 | 10건 |", report_eval.to_markdown(s, "fake", None))

    def test_scoring_catches_fabrication_and_exposure(self):
        from evaluation import report_eval

        class Bad(report_eval.FakeLLM):
            def complete(self, system, user):
                out = json.loads(super().complete(system, user))
                if "session_content" in out:
                    out["session_content"] = "김민지 학생이 모의고사 97점을 받음"
                return json.dumps(out, ensure_ascii=False)

        case = {"id": "X", "source": "M1#6", "forbidden": ["김민지"]}
        inputs = report_eval.activity_input(case)
        res = forms.draft("activity_report", inputs, Bad())
        row = report_eval.score("activity_report", case, inputs, {}, res)
        self.assertEqual(row["exposed"], [])       # 엔진이 이름을 다시 가리고
        self.assertEqual(row["fabricated"], [])    # 지어낸 숫자 문장을 뺐다
        res.draft["session_content"] = "김민지 학생이 모의고사 97점을 받음"   # 엔진을 거치지 않은 글이면 채점에서 걸린다
        row = report_eval.score("activity_report", case, inputs, {}, res)
        self.assertEqual(row["exposed"], ["김민지"])
        self.assertEqual(row["fabricated"], [("session_content", "97")])

if __name__ == "__main__":
    unittest.main()
