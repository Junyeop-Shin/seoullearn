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

    def test_report_words_are_not_masked(self):
        # 보고서에 흔한 말: '과제 양'의 '과제'(이름), '복습중'(학교명), '성실한 학생'(이름)은 가리지 않는다. 가리면 저장할 때 글이 사라진다
        for q in ["과제 양이 많다고 함", "문제 양은 적당함", "개념 복습중 졸았음", "인강 수강중 질문함", "서술형 대비중", "다음달초 시험 예정",
                  "성실한 학생임", "매칭된 학생이 연락을 받지 않음"]:
            r = guard.check(q)
            self.assertEqual((r.pii, r.text), ([], q), q)

    def test_short_school_names_still_masked(self):
        for q in ["한빛고 2학년 멘티예요", "누리초 다녀요", "가람중 시험 범위예요", "명지고 다니는 멘티예요", "서울공고 2학년이에요", "대원외고 멘티예요"]:
            self.assertIn("[학교명]", guard.check(q).text, q)

    def test_marks_are_dropped_from_drafts(self):
        text = "(과목역량) [이름] 학생은 [학교명] 2학년이고 [전화번호]로 연락함\n인강을 [학교명]에서 들음. [멘티명]은 그대로"
        self.assertEqual(guard.drop_marks(text), "(과목역량) 학생은 2학년이고 연락함\n인강을 들음. [멘티명]은 그대로")

    def test_student_is_not_masked_as_a_name(self):
        g = guard.check("김민지 학생 어머님이 010-1234-5678로 상담 원하심")
        self.assertEqual(g.text, "[이름] 학생 어머님이 [전화번호]로 상담 원하심")

    def test_name_is_masked_whatever_particle_follows(self):
        for q in ["김민수 학생을 맡게 됐어요", "김민수 학생에게 연락했어요", "김민수 학생과 통화", "김민수 학생도 지각", "김민수 어머니가 연락",
                  "김민수 학생에 대해 문의드립니다", "담당이 김민수 학생으로 바뀌었어요", "민수 학생부터 시작", "김민수 어머니로부터 연락", "지한 학생이 결석"]:
            self.assertEqual(guard.check(q).pii, ["이름"], q)
        # '결석한 학생', '배정된 학생'처럼 줄기가 흔한 낱말인 꾸밈말과 문장을 여는 말은 이름이 아니다 (가리면 검색 질의와 저장한 글에서 그 말이 사라진다)
        for q in ["결석한 학생을 어떻게 처리하나요", "지각한 학생도 출석 인정되나요", "배정된 학생에게 연락", "수강하던 학생이 그만둠", "오늘 학생이 결석했어요",
                  "혹시 학생이 지각하면 어떻게 하나요", "시간확대 학생은 몇 회차인가요", "서울런 학생은 누구나 신청", "무단결석 학생의 활동비",
                  "수업에 학생이 늦게 들어옴", "과제를 학생이 직접 고름", "강남구 학생은 어디서 만나나요"]:
            r = guard.check(q)
            self.assertEqual((r.pii, r.text), ([], q), q)
        # 꾸밈말과 흔한 낱말은 이름이 아니다 ('는'으로 끝나는 말, 학년, 중학교 …). 평가셋 Q057의 질문이 바뀌지 않아야 한다
        for q in ["EBS랑 강남인강만 듣는 학생도 멘토링 신청돼요?", "수학을 싫어하는 학생을 어떻게 지도하나요", "중학교 학생도 되나요",
                  "매칭 학생을 바꾸고 싶어요", "어떤 학생에게 맞는 강좌인가요", "1학년 학생을 맡았어요", "결석 학생에게 연락"]:
            r = guard.check(q)
            self.assertEqual((r.pii, r.text), ([], q), q)

    def test_phone_formats(self):
        for n in ["02 123 4567", "02)123-4567", "+82 10-1234-5678", "010-1234-5678", "01012345678", "031-123-4567"]:
            self.assertEqual(guard.check(f"연락처는 {n} 입니다").pii, ["전화번호"], n)
        self.assertEqual(guard.check("2026 10 11에 17 00 시작").pii, [])

    def test_safety_words_and_training_names(self):
        for s in ["멘티가 가정폭력을 당하는 것 같아요", "학교폭력 피해를 말했어요", "아버지가 손찌검을 한대요", "멘티가 체벌을 받는다고 해요",
                  "성희롱을 당했다고 합니다", "밥을 못 먹고 굶는다고 해요", "왕따를 당한대요", "극단적 선택 얘기를 해요", "누나한테 맞았대요",
                  "아동학대가 의심돼요", "성폭력 피해를 입었다고 해요"]:
            self.assertTrue(guard.check(s).safety, s)
        # 필수교육·강좌 이름, 강좌가 학년이나 나에게 '맞는지'를 묻는 말은 신호가 아니다
        for s in ["아동학대 예방교육은 어디서 들어요?", "성폭력 예방교육 수료증은 어떻게 받아요?", "성희롱·성폭력 예방교육 이수", "학교폭력 예방교육 들어야 하나요?",
                  "비폭력대화 강좌는 언제 열려요?", "이 강좌가 중2에게 맞을까요?", "초등 5학년에게 맞을까요?", "저한테 맞을지 모르겠어요",
                  "멘토에게 맞을 시간대", "각자해결하기로 했어요", "추가출석 인정되나요?"]:
            self.assertFalse(guard.check(s).safety, s)

    def test_safety(self):
        self.assertTrue(guard.check("멘티가 집에서 맞는다는 얘기를 했어요").safety)
        self.assertFalse(guard.check("시간 맞춰서 들어가면 되나요?").safety)
        for s in ["멘티가 아버지에게 맞았습니다", "집에서 맞았어요", "아빠한테 맞아서 멍이 들었대요", "형한테 자주 맞는다고 함",
                  "집에서 매를 맞는다고 해요", "친구에게 얻어맞았다고 함", "멘티가 가출했다고 합니다"]:
            self.assertTrue(guard.check(s).safety, s)
        # '옳다·어울리다'의 '맞다'는 신호가 아니다 (보고서와 질문에 흔한 표현)
        # 낱말 중간에서 맞는 것은 신호가 아니다. 진짜 신호는 그대로 잡는다
        for s in ["문제를 혼자해결함", "글자해석 연습", "평가출제 경향 설명", "이투스 개념때려잡기 수강", "개념 때려잡기 3강"]:
            self.assertFalse(guard.check(s).safety, s)
        for s in ["자해 흔적이 있음", "아버지가 때려요", "때려잡았다고 함", "아버지가 술 마시면 때리신대요", "아빠가 화나면 때리고 물건을 던진대요", "형이 자꾸 때립니다",
                  "엄마가 때릴까 봐 무섭대요", "아빠한테 혼나고 맞았대요", "엄마한테 어제도 맞았다고 해요", "멘티가 맞고 온 것 같아요"]:
            self.assertTrue(guard.check(s).safety, s)
        # 때리는 뜻이 아닌 말: 보고서에 흔한 '멍 때리다', '때려 맞히다(찍다)'가 걸리면 초안이 통째로 막힌다
        for s in ["수업 중 멍 때리는 일이 많음", "멍때려서 다시 설명함", "객관식은 때려 맞히는 편", "답을 때려 맞춤", "암기를 때려 박음", "학원을 때려치웠다고 함",
                  "시간이 맞고 온라인으로 진행", "멘토님께 확인해보니 답이 맞았어요", "이음단에게 어제 문의함"]:
            self.assertFalse(guard.check(s).safety, s)
        for s in ["활동보고서는 7일 이내 제출이 맞아요?", "이음단에게 문의하는 게 맞아요?", "멘티에게 맞는 강좌 추천",
                  "서울런에서 수준에 맞는 강의를 골랐음", "10문제 중 8개 맞았다고 함", "이 강좌가 멘티에게 잘 맞았습니다",
                  "집에서 푼 문제는 다 맞았음", "시간이 맞아서 일정을 옮김"]:
            self.assertFalse(guard.check(s).safety, s)

    def test_pg_store_reconnects_once_after_db_restart(self):
        import numpy as np

        from app.vector_store import PgVectorStore

        class Conn:
            def __init__(self, dead=False):
                self.dead = dead

            def execute(self, sql, params=None):
                if self.dead and params:
                    raise ConnectionError("server closed the connection")
                return self

            def fetchall(self):
                return [("c1", 0.9)]

        made = []

        def connect(url, autocommit):
            made.append(Conn(dead=not made))   # 첫 연결만 끊긴 상태
            return made[-1]

        self.assertEqual(PgVectorStore("x", connect).search("k", np.zeros(2), 1), [("c1", 0.9)])
        self.assertEqual(len(made), 2)


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
        # 활동가이드 문서를 바꾼 유효한 공지가 그 문서의 청크에 적혀 있다 (v1에는 공지가 없어 비어 있다)
        self.assertTrue(all(not c.superseded_by for c in v1))
        changed = [c for c in v2 if c.superseded_by]
        self.assertTrue(changed and all(c.doc_type == "manual" for c in changed))
        self.assertTrue(any("시간확대" in t for c in changed if c.doc_id == "manual-2026-5-1" for t in c.superseded_by))

    def test_answer_carries_sources_and_changed_notices(self):
        # 답변이 근거로 쓴 자료의 본문을 함께 돌려주고, 그 활동가이드 내용을 바꾼 공지가 있으면 제목을 알린다 (규칙, LLM 미사용)
        v2 = load_markdown("v2")
        old = next(c for c in v2 if c.doc_id == "manual-2026-5-1")
        notice = next(c for c in v2 if "manual-2026-5-1" in c.supersedes)

        class Hits:
            def __init__(self, hits):
                self.hits = hits

            def search(self, q, k):
                return [(c, 1.0) for c in self.hits]

        class Cites:
            name = "fake"

            def __init__(self, nums):
                self.nums = nums

            def complete(self, system, user):
                return json.dumps({"answerable": "yes", "answer": "답", "citations": self.nums, "route": None})

        res = qa.answer("시간확대 조건이 뭐예요?", Hits([old, notice]), Cites([1]))
        self.assertEqual(res.sources, [{"cite": old.cite, "text": old.text}])
        self.assertEqual(res.changed_notices, [notice.title])
        # 그 공지를 함께 근거로 썼으면 따로 알리지 않는다
        self.assertEqual(qa.answer("시간확대 조건이 뭐예요?", Hits([old, notice]), Cites([1, 2])).changed_notices, [])


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

    def test_null_citations_and_trailing_text_do_not_discard_the_answer(self):
        d = qa.parse_output('{"answerable":"no","answer":"자료에 없습니다.","citations":null,"route":"운영사무국"}\n참고: {위 답은 초안입니다}')
        self.assertEqual((d["answer"], d["citations"]), ("자료에 없습니다.", []))
        self.assertEqual(qa.parse_output('{"answerable":"yes","answer":"x","citations":["²", 2]}')["citations"], [2])


