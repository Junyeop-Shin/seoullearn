"""2단계 기능 테스트: 완료보고서, 인계 요약, 답 못 한 질문 모음. 가짜 LLM만 쓴다. (붙여 넣은 보고서 나누기는 화면 쪽 규칙이다: frontend/src/lib/reportSplit.js)"""
import json
import unittest
import unittest.mock
from pathlib import Path

from app import forms, unanswered
from app.forms import handover, hooks_completion

ROOT = Path(__file__).resolve().parents[2]


def sessions(mentee: str, subject: str = "수학") -> list[dict]:
    data = json.loads((ROOT / "synthetic" / f"sessions_{mentee}.json").read_text(encoding="utf-8"))
    return [{"session_date": s["date"], "session_no": s["session_no"], "subject": subject, "course": "가상 강좌", "status": s["status"],
             **{k: v for k, v in s["mentor_input"].items() if k != "notes"}, "session_content": s["mentor_input"].get("notes", "")}
            for s in data["sessions"]]


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

    def test_stats_and_facts_follow_what_was_written(self):
        # 과제 통계: '미수행', '수행 못 함', '수행 안 함'은 하지 않은 것으로 센다
        hw = lambda *xs: [{"session_no": i + 1, "homework": x} for i, x in enumerate(xs)]
        got = hooks_completion.stats(hw("과제: RPM 10p - 수행함", "과제: 미수행", "과제: 수행 못 함", "과제: 수행하지 못함", "과제: 수행 안 함",
                                        "과제: 수행평가 안내문 읽기 - 수행함"))["과제"]
        self.assertEqual(got, {"수행함": 2, "수행하지 않음": 4})
        # 출석한 회차의 건강 문장은 결석으로 바뀌지 않고 빠진다. 학습 진도 칸 전체가 있으면 거기서 뽑은 세 줄은 한 번만 넘긴다
        llm = EchoLLM()
        note = "출결: 정시 출석 (17:02~18:04)\n인강: 5~6강 수강함\n과제: RPM 10p - 수행함\n잘한 점: 필기를 꼼꼼히 함"
        forms.draft("completion_report", {}, llm, {"reports": [{"session_no": 1, "session_date": "2026-10-06", "status": "출석", "attendance": "정시 출석 (17:02~18:04)",
                    "lecture_progress": "인강: 5~6강 수강함", "homework": "과제: RPM 10p - 수행함", "progress_note": note,
                    "etc": "감기 기운이 있었지만 끝까지 집중함"}]})
        sent = llm.calls[0][1]
        self.assertNotIn("질병으로 인한 결석", sent)
        self.assertNotIn("감기", sent)
        self.assertEqual(sent.count("5~6강 수강함"), 2)   # 회차별 기록에 한 번, 통계의 마지막 인강 기록에 한 번
        self.assertEqual(sent.count("필기를 꼼꼼히 함"), 1)
        # 통계의 '마지막 인강 기록'도 건강 문장을 뺀 글이다. 학습 진도 칸이 따로 있어 건너뛰는 칸에서 걸러진 것도 경고한다
        sick = [{"session_no": 1, "session_date": "2026-10-06", "lecture_progress": "4강 수강함"},
                {"session_no": 2, "session_date": "2026-10-13", "lecture_progress": "장염으로 입원해서 5강만 수강", "progress_note": "출결: 정시 출석\n인강: 5강 수강함"}]
        self.assertEqual(hooks_completion.stats(sick)["마지막 인강 기록"], "4강 수강함")
        llm = EchoLLM()
        r = forms.draft("completion_report", {}, llm, {"reports": sick})
        self.assertNotIn("장염", llm.calls[0][1])
        self.assertTrue(any("정서·가정·건강" in w for w in r.warnings))

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
        self.assertTrue(any("3건" in w and "16회차" in w for w in r.warnings))
        # 시간확대(120분)는 한 회기가 8회차다: 8건이면 다 마친 것이고, 안내도 8회차로 나온다
        # 친화·성장활동 기록은 참고 입력으로 넘어가고, 정서 내용은 빠진다
        llm = EchoLLM()
        forms.draft("completion_report", {}, llm, {"reports": sessions("M1")[:3], "activities": [{"유형": "성장활동", "활동 내용": "캠퍼스와 학과 건물을 둘러봄", "멘티 소감": "부모님이랑 다퉈서 속상했다고 함"}]})
        self.assertIn("캠퍼스와 학과 건물을 둘러봄", llm.calls[0][1])
        self.assertNotIn("속상", llm.calls[0][1])
        long = forms.draft("completion_report", {}, EchoLLM(), {"reports": sessions("M1")[:8], "duration": "120"})
        self.assertFalse(any("마친 뒤 작성" in w for w in long.warnings))
        self.assertTrue(any("8회차 활동보고서가 승인된 직후" in x for x in long.reminders))
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
        # 활동보고서 화면이 만드는 줄: 안 들은 강은 세지 않는다
        watched = [{"session_no": 1, "lecture_progress": "인강: 5강 수강함"}, {"session_no": 2, "lecture_progress": "인강: 6강 수강하지 않음"}]
        self.assertEqual(handover.last_lecture(watched)["다음 시작"], "6강")
        self.assertEqual(handover.last_lecture([{"lecture_progress": "인강: 3~4강 수강하지 않음"}]), {})
        self.assertEqual(handover.last_lecture([{"lecture_progress": "5강 수강, 6, 7강 미수강"}])["다음 시작"], "6강")
        # 전체 강 수, 목표나 예정으로 적은 강은 들은 강이 아니다. '다음 주' 뒤에 강 번호가 바로 올 때만 계획으로 본다
        for text in ("인강: 총 30강 중 5강 수강함", "5강 수강함 (목표 5~8강)", "5강 수강함 다음 주 6~7강 예정", "5강 수강. 다음 주에는 6강", "다음 주 시험이라 5강만 수강", "10강 중 5강 수강함"):
            self.assertEqual(handover.last_lecture([{"lecture_progress": text}])["다음 시작"], "6강", text)
        # 회기 중에 강좌를 바꿨으면 지금 강좌의 번호를 쓴다
        changed = [{"session_no": 1, "course": "강좌 가", "lecture_progress": "인강: 12강 수강함"}, {"session_no": 2, "course": "강좌 나", "lecture_progress": "인강: 1강 수강함"}]
        self.assertEqual(handover.last_lecture(changed)["다음 시작"], "2강")
        # '약하'는 낱말 머리일 때만 학업 수준으로 본다 (예약하지, 요약하는)
        for ok in ("스터디카페를 예약하지 못한 주에는 온라인으로 진행함.", "지난 회차 내용을 요약하는 과제를 꾸준히 해 옴."):
            self.assertEqual(handover.second_check(ok, "attendance_pattern"), (ok, []))
        self.assertEqual(handover.second_check("독해가 약함.", "attitude")[0], "")
        r = handover.build(self.reports, EchoLLM(overrides={"summary": "8강까지 수강함. 다음 시작은 9강임."}))
        self.assertEqual(r["summary"]["course_progress"], "8강까지 수강함. 다음 시작은 9강임.")   # 규칙이 계산한 숫자는 통과
        self.assertEqual(handover.second_check("단어 과제를 다 외우지 못한 주가 있음.", "homework_pattern")[1], [])
        # 석차, 기초·실력의 높낮이, 단원을 모른다·힘들어한다는 학업 수준이다. 과제와 태도 이야기는 남긴다
        for bad in ("반에서 5등", "기초가 부족함", "개념 이해가 더딤", "함수 파트를 잘 모름", "학습 속도가 느림", "진도를 따라오지 못함", "로그 단원을 힘들어함"):
            self.assertEqual(handover.second_check(bad, "course_progress")[0], "", bad)
        for ok in ("과제 수행이 부족한 주가 있었음", "모르는 문제를 표시해 와서 질문함", "필기 속도가 느려 시간을 넉넉히 줌", "수학 개념 12강까지",
                   "밀크T 중3 영어 문법 약 10강까지 수강함", "영어 독해 좋아함"):
            self.assertEqual(handover.second_check(ok, "homework_pattern"), (ok, []), ok)

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
                self.answerable, self.calls = answerable, 0

            def complete(self, system, user):
                self.calls += 1
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
                self.assertEqual(llm.calls, 2)   # 질문 두 건의 답변뿐: 문의 초안은 정해진 틀이라 LLM을 부르지 않는다
                if expected:
                    self.assertEqual(ins.call_args_list[0].args, ("[학교명] 멘티 영문 인증서 되나요?", "no", "운영사무국"))

    def test_qa_safety_path_needs_no_retriever_or_llm(self):
        # 아동 안전 신호가 있으면 검색기와 LLM을 만들지도 않는다: DB나 키에 문제가 있어도 즉시 보고 안내는 나간다
        from fastapi.testclient import TestClient

        from app import main

        def broken():
            raise RuntimeError("db down")

        with unittest.mock.patch.object(main, "_llm", broken), unittest.mock.patch.object(main, "_retriever", broken):
            r = TestClient(main.app).post("/qa", json={"question": "멘티가 아버지에게 맞았습니다"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["safety"])
        self.assertIsNone(r.json()["inquiry_draft"])

    def test_stage2_endpoints(self):
        from fastapi.testclient import TestClient

        from app import main

        with unittest.mock.patch.object(main, "_draft_llm", lambda: EchoLLM()):
            c = TestClient(main.app)
            r = c.post("/drafts/handover_summary", json={"reports": sessions("M2", "영어")})
            self.assertEqual(len(r.json()["summary"]), 4)
            r = c.post("/drafts/completion_report", json={"inputs": {}, "extra": {"reports": sessions("M1")}})
            self.assertEqual(len(r.json()["draft"]["session_list"]), 16)


if __name__ == "__main__":
    unittest.main()
