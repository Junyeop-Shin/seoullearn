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
            self.assertEqual(c.post("/drafts/pre_contact", json={"inputs": {}}).status_code, 404)  # fields가 없는 양식


if __name__ == "__main__":
    unittest.main()
