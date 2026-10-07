#!/bin/sh
# 개선 하나를 적용한 뒤 같은 평가셋으로 다시 잰다.
#   scripts/measure.sh retrieval "메모" 설정1 [설정2 ...]   검색만 (LLM 호출 없음)
#   scripts/measure.sh answer "메모" 설정 [코퍼스]           답변 생성 + 채점
set -e
mode=$1; note=$2; shift 2
run() { docker compose run --rm ai-server "$@" 2>&1 | grep -v 'Container\|Loading weights\|unauthenticated\|Q0[0-9][0-9]' ; }
if [ "$mode" = retrieval ]; then
  for c in "$@"; do run python -m evaluation.run_eval --config "$c" --corpus v1 --retrieval-only --note "$note" | grep -E '"(config|hit@1|hit@5|mrr)"|저장'; done
else
  corpus=${2:-v1}
  out=$(run python -m evaluation.run_eval --config "$1" --corpus "$corpus" --note "$note" | grep '저장:' | sed 's/저장: \([^ ]*\).*/\1/')
  [ -n "$out" ] || { echo "답변 생성 실패"; exit 1; }
  run python -m evaluation.judge "$out" | tail -2
  python3 -c "import json,sys; s=json.load(open(sys.argv[1])); print(json.dumps({'retrieval':s['retrieval'],'answer':s['answer'],'judge':s['judge']},ensure_ascii=False))" "$(echo "$out" | sed 's#^/project/##; s#\.jsonl$#_judged.summary.json#')"
fi
