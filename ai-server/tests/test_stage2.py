"""2단계 기능 테스트: 보고서 분리, 완료보고서, 인계 요약, 이음단 요청문, 답 못 한 질문 모음. 가짜 LLM만 쓴다."""
import json
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path

from app import forms, unanswered
from app.forms import handover, hooks_completion, ieumdan, report_split

ROOT = Path(__file__).resolve().parents[2]


def sessions(mentee: str, subject: str = "수학") -> list[dict]:
    data = json.loads((ROOT / "synthetic" / f"sessions_{mentee}.json").read_text(encoding="utf-8"))
    return [{"session_date": s["date"], "session_no": s["session_no"], "subject": subject, "course": "가상 강좌", "status": s["status"],
             **{k: v for k, v in s["mentor_input"].items() if k != "notes"}, "session_content": s["mentor_input"].get("notes", "")}
            for s in data["sessions"]]


def as_pasted(reports: list[dict]) -> str:
    """플랫폼에서 복사해 붙여 넣은 모양: '항목 이름: 값'이 보고서마다 이어진다."""
    fields = forms.engine.load_form("activity_report")["fields"]
    blocks = []
    for r in reports:
        lines = []
        for f in fields:
            value = {"mentee_name": "김민지", "mentee_grade": "고2", "mentor": "홍길동(가람대 수학과)"}.get(f["key"], r.get(f["key"], ""))
            lines.append(f"{f['label']}: {value}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


class EchoLLM:
    name = "echo"

    def __init__(self, overrides=None, raw=None):
        self.overrides, self.raw, self.calls = overrides or {}, raw, []

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.raw is not None:
            return self.raw
        if "[만들 항목]" not in user:
            return json.dumps({"summary": self.overrides.get("summary", "기록대로 정리함.")}, ensure_ascii=False)
        out = {}
        for item in json.loads(user.split("[만들 항목]\n", 1)[1]):
            out[item["key"]] = self.overrides.get(item["key"], item.get("input") or (["초안 항목"] if item["type"] == "list" else "초안"))
        return json.dumps(out, ensure_ascii=False)


class SplitTest(unittest.TestCase):
    def test_sixteen_pasted_reports_are_split(self):
        reports = sessions("M1")
        r = report_split.split(as_pasted(reports))
        self.assertEqual([s["session_no"] for s in r["sessions"]], list(range(1, 17)))
        self.assertEqual(r["warnings"], [])
        for got, want in zip(r["sessions"], reports):
            for key in ("session_date", "actual_time", "scope", "attendance", "homework", "progress_scale"):
                self.assertEqual(got.get(key, ""), want[key], (want["session_no"], key))
            for pii in ("mentee_name", "mentee_grade", "mentor"):
                self.assertNotIn(pii, got)   # 개인정보 칸은 읽고 버린다
        self.assertNotIn("김민지", json.dumps([{k: v for k, v in s.items() if k != "session_content"} for s in r["sessions"]], ensure_ascii=False))

    def test_out_of_order_missing_and_duplicate(self):
        reports = sessions("M1")
        text = as_pasted([reports[2], reports[0], reports[4], reports[4]])
        r = report_split.split(text)
        self.assertEqual([s["session_no"] for s in r["sessions"]], [1, 3, 5])
        self.assertTrue(any("빠진 회차" in w and "2, 4" in w for w in r["warnings"]))
        self.assertTrue(any("두 번" in w for w in r["warnings"]))

    def test_label_variants_and_garbage(self):
        text = "멘토링 일자\n2026-03-09\n진행 회차 : 1회차\n진행시간: 17:03~18:05\n학습진도 - 출결: 정시 입장\n"
        r = report_split.split(text)
        self.assertEqual(r["sessions"][0], {"session_date": "2026-03-09", "session_no": 1, "actual_time": "17:03~18:05", "attendance": "정시 입장"})
        self.assertEqual(report_split.split("아무 글이나 붙여 넣음")["sessions"], [])


class CompletionReportTest(unittest.TestCase):
    def _draft(self, llm, **inputs):
        m1 = json.loads((ROOT / "synthetic" / "sessions_M1.json").read_text(encoding="utf-8"))
        base = {"extension_mentor": m1["completion_extra"]["extension_mentor"], "extension_mentee": m1["completion_extra"]["extension_mentee"],
                "requests": m1["completion_extra"]["requests_by_mentor"]}
        return forms.draft("completion_report", {**base, **inputs}, llm, {"reports": sessions("M1"), "plan_goal": m1["plan_goal"]})

    def test_session_list_is_computed_by_rule(self):
        self.assertEqual(hooks_completion.session_line({"session_no": 1, "session_date": "2026-03-09", "actual_time": "17:03~18:05"}),
                         "1회차 : 26. 03. 09. 월 17시03분~18시05분(62분간)")
        self.assertEqual(hooks_completion.session_line({"session_no": 3, "session_date": "2026-09-12", "status": "무단결석"}),
                         "3회차 : 26. 09. 12. 토 (무단결석)")
        r = self._draft(EchoLLM())
        self.assertEqual(len(r.draft["session_list"]), 16)
        self.assertEqual(r.draft["session_list"][0], "1회차 : 26. 03. 09. 월 17시03분~18시05분(62분간)")
        self.assertEqual(r.draft["subject"], "수학")
        self.assertEqual(r.draft["learning_goal"], ["시발점 수Ⅰ 완강", "수Ⅰ 1회독, 기말고사 수학 3등급", "학습플래너 작성, 오답노트 습관"])
        self.assertEqual(r.draft["mentee_phone"], "[멘티 연락처]")
        self.assertEqual(r.missing_questions, [])

    def test_emotional_care_stays_empty_and_memo_does_not_reach_llm(self):
        llm = EchoLLM()
        r = self._draft(llm)
        sent = llm.calls[0][1]
        self.assertEqual(r.draft["emotional_care"], "")            # 멘토가 비워 둔 칸은 초안도 비운다
        self.assertNotIn("부모님", sent)                            # 10회차 정서 메모는 LLM에 가지 않는다
        self.assertNotIn("다퉈", sent)
        self.assertNotIn("김민지", sent)
        self.assertNotIn("010-0000-0000", sent)
        todo = json.loads(sent.split("[만들 항목]\n", 1)[1])
        self.assertNotIn("emotional_care", [t["key"] for t in todo])
        self.assertTrue(any("감성케어" in x for x in r.reminders))
        self.assertTrue(any("정서" in w for w in r.warnings))
        self.assertNotIn("understanding_scale", sent)               # 학습이해도 척도는 넘기지 않는다

    def test_mentor_written_emotional_care_is_used(self):
        r = self._draft(EchoLLM(), emotional_care="시험 기간에 불안해해서 계획을 같이 세움")
        self.assertIn("계획을 같이 세움", r.draft["emotional_care"])

    def test_fabricated_numbers_in_achievement_are_dropped(self):
        llm = EchoLLM(overrides={"achievement": ["16회차 중 지각 1회로 출석이 성실함", "기말고사에서 97점을 받음"], "content": ["오답노트 습관을 잡아 감"]})
        r = self._draft(llm)
        self.assertEqual(r.draft["achievement"], ["16회차 중 지각 1회로 출석이 성실함"])
        self.assertTrue(any("입력에 없는 숫자" in w for w in r.warnings))

    def test_missing_goal_and_reports(self):
        r = forms.draft("completion_report", {}, EchoLLM(), {"reports": sessions("M1")[:3]})
        keys = {q["key"] for q in r.missing_questions}
        self.assertTrue({"learning_goal", "extension_mentor", "extension_mentee"} <= keys)
        self.assertTrue(any("3건" in w for w in r.warnings))
        llm = EchoLLM()
        r = forms.draft("completion_report", {}, llm, {"reports": []})
        self.assertEqual((r.draft["content"], r.draft["achievement"], r.draft["session_list"]), ([], [], []))
        self.assertEqual(llm.calls, [])   # 기록이 없으면 LLM을 부르지 않는다


class HandoverTest(unittest.TestCase):
    def setUp(self):
        self.reports = sessions("M2", "영어")
        self.expected = json.loads((ROOT / "synthetic" / "sessions_M2.json").read_text(encoding="utf-8"))["expected_handover"]

    def test_only_allowed_items_and_sources(self):
        llm = EchoLLM()
        r = handover.build(self.reports, llm)
        self.assertEqual(set(r["summary"]), {"attendance_pattern", "homework_pattern", "attitude", "course_progress"})
        self.assertEqual(set(r["summary"]), set(self.expected) - {"must_not_include"})
        self.assertEqual(len(llm.calls), 4)                    # 허용 항목마다 따로 묻는다
        sent = "\n".join(u for _, u in llm.calls)
        for banned in ("understanding_scale", "session_content", "requests", "가람중", "서운", "군입대", "교과서 본문"):
            self.assertNotIn(banned, sent, banned)             # 출처가 아닌 칸은 LLM에 가지 않는다
        self.assertIn("단어 10개만 외움", sent)                 # 과제 수행 기록은 간다
        self.assertEqual(r["pii_masked"], ["학교명"])

    def test_second_check_removes_academic_and_emotional_sentences(self):
        bad = "대체로 정시에 출석함. to부정사 구분을 어려워하고 중간고사 성적이 낮음. 멘티가 서운해함. 이전 멘토는 군입대로 그만둠."
        r = handover.build(self.reports, EchoLLM(overrides={"summary": bad}))
        for key, text in r["summary"].items():
            self.assertEqual(text, "대체로 정시에 출석함.", key)
        self.assertTrue(any("학업 수준" in w for w in r["warnings"]))

    def test_scale_words_allowed_only_for_attitude(self):
        text = "학습진도(성실성)는 보통과 잘함 사이임."
        self.assertEqual(handover.second_check(text, "attitude"), (text, []))
        self.assertEqual(handover.second_check(text, "homework_pattern")[0], "")
        # 학습 범위에 '중간고사 대비'가 있어도 요약에 시험 이야기가 나오면 뺀다
        self.assertEqual(handover.second_check("8강까지 수강함. 6회차는 중간고사 대비로 진행함.", "course_progress")[0], "8강까지 수강함.")

    def test_invented_numbers_and_bad_output(self):
        r = handover.build(self.reports, EchoLLM(overrides={"summary": "8회 모두 출석함. 결석은 37회임."}))
        self.assertEqual(r["summary"]["attendance_pattern"], "8회 모두 출석함.")
        r = handover.build(self.reports, EchoLLM(raw="잘 모르겠습니다"))
        self.assertEqual(set(r["summary"].values()), {""})     # 형식이 틀리면 지어내지 않고 비운다
        self.assertEqual(len(r["errors"]), 4)
        self.assertEqual(handover.build([], EchoLLM())["summary"]["attitude"], "")

    def test_last_lecture_is_computed_by_rule(self):
        self.assertEqual(handover.last_lecture(self.reports), {"마지막으로 수강한 강": "8강", "다음 시작": "9강"})
        self.assertEqual(handover.last_lecture([{"lecture_progress": "7강 미수강 (시험 준비)"}]), {})
        self.assertEqual(handover.last_lecture([{"lecture_progress": "4, 5강 수강"}])["다음 시작"], "6강")
        r = handover.build(self.reports, EchoLLM(overrides={"summary": "8강까지 수강함. 다음 시작은 9강임."}))
        self.assertEqual(r["summary"]["course_progress"], "8강까지 수강함. 다음 시작은 9강임.")   # 규칙이 계산한 숫자는 통과
        self.assertEqual(handover.second_check("단어 과제를 다 외우지 못한 주가 있음.", "homework_pattern")[1], [])

    def test_weak_units_flag_default_off(self):
        self.assertFalse(handover.include_weak_units())
        with unittest.mock.patch.dict("os.environ", {"HANDOVER_INCLUDE_WEAK_UNITS": "true"}):
            r = handover.build(self.reports, EchoLLM())
            self.assertIn("weak_units", r["summary"])

    def test_result_feeds_plan_initial(self):
        r = handover.build(self.reports, EchoLLM(overrides={"summary": "대체로 정시에 출석함."}))
        llm = EchoLLM()
        forms.draft("plan_initial", {"duration": "60", "weekday": "수", "start_datetime": "2026-10-14 19:00"}, llm,
                    {"pre_contact": {"goal": "문법 기본"}, "handover": r["summary"]})
        self.assertIn("대체로 정시에 출석함.", llm.calls[0][1])


class IeumdanRequestTest(unittest.TestCase):
    NOW = datetime(2026, 10, 12, 10, 0)   # 월요일

    def test_default_now_is_korean_time(self):
        from zoneinfo import ZoneInfo

        seen = []

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                seen.append(tz)
                return datetime(2026, 10, 12, 8, 0, tzinfo=tz)

        with unittest.mock.patch.object(ieumdan, "datetime", Clock):
            ieumdan.build("장소 요청", region="강서구")
        self.assertEqual(seen, [ZoneInfo("Asia/Seoul")])

    def test_schedule_change_three_day_rule(self):
        ok = ieumdan.build("일정 변경", current=datetime(2026, 10, 15, 19, 0), desired=datetime(2026, 10, 16, 19, 0), now=self.NOW)
        self.assertEqual(ok["warnings"], [])
        self.assertIn("기존: 10월 15일(목) 19:00", ok["message"])
        self.assertIn("변경 희망: 10월 16일(금) 19:00", ok["message"])
        late = ieumdan.build("일정 변경", current=datetime(2026, 10, 14, 19, 0), desired=datetime(2026, 10, 16, 19, 0), now=self.NOW)
        self.assertTrue(any("2일 남았습니다" in w and "3일 전" in w for w in late["warnings"]))
        past = ieumdan.build("일정 변경", current=datetime(2026, 10, 10, 19, 0), desired=datetime(2026, 10, 16, 19, 0), now=self.NOW)
        self.assertTrue(any("이미 지났습니다" in w for w in past["warnings"]))
        night = ieumdan.build("일정 변경", current=datetime(2026, 10, 20, 19, 0), desired=datetime(2026, 10, 21, 21, 30), now=self.NOW)
        self.assertTrue(any("09:00~22:00" in w for w in night["warnings"]))
        weekend = ieumdan.build("일정 변경", current=datetime(2026, 10, 20, 19, 0), desired=datetime(2026, 10, 21, 19, 0),
                                now=datetime(2026, 10, 17, 10, 0))
        self.assertTrue(any("주말" in w for w in weekend["warnings"]))

    def test_place_request_is_short_and_has_no_names(self):
        r = ieumdan.build("장소 요청", region="가람중 근처, 김민지 학생 집에서 가까운 곳", schedule="매주 수 19:00~20:00", now=self.NOW)
        self.assertNotIn("김민지", r["message"])
        self.assertNotIn("가람중", r["message"])
        self.assertEqual(r["pii_masked"], ["이름", "학교명"])
        self.assertLess(r["length"], 200)
        self.assertIn("희망 일정: 매주 수 19:00~20:00", r["message"])
        self.assertTrue(ieumdan.build("장소 요청", now=self.NOW)["warnings"])
        with self.assertRaises(ValueError):
            ieumdan.build("환불 요청")

    def test_place_change(self):
        r = ieumdan.build("장소 변경", region="옆 동네 청소년센터", current=datetime(2026, 10, 24, 10, 0), reason="멘티 이동 거리", now=self.NOW)
        self.assertIn("장소 변경을 요청드립니다", r["message"])
        self.assertIn("사유: 멘티 이동 거리", r["message"])
        self.assertTrue(any("3일 전" in x for x in r["reminders"]))


class UnansweredTest(unittest.TestCase):
    def test_what_is_stored(self):
        self.assertEqual(unanswered.to_store("가람중 멘티  활동인증서를 영문으로 받을 수 있나요? 010-1234-5678", "no"),
                         "[학교명] 멘티 활동인증서를 영문으로 받을 수 있나요? [전화번호]")
        self.assertIsNone(unanswered.to_store("지각 처리 어떻게 해요?", "yes"))                       # 답한 질문은 모으지 않는다
        self.assertIsNone(unanswered.to_store("멘티가 집에서 맞는다고 하는데 어떻게 해요?", "no"))        # 아동 안전
        self.assertIsNone(unanswered.to_store("멘티가 부모님이랑 다퉈서 힘들다는데 상담 규정이 있나요?", "partial"))  # 정서·가정
        self.assertIsNone(unanswered.to_store("질문", "no", safety=True))
        self.assertIsNone(unanswered.to_store("가" * 151, "partial"))                                  # 길게 풀어 쓴 상황 설명
        self.assertIsNone(unanswered.to_store("중간고사 4등급 나온 멘티도 시간확대 되나요?", "no"))        # 성적 이야기

    def test_off_by_default_and_failures_do_not_raise(self):
        with unittest.mock.patch.object(unanswered, "_insert") as ins:
            with unittest.mock.patch.dict("os.environ", {"UNANSWERED_LOG": "off"}):
                self.assertFalse(unanswered.record("영문 인증서 되나요?", "no", "운영사무국"))
            ins.assert_not_called()
            with unittest.mock.patch.dict("os.environ", {"UNANSWERED_LOG": "on"}):
                self.assertTrue(unanswered.record("영문 인증서 되나요?", "no", "운영사무국"))
                ins.assert_called_once_with("영문 인증서 되나요?", "no", "운영사무국")
                ins.side_effect = RuntimeError("db down")
                self.assertFalse(unanswered.record("영문 인증서 되나요?", "no", "운영사무국"))   # 답변은 막지 않는다

    def test_endpoints_record_only_unanswered(self):
        from fastapi.testclient import TestClient

        from app import main
        from app.retrieval import BM25Retriever
        from app.corpus import load_markdown

        class LLM:
            name = "fake"

            def __init__(self, answerable):
                self.answerable = answerable

            def complete(self, system, user):
                if "문의 글의 초안" in system:
                    return json.dumps({"draft": "문의드립니다."}, ensure_ascii=False)
                return json.dumps({"answerable": self.answerable, "answer": "답", "citations": [1], "route": None}, ensure_ascii=False)

        retriever = BM25Retriever(load_markdown("v1"))
        for answerable, expected in (("no", 2), ("yes", 0)):
            llm = LLM(answerable)
            with unittest.mock.patch.object(main, "_llm", lambda: llm), unittest.mock.patch.object(main, "_retriever", lambda: retriever), \
                    unittest.mock.patch.object(main, "_graph", lambda: main.router.build_graph(lambda: llm, lambda: retriever)), \
                    unittest.mock.patch.object(unanswered, "_insert") as ins, unittest.mock.patch.dict("os.environ", {"UNANSWERED_LOG": "on"}):
                c = TestClient(main.app)
                self.assertEqual(c.post("/qa", json={"question": "가람중 멘티 영문 인증서 되나요?"}).status_code, 200)
                self.assertEqual(c.post("/chat", json={"message": "영문 인증서 발급 되나요?"}).status_code, 200)
                self.assertEqual(c.post("/chat", json={"message": "멘티가 집에서 맞는다는데 어디에 물어봐요?"}).status_code, 200)
                self.assertEqual(c.post("/chat", json={"message": "3회차 활동보고서 초안 써 줘"}).status_code, 200)
                self.assertEqual(ins.call_count, expected)
                if expected:
                    self.assertEqual(ins.call_args_list[0].args, ("[학교명] 멘티 영문 인증서 되나요?", "no", "운영사무국"))

    def test_stage2_endpoints(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM()):
            c = TestClient(main.app)
            r = c.post("/drafts/split_reports", json={"text": as_pasted(sessions("M1")[:2])})
            self.assertEqual(len(r.json()["sessions"]), 2)
            r = c.post("/drafts/handover_summary", json={"reports": sessions("M2", "영어")})
            self.assertEqual(len(r.json()["summary"]), 4)
            r = c.post("/drafts/ieumdan_request", json={"kind": "일정 변경", "current": "2030-01-10T19:00", "desired": "2030-01-11T19:00"})
            self.assertEqual(r.status_code, 200)
            self.assertIn("일정 변경을 요청드립니다", r.json()["message"])
            self.assertEqual(c.post("/drafts/ieumdan_request", json={"kind": "기타"}).status_code, 422)
            r = c.post("/drafts/completion_report", json={"inputs": {}, "extra": {"reports": sessions("M1")}})
            self.assertEqual(len(r.json()["draft"]["session_list"]), 16)


if __name__ == "__main__":
    unittest.main()
