"""활동비 계산기 테스트. 기대값은 활동가이드 p.41~47의 표와 평가셋 계산 문항에서 가져왔다."""
import json
import unittest

from app import allowance
from app.corpus import load_markdown
from app.retrieval import BM25Retriever


class RateTest(unittest.TestCase):
    def test_rounding_matches_manual(self):
        self.assertEqual(allowance.up10(12_790 * 0.10), 1_280)
        self.assertEqual(allowance.up10(12_790 * 0.30), 3_840)
        self.assertEqual(allowance.up10(12_790 * 0.20), 2_560)
        self.assertEqual(allowance.up10(30_000 * 0.20), 6_000)

    def test_online_max_table_p47(self):
        # 온라인 활동수당 지급 기준 (최대값 예시): 1차~6차
        self.assertEqual([allowance.hourly("온라인", s, senior=True)["total"] for s in range(1, 7)],
                         [19_190, 20_470, 21_750, 23_030, 24_310, 25_590])

    def test_eval_q001_q002_q045_q050(self):
        self.assertEqual(allowance.hourly("온라인")["items"][0], {"name": "기본수당", "amount": 12_790})                 # Q001
        self.assertEqual(allowance.hourly("오프라인")["total"], 30_000)                                                # Q002
        self.assertEqual(allowance.hourly("온라인", 1, senior=True)["total"], 19_190)                                  # Q045
        r = allowance.hourly("오프라인", senior=True)                                                                   # Q050
        self.assertEqual((r["total"], [i["amount"] for i in r["items"]]), (36_000, [30_000, 6_000]))

    def test_senior_and_vulnerable_do_not_stack(self):
        both = allowance.hourly("오프라인", senior=True, vulnerable=True)
        self.assertEqual(both["total"], 36_000)
        self.assertTrue(any("중복 지급되지 않아" in n for n in both["notes"]))
        self.assertEqual(allowance.hourly("온라인", vulnerable=True)["total"], 12_790 + 3_840 + 2_560)

    def test_offline_has_no_prep_or_long_term(self):
        r = allowance.hourly("오프라인", stage=3)
        self.assertEqual(r["total"], 30_000)
        self.assertTrue(r["notes"])
        with self.assertRaises(ValueError):
            allowance.hourly("화상")
        with self.assertRaises(ValueError):
            allowance.hourly("온라인", 7)


class StageTest(unittest.TestCase):
    def test_monthly_example_table_p45(self):
        months = allowance.stages_by_month([5, 6, 6, 4, 7, 2])          # 월별 온라인 활동비 예시의 총 진행 횟수
        self.assertEqual([m["applied"] for m in months], [4, 4, 4, 4, 4, 0])
        self.assertEqual([m["stage"] for m in months], [1, 1, 2, 2, 3, 3])
        self.assertEqual([m["hourly"] for m in months], [12_790, 12_790, 14_070, 14_070, 15_350, 15_350])

    def test_eval_q046_two_months_of_four(self):
        months = allowance.stages_by_month([4, 4, 4])
        self.assertEqual([m["stage"] for m in months], [1, 1, 2])       # 바로 다음 달부터 1단계 상승
        self.assertEqual(months[2]["hourly"], 14_070)                    # 12,790 + 1,280

    def test_eval_q047_three_sessions_do_not_count(self):
        months = allowance.stages_by_month([4, 3, 4, 4])
        self.assertEqual([m["applied"] for m in months], [4, 0, 4, 4])
        self.assertEqual([m["stage"] for m in months], [1, 1, 1, 2])    # 3회인 달은 건너뛰고, 4회인 달이 2번 모여야 오른다

    def test_eval_q049_stage_never_drops_and_caps_at_six(self):
        months = allowance.stages_by_month([4, 4, 0, 0, 4])
        self.assertEqual([m["stage"] for m in months], [1, 1, 2, 2, 2])
        self.assertEqual(allowance.stages_by_month([4] * 14)[-1]["stage"], 6)


