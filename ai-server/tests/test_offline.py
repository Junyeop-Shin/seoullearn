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
        expired = [c for c in v2 if c.status == "expired"]
        self.assertTrue(expired and all(c.recurring == "yearly" for c in expired), "만료 공지는 매년 반복되는 공고만 지난 공고로 남는다")
        self.assertTrue(expired[0].cite.startswith("지난 공고"))
        self.assertIn("만료된 지난 공고", qa.build_context(expired[:1]))
        self.assertIn("지난 공고 기준", qa.SYSTEM)
        self.assertTrue(all(c.page for c in v1))


class RetrievalTest(unittest.TestCase):
    def test_bm25_finds_late_rule(self):
        r = BM25Retriever(load_markdown("v1"))
        top = [c.doc_id for c, _ in r.search("지각 처리 어떻게 해요?", 5)]
        self.assertIn("manual-2026-3-1", top)

    def test_glossary(self):
        q = GlossaryExpander().expand("주간보고서 늦게 내면?")
        self.assertIn("활동보고서", q)

    def test_reranker_reorders_candidates(self):
        from app.retrieval import OverlapReranker, RerankingRetriever

        chunks = load_markdown("v1")

        class Reversed:  # 정답을 맨 뒤에 두는 엉터리 검색기
            name = "reversed"

            def search(self, query, k):
                return list(reversed(BM25Retriever(chunks).search(query, k)))

        r = RerankingRetriever(Reversed(), OverlapReranker(), pool=20)
        top = r.search("지각 처리 어떻게 해요?", 5)
        self.assertEqual(len(top), 5)
        self.assertEqual(sorted((s for _, s in top), reverse=True), [s for _, s in top])
        self.assertTrue(r.name.endswith("+rerank"))

    def test_rerank_pipeline_builds_without_model(self):
        from app.pipelines import build_retriever
        from app.retrieval import OverlapReranker

        r, _ = build_retriever("md_bm25", "v1")
        self.assertFalse(hasattr(r, "reranker"))
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.retrieval.settings") as st:
            st.cache_dir = Path(tmp)
            st.data_dir = Path(__file__).resolve().parents[2] / "data"
            r, _ = build_retriever("md_hybrid_glossary_rerank", "v1", embedder=HashEmbedder(dim=256), reranker=OverlapReranker())
            self.assertEqual(len(r.search("활동비 언제 들어와요?", 5)), 5)

    def test_pgvector_backend_uses_store(self):
        from app.retrieval import VectorRetriever
        from app.vector_store import vector_literal

        class FakeStore:  # DB 없이 pgvector 경로만 확인
            def __init__(self):
                self.rows, self.added = {}, 0

            def has_index(self, key):
                return key in self.rows

            def add(self, key, chunks, matrix, model):
                self.added += 1
                self.rows[key] = [(c.id, v) for c, v in zip(chunks, matrix)]

            def search(self, key, q, k):
                scored = sorted(((cid, float(v @ q)) for cid, v in self.rows[key]), key=lambda x: (-x[1], x[0]))
                return scored[:k]

        chunks, emb, store = load_markdown("v1")[:30], HashEmbedder(dim=256), FakeStore()
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.retrieval.settings") as st:
            st.cache_dir = Path(tmp)
            pg = VectorRetriever(chunks, emb, backend="pgvector", store=store)
            VectorRetriever(chunks, emb, backend="pgvector", store=store)  # 두 번째는 다시 색인하지 않는다
            file = VectorRetriever(chunks, emb, backend="file")
            a = [c.id for c, _ in pg.search("활동비 지급일", 5)]
            b = [c.id for c, _ in file.search("활동비 지급일", 5)]
        self.assertEqual(store.added, 1)
        self.assertEqual(a, b)
        self.assertEqual(vector_literal(emb.embed_query("가")[:2] * 0), "[0.00000000,0.00000000]")

    def test_tokenize(self):
        self.assertIn("활동", tokenize("활동보고서"))


