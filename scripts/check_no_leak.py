"""입력 본문이 서버 어디에도 남지 않는지 검사한다.

가상 회차 기록(synthetic/sessions_M1.json 등)의 내용으로 backend의 /api/qa와 /api/chat을 10번,
활동보고서 초안(/api/drafts/activity_report)을 3번 호출한 뒤, 보낸 문장의 조각이 아래 세 곳에 남았는지 찾는다.
  1) frontend, backend, ai-server, db 컨테이너 로그
  2) DB 전체 (pg_dump). '답 못 한 질문 모음' 테이블은 가린 질문 문장을 일부러 저장하므로 따로 검사한다:
     전화번호·이름·학교명과 정서·성적 내용이 없는지, 질문한 사람을 알 수 있는 열이 없는지
  3) .cache 폴더에서 이번 호출 뒤에 새로 생기거나 늘어난 부분
     (평가 실행이 남긴 캐시에는 같은 가상 데이터가 들어 있을 수 있어, 호출 전 상태와 비교한다)

  docker compose up -d backend          # db, ai-server도 함께 뜬다
  python scripts/check_no_leak.py
남은 곳이 있으면 목록을 보여주고 종료 코드 1. 실제 LLM을 15번 안팎 호출한다 (가상 데이터만 보낸다).
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ["frontend", "backend", "ai-server", "db"]
MIN_FRAGMENT = 8  # 이보다 짧은 조각은 우연히 겹칠 수 있어 쓰지 않는다


# ------------------------------------------------------------------ 보낼 문장과 조각
def build_messages() -> list[str]:
    """가짜 전화번호, 이름, 학교명, 정서 메모가 든 회차를 반드시 넣어 10개를 만든다."""
    m1 = json.loads((ROOT / "synthetic" / "sessions_M1.json").read_text(encoding="utf-8"))["sessions"]
    m2 = json.loads((ROOT / "synthetic" / "sessions_M2.json").read_text(encoding="utf-8"))["sessions"]
    by_no = {s["session_no"]: s for s in m1}
    picked = [by_no[n] for n in (6, 8, 10, 1, 2, 3, 4, 5, 7) if n in by_no]
    school = next((s for s in m2 if any("학교" in t for t in s.get("traps", []))), m2[0])
    texts = []
    for s in picked + [school]:
        i = s["mentor_input"]
        parts = [i.get("notes", ""), i.get("attendance", ""), i.get("homework", ""), i.get("etc", ""), i.get("requests", "")]
        text = " ".join(p for p in parts if p).strip()
        texts.append((text + " 이 내용으로 어떻게 하면 되나요?")[:900])
    # 마지막 둘은 짧은 질문으로 바꾼다: '답 못 한 질문 모음'에 저장될 만한 모양이고 개인정보가 섞여 있다
    short = ["가람중 멘티 활동인증서를 영문으로도 받을 수 있나요? 010-0000-0000",
             "김민지 학생 어머님이 멘토 자격증 사본을 달라고 하시는데 줘도 되나요?"]
    return texts[:8] + short


def build_drafts() -> list[dict]:
    """활동보고서 초안 입력 3건: 실명·전화번호(6회차), 성적(8회차), 정서 메모(10회차)."""
    m1 = json.loads((ROOT / "synthetic" / "sessions_M1.json").read_text(encoding="utf-8"))["sessions"]
    out = []
    for s in m1:
        if s["session_no"] in (6, 8, 10):
            out.append({"session_date": s["date"], "session_no": s["session_no"], "subject": "수학", "course": "가상 강좌",
                        "status": s["status"], **s["mentor_input"]})
    return out


def fragments(messages: list[str], known_public: str) -> list[str]:
    """보낸 문장에서만 나오는 조각. 매뉴얼·공지·양식에 원래 있는 말은 뺀다 (DB의 매뉴얼 색인과 헷갈리지 않게)."""
    out: set[str] = set()
    for m in messages:
        words = m.split()
        for n in (2, 3):
            for k in range(len(words) - n + 1):
                frag = " ".join(words[k : k + n])
                if len(frag) >= MIN_FRAGMENT and frag not in known_public:
                    out.add(frag)
        out.update(re.findall(r"01[016789][- .]?\d{3,4}[- .]?\d{4}", m))  # 전화번호는 그대로도 찾는다
    return sorted(out)


def encodings(frag: str) -> list[bytes]:
    """같은 조각이 저장될 수 있는 모양들: UTF-8 그대로, JSON의 \\uXXXX, URL 인코딩."""
    from urllib.parse import quote

    return list({frag.encode("utf-8"), json.dumps(frag, ensure_ascii=True)[1:-1].encode("ascii"), quote(frag).encode("ascii")})


def find_in(data: bytes, frags: list[str]) -> list[str]:
    return [f for f in frags if any(e in data for e in encodings(f))]


def public_text() -> str:
    parts = []
    for pattern in ("data/manual/*.md", "data/notice/*.md", "forms/*.json", "data/glossary.csv"):
        parts += [p.read_text(encoding="utf-8") for p in ROOT.glob(pattern)]
    return "\n".join(parts)


# ------------------------------------------------------------------ 호출
class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _token(self) -> str:
        return next((c.value for c in self.jar if c.name == "XSRF-TOKEN"), "")

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, str]:
        req = urllib.request.Request(self.base + path, method=method,
                                     data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        if method != "GET":
            req.add_header("X-XSRF-TOKEN", self._token())
        try:
            with self.opener.open(req, timeout=120) as res:
                return res.status, res.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")


def send(base: str, messages: list[str], drafts: list[dict]) -> tuple[str, list[int]]:
    c = Client(base)
    username = "leakcheck_" + secrets.token_hex(4)
    password = secrets.token_urlsafe(16)
    c.call("GET", "/api/auth/csrf")
    code, body = c.call("POST", "/api/auth/signup", {"username": username, "password": password})
    if code != 201:
        raise SystemExit(f"가입 실패 ({code}): {body[:200]}  backend가 떠 있는지 확인해 주세요.")
    code, _ = c.call("POST", "/api/auth/login", {"username": username, "password": password})
    if code != 200:
        raise SystemExit(f"로그인 실패 ({code})")
    codes = []
    for n, m in enumerate(messages):
        path, body = ("/api/qa", {"question": m}) if n % 2 == 0 else ("/api/chat", {"message": m})
        code, _ = c.call("POST", path, body)
        codes.append(code)
    for d in drafts:
        code, _ = c.call("POST", "/api/drafts/activity_report", {"inputs": d})
        codes.append(code)
    c.call("POST", "/api/auth/logout")
    return username, codes


# ------------------------------------------------------------------ 검사 대상
def compose(*args: str) -> bytes:
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, check=False).stdout


def cache_sizes() -> dict[str, int]:
    cache = ROOT / ".cache"
    return {str(f.relative_to(cache)): f.stat().st_size for f in cache.rglob("*") if f.is_file()} if cache.exists() else {}


def scan(frags: list[str], since: str, before: dict[str, int]) -> list[tuple[str, list[str]]]:
    """(위치, 찾은 조각 목록)."""
    found = []
    for svc in SERVICES:
        logs = subprocess.run(["docker", "compose", "logs", "--no-color", "--since", since, svc], cwd=ROOT,
                              capture_output=True, check=False)
        hit = find_in(logs.stdout + logs.stderr, frags)
        if hit:
            found.append((f"{svc} 컨테이너 로그", hit))
    dump = compose("exec", "-T", "db", "pg_dump", "-U", "seoullearn", "--data-only", "--inserts",
                   "--exclude-table-data=unanswered_question", "seoullearn")
    if not dump:
        raise SystemExit("DB 내용을 읽지 못했습니다. db 컨테이너가 떠 있는지 확인해 주세요.")
    hit = find_in(dump, frags)
    if hit:
        found.append(("DB (pg_dump)", hit))
    cache = ROOT / ".cache"
    for f in sorted(cache.rglob("*")) if cache.exists() else []:
        if f.is_file():
            data, old = f.read_bytes(), before.get(str(f.relative_to(cache)))
            if old is not None and len(data) >= old:
                data = data[old:]  # 뒤에 덧붙은 부분만 본다. 줄었거나 새 파일이면 전체를 본다
            hit = find_in(data, frags)
            if hit:
                found.append((f".cache/{f.relative_to(cache)}", hit))
    return found


# ------------------------------------------------------------------ 답 못 한 질문 모음
UNANSWERED_COLUMNS = {"id", "question", "answerable", "route", "created_on"}
# 가상 데이터에 넣어 둔 개인정보와, 저장되면 안 되는 내용의 표지
TRAPS = re.compile(r"01[016789][- .]?\d{3,4}[- .]?\d{4}|김민지|가람중|부모님|다퉈|다퉜|등급|성적|장염|군입대")


def psql(sql: str) -> list[str]:
    out = compose("exec", "-T", "db", "psql", "-U", "seoullearn", "-d", "seoullearn", "-At", "-c", sql)
    return [x for x in out.decode("utf-8", "replace").splitlines() if x.strip()]


def unanswered_max_id() -> int:
    rows = psql("SELECT COALESCE(MAX(id), 0) FROM unanswered_question")
    return int(rows[0]) if rows and rows[0].isdigit() else 0


def check_unanswered(before_id: int) -> tuple[list[str], int]:
    """(문제 목록, 이번 호출로 저장된 건수). 검사 뒤 이번 호출로 생긴 행은 지운다."""
    problems = []
    cols = set(psql("SELECT column_name FROM information_schema.columns WHERE table_name = 'unanswered_question'"))
    if cols and cols != UNANSWERED_COLUMNS:
        problems.append(f"답 못 한 질문 테이블에 예상 밖의 열이 있습니다: {sorted(cols - UNANSWERED_COLUMNS)}")
    rows = psql(f"SELECT question FROM unanswered_question WHERE id > {before_id}")
    bad = [r for r in rows if TRAPS.search(r)]
    if bad:
        problems.append(f"답 못 한 질문 테이블에 개인정보·민감 내용이 든 행이 {len(bad)}건 있습니다 (예: {bad[0][:30]!r})")
    psql(f"DELETE FROM unanswered_question WHERE id > {before_id}")
    return problems, len(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8080")
    a = p.parse_args()
    messages, drafts = build_messages(), build_drafts()
    frags = fragments(messages + [" ".join(str(v) for v in d.values()) for d in drafts], public_text())
    if len(frags) < 50:
        raise SystemExit("검사할 조각이 너무 적습니다. 가상 데이터를 확인해 주세요.")
    since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = cache_sizes()
    before_id = unanswered_max_id()
    username, codes = send(a.base, messages, drafts)
    time.sleep(2)  # 로그가 밀려 나올 시간
    try:
        found = scan(frags, since, before)
        problems, stored = check_unanswered(before_id)
    finally:
        compose("exec", "-T", "db", "psql", "-U", "seoullearn", "-d", "seoullearn", "-c",
                f"DELETE FROM app_user WHERE username = '{username}'")
    ok_calls = sum(c == 200 for c in codes)
    print(f"호출 {len(codes)}회 (성공 {ok_calls}회, 상태 코드 {codes}), 검사한 조각 {len(frags)}개")
    print(f"검사 대상: {', '.join(SERVICES)} 컨테이너 로그, DB 전체, .cache 폴더에 새로 쓰인 부분")
    if ok_calls < len(codes):
        print("경고: 실패한 호출이 있습니다. 실패한 호출은 LLM까지 가지 않았을 수 있어 검사가 약해집니다.")
    print(f"답 못 한 질문 모음에 저장된 건수: {stored}건 (검사 뒤 삭제)")
    for p in problems:
        print(f"- {p}")
    if not found and not problems:
        print("OK: 입력 본문 조각이 남은 곳이 없습니다.")
        return 0 if ok_calls == len(codes) else 1
    if not found:
        return 1
    print("\n입력 본문 조각이 남은 곳:")
    for where, hit in found:
        print(f"- {where}: {len(hit)}개 (예: {hit[0][:30]!r})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
