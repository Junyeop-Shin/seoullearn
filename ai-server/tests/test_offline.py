"""네트워크·API 키 없이 도는 테스트.  python -m unittest discover -s tests -v"""
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from app import guard, qa
from app.corpus import load_markdown
from app.llm import HashEmbedder
from app.retrieval import BM25Retriever, GlossaryExpander, tokenize


class GuardTest(unittest.TestCase):
    def test_masks_phone_school_name(self):
        r = guard.check("김민지 학생 어머님이 010-0000-0000으로 연락 달래요. 가람중 중간고사 범위예요")
        self.assertIn("[전화번호]", r.text)
        self.assertIn("[학교명]", r.text)
        self.assertIn("[이름]", r.text)
        self.assertIn("중간고사", r.text)  # 일반 단어는 남긴다
        self.assertEqual(r.pii, ["이름", "전화번호", "학교명"])

    def test_no_false_positive(self):
        for q in ["멘티 학생이 지각했어요", "고등학생 멘티도 시간확대 되나요?", "중간고사 기간에 쉬어도 돼요?", "최고 시급이 얼마예요?"]:
            self.assertEqual(guard.check(q).pii, [], q)

    def test_verb_endings_are_not_school_names(self):
        # '~고'로 끝나는 활용형과 '~중·~초' 일반 명사를 학교명으로 가리면 질문이 망가진다
        for q in ["일정을 미루고 싶어요", "멘티가 못 간다고 했어요", "어디에 알아보라고 하나요?", "보고서를 제출했고 승인을 기다려요",
                  "지금 수업중 이에요", "모집공고 언제 나와요?", "학기초 일정이 궁금해요", "쉽고 빠른 방법 있나요?"]:
            r = guard.check(q)
            self.assertEqual((r.pii, r.text), ([], q), q)

    def test_short_school_names_still_masked(self):
        for q in ["한빛고 2학년 멘티예요", "누리초 다녀요", "가람중 시험 범위예요", "명지고 다니는 멘티예요", "서울공고 2학년이에요", "대원외고 멘티예요"]:
            self.assertIn("[학교명]", guard.check(q).text, q)

    def test_safety(self):
        self.assertTrue(guard.check("멘티가 집에서 맞는다는 얘기를 했어요").safety)
        self.assertFalse(guard.check("시간 맞춰서 들어가면 되나요?").safety)


class CorpusTest(unittest.TestCase):
    def test_v1_v2(self):
        v1, v2 = load_markdown("v1"), load_markdown("v2")
        self.assertGreater(len(v1), 80)
        self.assertTrue(all(c.doc_type == "manual" for c in v1))
        self.assertGreater(len(v2), len(v1))
        self.assertFalse(any(c.status == "expired" for c in v2), "만료 공지는 기본 검색에서 빠져야 함")
        self.assertTrue(all(c.page for c in v1))


class RetrievalTest(unittest.TestCase):
    def test_bm25_finds_late_rule(self):
        r = BM25Retriever(load_markdown("v1"))
        top = [c.doc_id for c, _ in r.search("지각 처리 어떻게 해요?", 5)]
        self.assertIn("manual-2026-3-1", top)

    def test_glossary(self):
        q = GlossaryExpander().expand("주간보고서 늦게 내면?")
        self.assertIn("활동보고서", q)

    def test_tokenize(self):
        self.assertIn("활동", tokenize("활동보고서"))


class ParseTest(unittest.TestCase):
    def test_parse_code_block(self):
        d = qa.parse_output('```json\n{"answerable":"partial","answer":"x","citations":[2,"1"],"route":"이음단"}\n```')
        self.assertEqual(d["citations"], [2, 1])
        self.assertEqual(d["route"], "이음단")

    def test_bad_route_dropped(self):
        d = qa.parse_output('{"answerable":"yes","answer":"x","citations":[],"route":"서울시청"}')
        self.assertIsNone(d["route"])