class ParseTest(unittest.TestCase):
    def test_parse_code_block(self):
        d = qa.parse_output('```json\n{"answerable":"partial","answer":"x","citations":[2,"1"],"route":"이음단"}\n```')
        self.assertEqual(d["citations"], [2, 1])
        self.assertEqual(d["route"], "이음단")

    def test_missing_route_key_means_no_route(self):
        d = qa.parse_output('{"answerable":"yes","answer":"x","citations":[1]}')
        self.assertIsNone(d["route"])

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

class ChangeNotedMetricTest(unittest.TestCase):
    def test_change_noted_rate(self):
        from evaluation.metrics import notes_change, summarize

        self.assertTrue(notes_change("8월 10일 신청 건부터 멘티가 직접 신청하는 것으로 바뀌었습니다."))
        self.assertFalse(notes_change("멘티가 직접 신청합니다."))

        def rec(answer, supersede):
            return {"gold": {"evidence": [], "answerable": "yes", "route": None, "answer": ""}, "ranks": [], "category": "공지변경",
                    "supersede": supersede, "cite_ok": [],
                    "pred": {"answerable": "yes", "route": None, "answer": answer, "citations": [], "error": None}}

        s = summarize([rec("이전에는 멘토가 대신 신청했습니다.", True), rec("멘티가 신청합니다.", True), rec("기존과 같습니다.", False)], 5)
        self.assertEqual(s["answer"]["change_noted_n"], 2)
        self.assertEqual(s["answer"]["change_noted_rate"], 50.0)


class LLMCacheTest(unittest.TestCase):
    def test_api_server_models_do_not_cache(self):
        # API 서버가 쓰는 경로(main._llm → get_chat_model)는 캐시를 켜지 않아야 한다
        import inspect

        from app import llm, main

        self.assertFalse(inspect.signature(llm.get_chat_model).parameters["use_cache"].default)
        self.assertFalse(inspect.signature(llm.LangChainLLM.__init__).parameters["use_cache"].default)
        self.assertIn('get_chat_model("answer")', inspect.getsource(main._llm))
        self.assertNotIn("get_eval_model", inspect.getsource(main))
        self.assertNotIn("get_eval_model", inspect.getsource(__import__("app.router", fromlist=["x"])))

    def test_no_cache_means_no_file(self):
        from app.llm import LangChainLLM

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.llm.settings") as st, \
                unittest.mock.patch("langchain.chat_models.init_chat_model") as init:
            st.cache_dir, st.llm_rpm, st.llm_max_retries = Path(tmp), 0, 0
            init.return_value.invoke.return_value.content = "답변"
            self.assertEqual(LangChainLLM("fake", "fake").complete("s", "가람중 멘티 질문"), "답변")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.assertEqual(LangChainLLM("fake", "fake", use_cache=True).complete("s", "평가 질문"), "답변")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["llm_cache.jsonl"])