class EstimateTest(unittest.TestCase):
    def test_month_estimate_online(self):
        r = allowance.estimate("온라인", normal=4, no_show=1, late_cancel=1, stage=2, senior=True)
        per_hour = 12_790 + 3_840 + 1_280 + 2_560
        self.assertEqual(r["hourly"]["total"], per_hour)
        self.assertEqual([l["amount"] for l in r["lines"]], [4 * per_hour, 12_790, 3_840])
        self.assertEqual(r["total"], 4 * per_hour + 12_790 + 3_840)
        self.assertTrue(r["counts_for_stage"])
        self.assertTrue(any("기본수당이 지급" in n for n in r["notes"]))

    def test_eval_q048_two_hour_session_counts_once(self):
        r = allowance.estimate("온라인", normal=3, hours=2)
        self.assertEqual(r["total"], 3 * 2 * (12_790 + 3_840))            # 금액은 2시간분
        self.assertEqual(r["valid_count"], 3)                              # 진행 횟수는 회차당 1회
        self.assertFalse(r["counts_for_stage"])

    def test_vulnerable_is_shown_as_later_payment(self):
        r = allowance.estimate("오프라인", normal=4, vulnerable=True)
        self.assertEqual(r["total"], 4 * 30_000)
        self.assertEqual(r["later"]["amount"], 4 * 6_000)
        self.assertIsNone(allowance.estimate("오프라인", normal=4, senior=True)["later"])

    def test_offline_late_cancel_is_not_paid(self):
        r = allowance.estimate("오프라인", normal=2, late_cancel=1)
        self.assertEqual(r["total"], 60_000)
        self.assertTrue(any("온라인 멘토링에만" in n for n in r["notes"]))


class RouterCalcTest(unittest.TestCase):
    class NoLLM:
        name = "none"

        def complete(self, system, user):
            raise AssertionError("계산 질문에 LLM을 부르면 안 된다")

    def _chat(self, message):
        from app import router

        llm = self.NoLLM()
        return router.build_graph(lambda: llm, lambda: BM25Retriever(load_markdown("v1"))).invoke({"message": message})

    def test_rate_questions_use_the_calculator(self):
        s = self._chat("온라인 멘토링은 시간당 얼마 받아요?")                      # Q001
        self.assertEqual((s["intent"], s["method"]), ("calc", "rule"))
        self.assertIn("12,790원", s["result"]["answer"])
        self.assertIn("16,630원", s["result"]["answer"])                       # 기본 + 준비활동
        self.assertTrue(s["result"]["citations"])
        s = self._chat("오프라인으로 고등학생 가르치면 시간당 얼마예요?")           # Q050
        self.assertIn("36,000원", s["result"]["answer"])
        self.assertNotIn("12,790", s["result"]["answer"])
        s = self._chat("온라인 처음 8회차까지 최대로 받으면 시간당 얼마예요?")       # Q045
        self.assertIn("19,190원", s["result"]["answer"])
        s = self._chat("활동비 시간당 얼마예요?")                                 # 유형을 안 적으면 둘 다
        self.assertIn("온라인 멘토링", s["result"]["answer"])
        self.assertIn("오프라인 멘토링", s["result"]["answer"])

    def test_other_pay_questions_are_not_calc(self):
        for q in ("활동비 언제 들어와요?", "활동비에서 세금 얼마 떼요?", "두 달 연속으로 한 달에 4번씩 했으면 시급 올라가요?",
                  "장학금은 얼마예요?"):
            self.assertFalse(allowance.is_rate_question(q), q)

    def test_endpoint(self):
        from fastapi.testclient import TestClient

        from app import main

        c = TestClient(main.app)
        r = c.post("/tools/allowance", json={"mode": "온라인", "normal": 4, "stage": 1, "monthly_valid": [5, 6, 6, 4, 7, 2]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["total"], 4 * 16_630)
        self.assertEqual([m["stage"] for m in body["months"]], [1, 1, 2, 2, 3, 3])
        self.assertIn("추정 금액", body["disclaimer"])
        self.assertEqual(c.post("/tools/allowance", json={"mode": "화상"}).status_code, 422)
        json.dumps(body)


if __name__ == "__main__":
    unittest.main()
