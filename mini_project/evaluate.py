"""[버릴지도 ⑤] 검색 · 생성을 같은 문항으로 잰다 — README · CONTEXT 에 적을 숫자를 만든다

  «한 번에 하나만 바꾼다» — 무엇이 효과였는지 알려면 나머지는 고정해야 한다.

    E1 분할       python evaluate.py retrieval --index index_recursive   ↔   python evaluate.py retrieval
    E2 검색 전략   retrieval 표의 basic 줄 ↔ multiquery 줄 (year_bonus 0)
    E3 year_bonus  retrieval 표의 같은 전략 안에서 0 · 0.5g · 1g · 2g
    E4 프롬프트    python evaluate.py answer   ↔   python evaluate.py answer --prompt recent

  retrieval — 전략 × year_bonus 격자
    ① basic · bonus 0 으로 전 문항의 «1위와 3위의 거리 차» 중앙값 g 를 잰다
       → year_bonus 후보를 0 · 0.5g · 1g · 2g 로 정한다 (거리의 눈금을 모르는 채 숫자를 찍지 않으려고)
    ② 칸마다 Top-1 · Top-3 정답 수, 유형별 Top-3, 연도충돌 문항의 top-1 이 2026 인 수, 평균 검색 시간
    ③ multiquery 는 다시 쓴 질문이 실행마다 달라질 수 있다 → 3회 반복해 최소~최대를 적는다

  answer — scratch_eval.py 의 채점 규칙 그대로
    정답 = must 중 하나 포함  그리고  bad 없음  그리고  자기모순 아님
    자기모순 = must 가 «찾지 못했» 이 아닌데 답에 «찾지 못했» 이 들어 있음 (정답을 말하고 스스로 뒤집음)

  채택 규칙: 더 복잡한 쪽(multiquery · bonus > 0 · 긴 프롬프트)은 정답 수가 **실제로 늘 때만**. 같으면 단순한 쪽.
            1~2문항 차이는 «차이가 있다» 가 아니라 «같은 수준» 이다 (30문항은 작은 표본).
            효과가 없었으면 없었다고 적는다.

실행 (이 폴더에서 · 측정 전에 ollama ps 로 다른 모델이 떠 있지 않은지 확인):
    python evaluate.py retrieval
    python evaluate.py retrieval --index index_recursive
    python evaluate.py answer
    python evaluate.py answer --strategy multiquery --year-bonus 0.05
    python evaluate.py answer --prompt recent
    python evaluate.py answer --ids scratch            # scratch_eval.py 의 6문항만 (10주차 6/6 과 비교)
    python evaluate.py answer --model gemma3:4b        # (선택) 수업 기본 모델과 비교
"""

import os
import sys

# ★ config 를 import 하기 **전에** — 인덱스 · 모델 · 프롬프트는 «실행 한 번 = 설정 하나» 라서 환경 변수로 넘긴다
for _flag, _key in (("--index", "RECYCLE_INDEX"), ("--model", "RECYCLE_MODEL"), ("--prompt", "RECYCLE_PROMPT")):
    for _i, _arg in enumerate(sys.argv):
        if _arg == _flag and _i + 1 < len(sys.argv):
            os.environ[_key] = sys.argv[_i + 1]
        elif _arg.startswith(_flag + "="):
            os.environ[_key] = _arg.split("=", 1)[1]

import config  # noqa: E402,F401
from config import EMBED_MODEL, HERE, INDEX_DIR, MODEL, PROMPT_VARIANT, SHORT_NAME, STRATEGIES, TAG, TOP_K  # noqa: E402

import argparse  # noqa: E402
import json  # noqa: E402
import statistics  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import rag_backend as rb  # noqa: E402
from questions import NO_RETRIEVAL, QUESTIONS, SCRATCH_IDS, YEAR_WATCH, is_hit  # noqa: E402

RESULT_DIR = HERE / "eval_results"
REPEATS = 3                                    # multiquery 반복 횟수
KINDS = ("표준", "생활용어", "연도충돌", "품목사전")
OX = {True: "○", False: "×"}


# ── 공통 ───────────────────────────────────────────────────────────
def pick(ids: str | None) -> list[tuple]:
    if not ids:
        return QUESTIONS
    want = SCRATCH_IDS if ids == "scratch" else tuple(i.strip() for i in ids.split(","))
    by_id = {q[0]: q for q in QUESTIONS}
    unknown = [i for i in want if i not in by_id]
    if unknown:
        raise SystemExit(f"모르는 문항 id: {unknown}")
    return [by_id[i] for i in want]