class LeakCheckScriptTest(unittest.TestCase):
    def _mod(self):
        import importlib.util

        path = Path(__file__).resolve().parents[2] / "scripts" / "check_no_leak.py"
        spec = importlib.util.spec_from_file_location("check_no_leak", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_fragments_and_detection(self):
        c = self._mod()
        frags = c.fragments(["멘티가 부모님이랑 크게 다퉈서 집중을 못 했어요 010-0000-0000 활동보고서 작성"], "활동보고서 작성")
        self.assertIn("010-0000-0000", frags)
        self.assertNotIn("활동보고서 작성", frags)  # 매뉴얼에 원래 있는 말은 조각으로 쓰지 않는다
        self.assertTrue(all(len(f) >= c.MIN_FRAGMENT for f in frags))
        target = "부모님이랑 크게"
        self.assertIn(target, frags)
        self.assertEqual(c.find_in("로그 한 줄: 부모님이랑 크게 다퉈서".encode("utf-8"), [target]), [target])
        self.assertEqual(c.find_in(json.dumps({"v": "부모님이랑 크게"}).encode("ascii"), [target]), [target])  # \\uXXXX로 저장된 경우
        self.assertEqual(c.find_in("qa len=30 answerable=yes".encode("utf-8"), frags), [])


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

    def test_unanswered_question_always_has_route(self):
        from app.retrieval import BM25Retriever

        class NoRoute:
            name = "noroute"

            def __init__(self, answerable):
                self.answerable = answerable

            def complete(self, system, user):
                return json.dumps({"answerable": self.answerable, "answer": "자료에 없습니다.", "citations": [], "route": None})

        r = BM25Retriever(load_markdown("v1"))
        self.assertEqual(qa.answer("지각 처리 어떻게 해요?", r, NoRoute("no")).route, "운영사무국")
        self.assertEqual(qa.answer("지각 처리 어떻게 해요?", r, NoRoute("partial")).route, "운영사무국")
        self.assertIsNone(qa.answer("지각 처리 어떻게 해요?", r, NoRoute("yes")).route)

    def test_format_error_is_recorded(self):
        res = self._answer(ValueError("JSON 없음"))
        self.assertIn("ValueError", res.error)


class InquiryDraftTest(unittest.TestCase):
    class Fake:
        name = "fake"

        def __init__(self, out):
            self.out, self.calls = out, []

        def complete(self, system, user):
            self.calls.append(user)
            return self.out

    def _res(self, **kw):
        base = dict(question="가람중 멘티가 학습사이트를 바꾸고 싶대요", answer="자료에 없습니다.", answerable="no", route="운영사무국",
                    cite_labels=["활동가이드 p.62 문의처별 담당 범위"])
        return qa.QAResult(**{**base, **kw})

    def test_draft_for_unanswered_question(self):
        from app import inquiry

        llm = self.Fake('{"draft": "안녕하세요, 서울런 멘토입니다. 학습사이트 변경이 가능한지 문의드립니다. 확인 부탁드립니다."}')
        d = inquiry.build(self._res(), llm)
        self.assertIn("문의드립니다", d.text)
        self.assertIn("02-3274-9212", d.contact)
        self.assertIsNone(d.error)
        self.assertNotIn("가람중", llm.calls[0])  # LLM에는 가린 질문만 간다
        self.assertIn("p.62", llm.calls[0])

    def test_ieumdan_uses_openchat_link(self):
        from app import inquiry

        d = inquiry.build(self._res(route="이음단", answerable="partial"), self.Fake('{"draft": "문의드립니다."}'),
                          "https://open.kakao.com/o/abc123")
        self.assertEqual(d.contact, "https://open.kakao.com/o/abc123")

    def test_no_draft_when_answered_or_safety(self):
        from app import inquiry

        llm = self.Fake('{"draft": "x"}')
        self.assertIsNone(inquiry.build(self._res(answerable="yes"), llm))
        self.assertIsNone(inquiry.build(self._res(safety=True, route="운영사무국(즉시)", answerable="yes"), llm))
        self.assertIsNone(inquiry.build(self._res(route="운영사무국(즉시)"), llm))
        self.assertEqual(llm.calls, [])

    def test_bad_output_is_recorded_and_pii_masked(self):
        from app import inquiry

        d = inquiry.build(self._res(), self.Fake("초안입니다"))
        self.assertIn("ValueError", d.error)
        self.assertIn("문의드립니다", d.text)
        self.assertNotIn("가람중", d.text)
        d2 = inquiry.build(self._res(), self.Fake('{"draft": "가람중 김민지 학생 관련 문의드립니다. 010-1234-5678"}'))
        self.assertNotIn("가람중", d2.text)
        self.assertNotIn("010-1234-5678", d2.text)


class RouterTest(unittest.TestCase):
    class CountingLLM:
        name = "fake"

        def __init__(self, out='{"intent": "report"}'):
            self.out, self.calls = out, 0

        def complete(self, system, user):
            self.calls += 1
            if "의도를 하나로 분류" in system:
                return self.out
            return json.dumps({"answerable": "yes", "answer": "(가짜 답변)", "citations": [1], "route": None}, ensure_ascii=False)

    def _graph(self, llm):
        from app import router

        return router.build_graph(lambda: llm, lambda: BM25Retriever(load_markdown("v1")))

    def test_rule_classification(self):
        from app.router import classify_by_rule

        self.assertEqual(classify_by_rule("지각하면 어떻게 처리돼요?"), "qa")
        self.assertEqual(classify_by_rule("활동보고서 제출 기한이 언제예요?"), "qa")  # 보고서에 관한 질문
        self.assertEqual(classify_by_rule("2회차 활동보고서 초안 만들어 줘"), "report")
        self.assertEqual(classify_by_rule("종합계획서 회차별 커리큘럼 짜 줘"), "plan")
        self.assertIsNone(classify_by_rule("활동보고서 좀 봐 줘"))  # 무엇을 원하는지 애매함
        self.assertIsNone(classify_by_rule("보고서랑 계획서 둘 다 써 줘"))

    def test_report_goes_to_screen_without_llm(self):
        llm = self.CountingLLM()
        s = self._graph(llm).invoke({"message": "4회차 활동보고서 초안 써 줘"})
        self.assertEqual((s["intent"], s["method"]), ("report", "rule"))
        self.assertIn("해당 화면으로 이동", s["result"]["answer"])
        self.assertIn("진행 회차", s["result"]["required_inputs"])
        self.assertNotIn("멘티 성명", s["result"]["required_inputs"])  # 개인정보 칸은 입력받지 않는다
        self.assertEqual(llm.calls, 0)

    def test_plan_goes_to_screen(self):
        s = self._graph(self.CountingLLM()).invoke({"message": "국어 16회차 커리큘럼 짜 줘"})
        self.assertEqual(s["intent"], "plan")
        self.assertEqual(s["result"]["form_id"], "plan_initial")
        self.assertTrue(s["result"]["required_inputs"])

    def test_safety_skips_classification_and_llm(self):
        llm = self.CountingLLM()
        s = self._graph(llm).invoke({"message": "멘티가 집에서 맞는다는 얘기를 했어요. 보고서 써 줘"})
        self.assertEqual((s["intent"], s["method"]), ("safety", "guard"))
        self.assertEqual(s["result"]["route"], "운영사무국(즉시)")
        self.assertNotIn("inquiry_draft", s["result"])
        self.assertEqual(llm.calls, 0)

    def test_qa_path_and_ambiguous_uses_llm_with_masked_text(self):
        llm = self.CountingLLM()
        s = self._graph(llm).invoke({"message": "지각 처리 어떻게 해요?"})
        self.assertEqual((s["intent"], s["method"]), ("qa", "rule"))
        self.assertEqual(s["result"]["answer"], "(가짜 답변)")

        seen = []

        class Spy(self.CountingLLM):
            def complete(self, system, user):
                seen.append(user)
                return super().complete(system, user)

        s = self._graph(Spy()).invoke({"message": "가람중 멘티 활동보고서 좀 봐 줘"})
        self.assertEqual((s["intent"], s["method"]), ("report", "llm"))
        self.assertNotIn("가람중", seen[0])
        self.assertEqual(s["pii_masked"], ["학교명"])

    def test_bad_llm_intent_is_recorded_and_falls_back_to_qa(self):
        s = self._graph(self.CountingLLM(out="잘 모르겠습니다")).invoke({"message": "활동보고서 좀 봐 줘"})
        self.assertEqual((s["intent"], s["method"]), ("qa", "llm"))
        self.assertTrue(s["classify_error"])

    def test_intent_eval_runs_without_llm(self):
        from evaluation.intent_eval import evaluate

        items = json.loads((Path(__file__).resolve().parents[2] / "eval" / "intent_set.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual(len(items), 30)
        s = evaluate(items)
        self.assertEqual(s["llm_calls"], 0)
        self.assertEqual(s["per_intent"]["safety"]["correct"], s["per_intent"]["safety"]["n"])
        s2 = evaluate(items, self.CountingLLM())
        self.assertEqual(s2["by_method"].get("unresolved", 0), 0)

    def test_chat_endpoint(self):
        from fastapi.testclient import TestClient

        from app import main

        llm = self.CountingLLM()
        with unittest.mock.patch.object(main, "_graph", lambda: self._graph(llm)):
            r = TestClient(main.app).post("/chat", json={"message": "3회차 활동보고서 초안 써 줘"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["intent"], "report")
        self.assertEqual(body["screen"], "활동보고서 작성")
        self.assertTrue(body["required_inputs"])

if __name__ == "__main__":
    unittest.main()