class RouteAndEmbeddingTest(unittest.TestCase):
    def test_route_contact(self):
        url = "https://open.kakao.com/o/abcDEF12"
        self.assertEqual(qa.route_contact("이음단", url)[1], url)
        self.assertIsNone(qa.route_contact("운영사무국", url)[1])  # 이음단 외에는 링크를 붙이지 않는다
        self.assertEqual(qa.route_contact(None, url), (None, None))

    def test_openchat_pattern(self):
        import re

        self.assertTrue(re.match(qa.KAKAO_OPENCHAT_PATTERN, "https://open.kakao.com/o/abcDEF12"))
        self.assertFalse(re.match(qa.KAKAO_OPENCHAT_PATTERN, "https://evil.example.com/o/abc"))
        self.assertFalse(re.match(qa.KAKAO_OPENCHAT_PATTERN, "http://open.kakao.com/o/abc"))

    def test_routing_rule_in_prompt(self):
        self.assertIn("온라인·오프라인 모두", qa.SYSTEM)
        self.assertIn("매칭 전 단계", qa.SYSTEM)

    def test_e5_prefixes(self):
        from app.llm import e5_prefixes

        self.assertEqual(e5_prefixes("dragonkue/multilingual-e5-small-ko-v2"), ("query: ", "passage: "))
        self.assertEqual(e5_prefixes("BAAI/bge-m3"), ("", ""))
        q, d = e5_prefixes("intfloat/multilingual-e5-large-instruct")
        self.assertTrue(q.startswith("Instruct: ") and q.endswith("\nQuery: "))
        self.assertEqual(d, "")

    def test_vector_uses_query_embedding(self):
        from app.retrieval import VectorRetriever

        class Spy(HashEmbedder):
            def __init__(self):
                super().__init__(dim=256)
                self.name, self.queries = "spy", []

            def embed_query(self, text):
                self.queries.append(text)
                return super().embed_query(text)

        chunks = load_markdown("v1")[:10]
        spy = Spy()
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.retrieval.settings") as st:
            st.cache_dir = Path(tmp)
            VectorRetriever(chunks, spy).search("지각", 3)
        self.assertEqual(spy.queries, ["지각"])


class EndToEndTest(unittest.TestCase):
    def test_eval_runner_with_fake_llm(self):
        from evaluation.run_eval import run

        with tempfile.TemporaryDirectory() as tmp:
            out, s = run("md_hybrid", "v1", fake_llm=True, limit=12, embedder=HashEmbedder(), out_dir=Path(tmp))
            recs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(recs), 12)
            self.assertIn("answer", s)
            self.assertIn("hit@5", s["retrieval"])
            # 안전 문항이 섞여도 LLM 없이 즉시 연결되는지
            out2, s2 = run("md_bm25", "v1", fake_llm=True, ids={"Q041"}, out_dir=Path(tmp))
            self.assertEqual(s2["answer"]["safety_route_ok"], 100.0)


    def test_embedding_bench_with_hash_embedder(self):
        from evaluation.embedding_bench import bench

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.retrieval.settings") as st:
            st.cache_dir = Path(tmp)
            r = bench(HashEmbedder(dim=256), out_dir=Path(tmp), limit=6)
        self.assertEqual(set(r["configs"]), {"md_vector", "md_hybrid"})
        for c in r["configs"].values():
            self.assertIn("hit@5", c)
            self.assertIn("mrr", c)
            self.assertGreaterEqual(c["search_ms_per_query"], 0)
        self.assertGreaterEqual(r["index_seconds"], 0)
        self.assertGreater(r["process_peak_rss_mb"], 0)

class LLMFailureTest(unittest.TestCase):
    def _answer(self, exc):
        from app import qa
        from app.retrieval import BM25Retriever

        class Broken:
            name = "broken"

            def complete(self, system, user):
                raise exc

        return qa.answer("지각 처리 어떻게 해요?", BM25Retriever(load_markdown("v1")), Broken())

    def test_quota_error_stops_instead_of_being_recorded(self):
        from app.llm import LLMUnavailableError

        with self.assertRaises(LLMUnavailableError):
            self._answer(LLMUnavailableError("429 RESOURCE_EXHAUSTED"))

    def test_format_error_is_recorded(self):
        res = self._answer(ValueError("JSON 없음"))
        self.assertIn("ValueError", res.error)


if __name__ == "__main__":
    unittest.main()