def vram() -> str:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.strip()
        used, total = out.splitlines()[0].split(",")
        return f"{int(used) / 1024:.2f} / {int(total) / 1024:.0f} GB"
    except Exception:
        return "?"


def ollama_ps() -> str:
    try:
        return subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "?"


def header(title: str, extra: dict) -> list[str]:
    manifest = rb.read_manifest()
    rows = {"인덱스": f"{INDEX_DIR.name} ({manifest.get('chunks', '?')}청크 · {manifest.get('mode', '?')})",
            "임베딩": EMBED_MODEL, **extra, "top_k": TOP_K}
    return [f"# {title}", "", f"- 실행: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            *[f"- {k}: `{v}`" for k, v in rows.items()], ""]


def save(kind: str, lines: list[str], data: dict) -> None:
    RESULT_DIR.mkdir(exist_ok=True)
    stem = RESULT_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{kind}"
    stem.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    stem.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {RESULT_DIR.name}/{stem.name}.md  (+ .json)")


def fmt(x: float) -> str:
    return f"{x:.3f}"


# ── retrieval ──────────────────────────────────────────────────────
def grade_hits(hits, gold) -> dict:
    """hits = rank() 결과. Top-1 · Top-3 정답 여부와 1위의 연도."""
    docs = [h[0] for h in hits]
    return {"top1": bool(docs) and is_hit(docs[0], gold, SHORT_NAME),
            "top3": any(is_hit(d, gold, SHORT_NAME) for d in docs),
            "year1": docs[0].metadata.get("year") if docs else None,
            "top": [rb.source_of(d) for d in docs]}


def summarize(qs: list[tuple], graded: dict) -> dict:
    """graded[qid] = grade_hits 결과 → 칸 하나의 요약."""
    conflict = [q[0] for q in qs if q[1] == "연도충돌"]
    return {"top1": sum(graded[q[0]]["top1"] for q in qs), "top3": sum(graded[q[0]]["top3"] for q in qs),
            "by_kind": {k: f"{sum(graded[q[0]]['top3'] for q in qs if q[1] == k)}/{sum(q[1] == k for q in qs)}"
                        for k in KINDS if any(q[1] == k for q in qs)},
            "recent_top1": f"{sum(graded[i]['year1'] == 2026 for i in conflict)}/{len(conflict)}",
            "watch": graded[YEAR_WATCH]["top3"] if YEAR_WATCH in graded else None}


def run_retrieval(args) -> None:
    qs = [q for q in pick(args.ids) if q[1] not in NO_RETRIEVAL]
    n = len(qs)
    eval_cfg = {"tags": [TAG, "eval", "retrieval"], "metadata": {"source": "evaluate", "index": INDEX_DIR.name}}
    rb.get_store()                                           # 인덱스 · manifest 확인 (없으면 여기서 멈춘다)

    # ① basic 후보 — 문항마다 한 번만 검색하고, year_bonus 는 그 위에서 다시 매긴다 (검색을 반복하지 않는다)
    print(f"[1/2] basic 검색 — {n}문항")
    cand, sec = {"basic": [{}]}, {"basic": []}
    for qid, _kind, question, *_ in qs:
        t = time.perf_counter()
        cand["basic"][0][qid] = rb.candidates([question])
        sec["basic"].append(time.perf_counter() - t)
    gaps = []
    for qid in cand["basic"][0]:
        dist = sorted(hit[1] for hit in cand["basic"][0][qid].values())
        if len(dist) >= 3:
            gaps.append(dist[2] - dist[0])
    g = statistics.median(gaps)
    bonuses = [("0", 0.0), ("0.5g", 0.5 * g), ("1g", g), ("2g", 2 * g)]

    # ② multiquery 후보 — 다시 쓰기가 실행마다 달라질 수 있어 REPEATS 회
    rewrites: list[dict] = []
    if not args.no_multiquery:
        print(f"[2/2] multiquery 검색 — {n}문항 × {args.repeats}회 (다시 쓰기 LLM 호출)")
        cand["multiquery"], sec["multiquery"] = [], []
        for r in range(args.repeats):
            cand["multiquery"].append({})
            rewrites.append({})
            for qid, _kind, question, *_ in qs:
                t = time.perf_counter()
                extra = rb.rewrite_queries(question, eval_cfg)
                cand["multiquery"][r][qid] = rb.candidates([question, *extra])
                sec["multiquery"].append(time.perf_counter() - t)
                rewrites[r][qid] = extra

    # ③ 격자
    grid = []
    for strategy in cand:
        for label, bonus in bonuses:
            runs = []
            for rep in cand[strategy]:
                graded = {q[0]: grade_hits(rb.rank(rep[q[0]], bonus, TOP_K), q[3]) for q in qs}
                runs.append({"graded": graded, **summarize(qs, graded)})
            grid.append({"strategy": strategy, "bonus_label": label, "year_bonus": bonus, "runs": runs,
                         "avg_sec": sum(sec[strategy]) / len(sec[strategy])})

    def span(cell, key):
        vals = [r[key] for r in cell["runs"]]
        return f"{min(vals)}" if min(vals) == max(vals) else f"{min(vals)}~{max(vals)}"

    lines = header("검색 평가 (retrieval)", {"다시 쓰기 모델": MODEL if "multiquery" in cand else "(안 씀)"})
    lines += [f"- 문항: {n}개 (범위밖 · 입력검증 제외)",
              f"- **g = {fmt(g)}** — basic 에서 «1위와 3위의 L2 거리 차» 의 중앙값. year_bonus 후보의 눈금",
              f"- multiquery 는 {args.repeats}회 반복 — 값이 `a~b` 면 실행마다 달랐다는 뜻", "",
              "## 요약", "",
              f"| 전략 | year_bonus | Top-1 (/{n}) | Top-3 (/{n}) | " + " | ".join(KINDS)
              + f" | 연도충돌 top-1 이 2026 | {YEAR_WATCH} Top-3 | 평균 검색 시간 |",
              "|---|---|---|---|" + "---|" * len(KINDS) + "---|---|---|"]
    for cell in grid:
        first = cell["runs"][0]
        lines.append(f"| {cell['strategy']} | {cell['bonus_label']} ({fmt(cell['year_bonus'])}) | {span(cell, 'top1')} | "
                     f"{span(cell, 'top3')} | " + " | ".join(first["by_kind"].get(k, "-") for k in KINDS)
                     + f" | {first['recent_top1']} | {OX.get(first['watch'], '-')} | {cell['avg_sec']:.2f}초 |")
    lines += ["", "유형별 · 연도충돌 · 감시 문항 열은 1회차 기준.", "",
              "## 문항별 Top-3 (1회차) — 어느 문항이 어느 칸에서 바뀌었나", "",
              "| id | 유형 | 질문 | " + " | ".join(f"{c['strategy'][:5]} {c['bonus_label']}" for c in grid) + " |",
              "|---|---|---|" + "---|" * len(grid)]
    for qid, kind, question, *_ in qs:
        lines.append(f"| {qid} | {kind} | {question} | "
                     + " | ".join(OX[c["runs"][0]["graded"][qid]["top3"]] for c in grid) + " |")
    lines += ["", "## basic · bonus 0 의 1~3위 (틀린 문항을 볼 때)", ""]
    base = grid[0]["runs"][0]["graded"]
    for qid, _kind, question, *_ in qs:
        lines.append(f"- {OX[base[qid]['top3']]} **{qid}** {question} → " + " / ".join(base[qid]["top"]))
    if rewrites:
        lines += ["", "## multiquery 가 다시 쓴 검색 질문 (1회차)", ""]
        lines += [f"- **{qid}** {question} → " + " / ".join(rewrites[0][qid] or ["(없음)"])
                  for qid, _kind, question, *_ in qs]

    print("\n" + "\n".join(lines))
    save("retrieval", lines, {"index": INDEX_DIR.name, "manifest": rb.read_manifest(), "embed_model": EMBED_MODEL,
                              "model": MODEL, "g": g, "grid": grid, "rewrites": rewrites})


# ── answer ─────────────────────────────────────────────────────────
def grade_answer(answer: str, must: list[str], bad: list[str]) -> str:
    """ok | contradict | wrong"""
    if "찾지 못했" not in must and "찾지 못했" in answer:
        return "contradict"                                  # 정답을 말해 놓고 «찾지 못했습니다» 를 붙임
    return "ok" if any(m in answer for m in must) and not any(b in answer for b in bad) else "wrong"


def run_answer(args) -> None:
    qs = pick(args.ids)
    strategy, year_bonus = rb._resolve(args.strategy, args.year_bonus)
    rb.get_store()
    print(f"생성 평가 — {len(qs)}문항 · {MODEL} · {strategy} · year_bonus {year_bonus} · prompt {PROMPT_VARIANT}")
    print("모델 올리는 중…")
    warm = rb.warmup()                                       # 첫 호출(로딩)을 시간 통계에서 뺀다

    rows, mark = [], {"ok": "✅", "contradict": "⚠️ 자기모순", "wrong": "❌"}
    for qid, kind, question, gold, must, bad in qs:
        try:
            ans, docs, sec = rb.ask(question, {"source": "evaluate", "question_id": qid}, strategy, year_bonus,
                                    tags=["eval"])
            ans = ans.strip()
            verdict = grade_answer(ans, must, bad)
        except Exception as e:
            ans, docs, sec, verdict = f"(실패 — {type(e).__name__}: {e})", [], 0.0, "wrong"
        rows.append({"id": qid, "kind": kind, "question": question, "answer": ans, "verdict": verdict, "sec": sec,
                     "retrieved": (any(is_hit(d, gold, SHORT_NAME) for d in docs) if gold else None),
                     "sources": [rb.source_of(d) for d in docs]})
        print(f"{mark[verdict]} [{sec:4.1f}초] {qid} {question}\n   {ans.replace(chr(10), ' ')[:200]}")
    gpu, ps = vram(), ollama_ps()

    ok = sum(r["verdict"] == "ok" for r in rows)
    contradict = sum(r["verdict"] == "contradict" for r in rows)
    secs = [r["sec"] for r in rows if r["sec"]]
    kinds = list(dict.fromkeys(r["kind"] for r in rows))
    lines = header("생성 평가 (answer)", {"생성 모델": MODEL, "검색 전략": strategy, "year_bonus": year_bonus,
                                       "프롬프트": PROMPT_VARIANT})
    lines += ["## 요약", "", "| 항목 | 값 |", "|---|---|",
              f"| 정답 | **{ok} / {len(rows)}** |",
              f"| 자기모순 (정답 뒤에 «찾지 못했습니다») | {contradict}회 |",
              *[f"| {k} | {sum(r['verdict'] == 'ok' for r in rows if r['kind'] == k)} / "
                f"{sum(r['kind'] == k for r in rows)} |" for k in kinds],
              f"| 답 1개 시간 (로딩 후) | 평균 {sum(secs) / len(secs):.1f}초 · 최대 {max(secs):.1f}초 |" if secs
              else "| 답 1개 시간 | - |",
              f"| 워밍업 (모델 로딩) | {warm:.1f}초 |",
              f"| 생성 중 GPU 메모리 (nvidia-smi) | {gpu} |", "",
              "## 문항별", "", "| id | 유형 | 판정 | 검색 | 초 | 질문 | 답 (앞 200자) |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        got = "-" if r["retrieved"] is None else OX[r["retrieved"]]
        text = r["answer"].replace("\n", " ").replace("|", "\\|")[:200]
        lines.append(f"| {r['id']} | {r['kind']} | {mark[r['verdict']]} | {got} | {r['sec']:.1f} | {r['question']} | {text} |")
    lines += ["", "«검색» 열 = 근거 3개 안에 정답 청크가 있었나. × 인데 판정이 ❌ 면 모델 탓이 아니라 검색 탓이다.",
              "", "## ollama ps", "", "```", ps, "```"]

    print("\n" + "\n".join(lines[:lines.index("## 문항별")]))
    save("answer", lines, {"index": INDEX_DIR.name, "manifest": rb.read_manifest(), "model": MODEL,
                           "embed_model": EMBED_MODEL, "strategy": strategy, "year_bonus": year_bonus,
                           "prompt": PROMPT_VARIANT, "ok": ok, "total": len(rows), "contradict": contradict,
                           "gpu": gpu, "warmup_sec": warm, "rows": rows})


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="분리배출 RAG 평가")
    ap.add_argument("what", choices=("retrieval", "answer"))
    ap.add_argument("--index", help="인덱스 폴더 이름 (기본 index_recycle)")
    ap.add_argument("--model", help="생성 모델 (기본 config.MODEL)")
    ap.add_argument("--prompt", choices=tuple(rb.RAG_PROMPTS), help="RAG 프롬프트 (기본 base)")
    ap.add_argument("--strategy", choices=STRATEGIES, default=None, help="answer 전용")
    ap.add_argument("--year-bonus", type=float, default=None, help="answer 전용")
    ap.add_argument("--ids", help="문항 id 를 쉼표로 (예: c1,y2) · scratch = scratch_eval.py 의 6문항")
    ap.add_argument("--repeats", type=int, default=REPEATS, help="retrieval 의 multiquery 반복 횟수")
    ap.add_argument("--no-multiquery", action="store_true", help="retrieval 에서 LLM 없이 basic 만")
    args = ap.parse_args()
    try:
        (run_retrieval if args.what == "retrieval" else run_answer)(args)
    finally:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        wait_for_all_tracers()


if __name__ == "__main__":
    main()