class RouteAndEmbeddingTest(unittest.TestCase):
    def test_route_contact(self):
        self.assertIn("카카오톡 채널", qa.route_contact("이음단"))   # 자치구별 채널 바로가기는 화면이 만든다
        self.assertIn("02-3274-9212", qa.route_contact("운영사무국"))
        self.assertIsNone(qa.route_contact(None))

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


class ShuffleTest(unittest.TestCase):
    def test_shuffle_keeps_the_same_documents_and_is_repeatable(self):
        from evaluation.run_eval import ShuffledRetriever

        inner = BM25Retriever(load_markdown("v1"))
        base = [c.id for c, _ in inner.search("지각 처리 어떻게 해요?", 5)]
        a = [c.id for c, _ in ShuffledRetriever(inner, 1).search("지각 처리 어떻게 해요?", 5)]
        b = [c.id for c, _ in ShuffledRetriever(inner, 1).search("지각 처리 어떻게 해요?", 5)]
        c = [c.id for c, _ in ShuffledRetriever(inner, 2).search("지각 처리 어떻게 해요?", 5)]
        self.assertEqual(sorted(a), sorted(base))
        self.assertEqual(a, b)
        self.assertTrue(a != base or c != base)


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

    def test_provider_errors_are_not_swallowed_as_format_errors(self):
        # 키 오류 같은 제공사 오류를 형식 오류로 삼키면 '운영사무국에 문의'로 답하게 된다: 재시도 대상이 아니어도 LLMUnavailableError로 올린다
        from app.llm import LangChainLLM, LLMUnavailableError

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("app.llm.settings") as st, \
                unittest.mock.patch("langchain.chat_models.init_chat_model") as init:
            st.cache_dir, st.llm_rpm, st.llm_max_retries = Path(tmp), 0, 0
            init.return_value.invoke.side_effect = RuntimeError("401 invalid api key")
            with self.assertRaises(LLMUnavailableError):
                LangChainLLM("fake", "fake").complete("s", "질문")

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
    """문의 초안은 정해진 틀로 만든다 (LLM을 부르지 않는다)."""

    def _res(self, **kw):
        base = dict(question="가람중 멘티가 학습사이트를 바꾸고 싶대요. 연락처는 010-1234-5678", answer="자료에 없습니다.", answerable="no", route="운영사무국")
        return qa.QAResult(**{**base, **kw})

    def test_draft_for_unanswered_question(self):
        from app import inquiry

        d = inquiry.build(self._res())
        self.assertTrue(d.text.startswith("안녕하세요, 서울런 멘토입니다."))
        self.assertIn("멘티가 학습사이트를 바꾸고 싶대요", d.text)
        self.assertIn("찾아보았지만 해당 내용을 찾지 못했습니다. 확인 부탁드립니다.", d.text)
        self.assertIn("02-3274-9212", d.contact)
        # 가린 정보와 자리표시는 초안에 남기지 않는다
        for word in ["가람중", "010-1234-5678", "[학교명]", "[전화번호]", "을(를)"]:
            self.assertNotIn(word, d.text)

    def test_partial_answer_names_what_was_checked(self):
        from app import inquiry

        d = inquiry.build(self._res(route="이음단", answerable="partial", cite_labels=["활동가이드 p.62 문의처별 담당 범위", "활동가이드 p.62 문의처별 담당 범위"]))
        self.assertIn("활동가이드 p.62 문의처별 담당 범위에서 일부 내용은 확인했지만 정확한 기준을 찾지 못했습니다.", d.text)
        self.assertIn("이음단", d.contact)
        self.assertNotIn("http", d.contact)   # 주소는 화면이 자치구별 목록에서 붙인다

    def test_no_draft_when_answered_or_safety(self):
        from app import inquiry

        self.assertIsNone(inquiry.build(self._res(answerable="yes")))
        self.assertIsNone(inquiry.build(self._res(safety=True, route="운영사무국(즉시)", answerable="yes")))
        self.assertIsNone(inquiry.build(self._res(route="운영사무국(즉시)")))
        # 답변을 만들다 실패한 것(형식 오류)은 자료에 없는 것이 아니다: '찾지 못했습니다'라는 초안을 만들지 않는다
        self.assertIsNone(inquiry.build(self._res(error="ValueError: JSON 없음")))


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
        # 완료보고서와 결과보고서는 화면이 따로 있어 활동보고서 안내로 보내지 않는다
        for q in ["완료보고서 초안 만들어 줘", "완료 보고서 써 줘", "성장활동 결과보고서 작성해 줘"]:
            self.assertEqual(classify_by_rule(q), "qa", q)

    def test_report_goes_to_screen_without_llm(self):
        llm = self.CountingLLM()
        s = self._graph(llm).invoke({"message": "4회차 활동보고서 초안 써 줘"})
        self.assertEqual((s["intent"], s["method"]), ("report", "rule"))
        self.assertIn("'내 멘티'에서 멘티를 고르면", s["result"]["answer"])
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

    def test_format_error_is_not_shown_as_not_found(self):
        # 답변의 형식이 깨지면 답변 상태를 비운다: 화면이 '자료에서 찾지 못했습니다'라고 하지 않고 문의 초안도 붙지 않는다. 문의처는 남는다
        class Broken(self.CountingLLM):
            def complete(self, system, user):
                return "잘 모르겠습니다"

        r = self._graph(Broken()).invoke({"message": "지각 처리 어떻게 해요?"})["result"]
        self.assertTrue(r["error"])
        self.assertIsNone(r["answerable"])
        self.assertIsNone(r["inquiry_draft"])
        self.assertEqual(r["route"], "운영사무국")

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
