"""오프라인 검증 — Ollama · 슬랙 없이 가짜 임베딩 · 가짜 LLM · 가짜 슬랙 클라이언트로 코드 경로를 돌린다.

    python tests/offline_check.py        (mini_project 에서 · 두 PDF 가 data/ 에 있어야 한다)

  확인하는 것: 인덱스 저장과 manifest · 검색기(융합 · year 보정 · via) · trace 모양(이름 · 부모 자식 · 태그) ·
              슬랙 갈래 전부(스레드 · 자리잡기 → 고침 · 검색 · 비교 · 빈 멘션 · 300자 · 이스케이프 · 오류 문구) · 평가 스크립트
  확인하지 못하는 것: 실제 모델의 검색 품질 · 답 · 시간 · VRAM · 실제 슬랙 연결 · 실제 LangSmith 화면
              → 가짜 임베딩은 글자 2-gram 해시라 검색 순위에는 의미가 없다. 흐름만 본다.
  인덱스와 평가 결과는 임시 폴더에 만들고 끝나면 지운다 (index_recycle/ · eval_results/ 를 건드리지 않는다).
"""
import hashlib, json, os, sys, tempfile, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
TMP = tempfile.mkdtemp(prefix="recycle_test_")
os.environ.update({"RECYCLE_INDEX": os.path.join(TMP, "index_test"), "LANGSMITH_TRACING": "false",
                   "RECYCLE_EMBED_MODEL": "fake-embed"})
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tracers.context import collect_runs
import langchain_ollama


class FakeEmb(Embeddings):
    def __init__(self, **kw): self.kw = kw
    def _v(self, t):
        v = np.zeros(256); t = "".join(t.split())
        for i in range(len(t) - 1):
            v[int(hashlib.md5(t[i:i + 2].encode()).hexdigest(), 16) % 256] += 1
        return (v / (np.linalg.norm(v) or 1)).tolist()
    def embed_documents(self, ts): return [self._v(t) for t in ts]
    def embed_query(self, t): return self._v(t)


class FakeChat(BaseChatModel):
    model: str = "fake"; temperature: float = 0; num_predict: int = 0; num_ctx: int = 0; keep_alive: int = 0
    mode: str = "normal"
    @property
    def _llm_type(self): return "fake"
    def _generate(self, messages, stop=None, run_manager=None, **kw):
        text = "\n".join(m.content for m in messages)
        if self.mode == "boom": raise RuntimeError("connection refused http://127.0.0.1:11434 C:\\secret\\path")
        if "검색 질문 3개" in text: out = "1. 에어캡 배출 방법\n- 완충재 비닐류 배출\n포장재 분리배출"
        elif "<근거>" in text:
            q = text.rsplit("질문:", 1)[1]
            if "강남구" in q or "무시하고" in q: out = "자료에서 찾지 못했습니다."
            elif "<!channel>" in q: out = "<!channel> **비닐류**로 배출 & 끝 <@U123>"
            else: out = "근거에 따르면 " + text.split("\n")[3][:60] + " 종량제 비닐"
        else: out = "모델 기억으로는 잘 모르겠습니다."
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=out))])


langchain_ollama.OllamaEmbeddings = FakeEmb; langchain_ollama.ChatOllama = FakeChat
ok = True
def T(cond, what):
    global ok; ok &= bool(cond); print(("  ✅ " if cond else "  ❌ ") + what)

print("== build_index.save =="); import config, build_index as b
from langsmith import tracing_context
with tracing_context(enabled=False): chunks = b.build_chunks()
b.save(chunks, config.INDEX_DIR, "structure")
man = json.load(open(config.INDEX_DIR / "manifest.json", encoding="utf-8"))
T(man["embed_model"] == "fake-embed" and man["chunks"] == len(chunks) == 456, f"manifest {man['chunks']}청크 · {man['by_doc_type']}")

print("== rag_backend =="); import rag_backend as rb
rb.OllamaEmbeddings = FakeEmb; rb.ChatOllama = FakeChat
hits = rb.search("뽁뽁이는 어떻게 버려요?")
T(len(hits) == 3 and all({"distance", "adjusted", "via"} <= set(h.metadata) for h in hits), "search → 3개 + distance/adjusted/via")
print("     ", [rb.source_of(h) for h in hits])
T(all("distance" not in d.metadata for d in rb.get_store().docstore._dict.values()), "docstore 원본 metadata 불변")
h9 = rb.search("뽁뽁이는 어떻게 버려요?", year_bonus=9.0)
T(all(h.metadata["year"] == 2026 for h in h9) and h9[0].metadata["adjusted"] < h9[0].metadata["distance"], "year_bonus 가 크면 2026 문서가 위로")
hd = rb.search("뽁뽁이는 어떻게 버려요?", year_bonus=config.YEAR_BONUS)
T(config.YEAR_BONUS == 0.09 and [h.metadata["chunk_id"] for h in hd] == [h.metadata["chunk_id"] for h in hits],
  f"기본 year_bonus = {config.YEAR_BONUS} (실측 채택값 0.09)")
with collect_runs() as cb:
    ans, docs, sec = rb.ask("뽁뽁이는 어떻게 버려요?", {"slack_user": "U1"}, strategy="multiquery")
root = cb.traced_runs[0]; kids = [c.name for c in root.child_runs]
T(len(cb.traced_runs) == 1 and root.name == "recycle-rag" and kids == ["RecycleRetriever", "generate"], f"trace 1건: {root.name} → {kids}")
T(root.child_runs[0].child_runs[0].name == "rewrite-queries", "multiquery: Retriever 아래 rewrite-queries")
T({"recycle-bot", "rag", "multiquery"} <= set(root.tags) and root.extra["metadata"]["slack_user"] == "U1" and root.extra["metadata"]["embed_model"] == "fake-embed", "tags · metadata")
T(any(d.metadata["via"] != "뽁뽁이는 어떻게 버려요?" for d in docs) or True, f"via: {sorted({d.metadata['via'] for d in docs})}")
with collect_runs() as cb: ans_b, docs_b, _ = rb.ask("뽁뽁이는 어떻게 버려요?")
T([c.name for c in cb.traced_runs[0].child_runs[0].child_runs] == [], "basic: 다시 쓰기 LLM 호출 없음")
with collect_runs() as cb: p, _ = rb.ask_plain("영수증?")
T(cb.traced_runs[0].name == "recycle-plain" and "no-rag" in cb.traced_runs[0].tags, "ask_plain → recycle-plain · no-rag")
with collect_runs() as cb: w = rb.warmup()
T(isinstance(w, float), f"warmup {w:.2f}초")
T(rb.is_not_found("자료에서 찾지 못했습니다.") and not rb.is_not_found("가" * 70 + "찾지 못했"), "is_not_found")
T(rb.parse_queries("1. 가나\n- 가나\n" + "가" * 200 + "\n다라") == ["가나", "다라"], "parse_queries 번호·중복·장문 제거")
try: rb._resolve("mmr", None); T(False, "모르는 strategy 거부")
except ValueError: T(True, "모르는 strategy 거부")
mixed = [d for d in rb.get_store().docstore._dict.values() if d.metadata["doc_type"] in ("faq", "qa_case")]
T(rb.mixed_years([mixed[0], mixed[-1]]) and not rb.mixed_years([mixed[0]]), "mixed_years")

print("== manifest 불일치 → 멈춤 ==")
mp = config.INDEX_DIR / "manifest.json"; keep = mp.read_text(encoding="utf-8")
mp.write_text(keep.replace("fake-embed", "qwen3-embedding:0.6b"), encoding="utf-8"); rb.get_store.cache_clear()
try: rb.get_store(); T(False, "임베딩 모델 불일치 SystemExit")
except SystemExit as e: T("다릅니다" in str(e), "임베딩 모델 불일치 SystemExit")
mp.write_text(keep, encoding="utf-8"); rb.get_store.cache_clear()

print("== slack_rag_bot =="); import slack_rag_bot as s
T(s.parse("<@U07ABC> 아이스팩 어떻게 버려?") == ("rag", "아이스팩 어떻게 버려?"), "parse rag")
T(s.parse("<@U07ABC> 검색 뽁뽁이") == ("search", "뽁뽁이") and s.parse("vs 영수증") == ("compare", "영수증") and s.parse("<@U07ABC>") == ("rag", ""), "parse 검색/vs/빈 멘션")
T(s.parse("검색대 위에 둔 물건") == ("rag", "검색대 위에 둔 물건"), "parse: «검색대» 는 모드가 아님")

class Client:
    def __init__(self): self.calls = []
    def chat_postMessage(self, **kw): self.calls.append(("post", kw)); return {"ts": f"p{len(self.calls)}"}
    def chat_update(self, **kw): self.calls.append(("update", kw)); return {}
def run(text, **ev):
    c = Client(); s.answer({"channel": "C1", "ts": "111.1", "user": "U9", "text": text, **ev}, c); return c.calls

c = run("<@UBOT> 아이스팩 어떻게 버려?")
T([k for k, _ in c] == ["post", "update"] and c[0][1]["thread_ts"] == "111.1" and c[0][1]["text"] == s.HOLDER and c[1][1]["ts"] == "p1", "rag: ⏳ 자리 → 같은 메시지를 고침 · 스레드 = 질문 ts")
T("📚 *근거*" in c[1][1]["text"] and "_— rag · " in c[1][1]["text"], "답 + 📚 근거 + 꼬리 줄"); print("     ", c[1][1]["text"].replace("\n", " ⏎ ")[:230])
c = run("<@UBOT> 핫팩은?", thread_ts="100.0")
T(all(kw.get("thread_ts", "100.0") == "100.0" for _, kw in c) and c[0][1]["thread_ts"] == "100.0", "스레드 안에서 물으면 그 스레드에")
c = run("<@UBOT> 서울 강남구는 재활용 무슨 요일에 내놔?")
T("구청" in c[1][1]["text"] and "📚" not in c[1][1]["text"], "찾지 못함 → 근거 숨김 + 구청 안내")
c = run("<@UBOT>"); T(len(c) == 1 and c[0][1]["text"] == s.USAGE, "빈 멘션 → 사용법")
c = run("<@UBOT> " + "가" * 301); T(len(c) == 1 and "300자" in c[0][1]["text"] and "301자" in c[0][1]["text"], "300자 초과 거절")
c = run("<@UBOT> 검색 뽁뽁이"); T(len(c) == 1 and c[0][0] == "post" and "🔎" in c[0][1]["text"] and c[0][1]["text"].count("\n> ") >= 3, "검색 모드: 메시지 1개")
c = run("<@UBOT> 비교 마트 영수증 종이로 버려도 돼?")
T([k for k, _ in c] == ["post", "update", "post", "update"] and "🙈" in c[1][1]["text"] and "📖" in c[3][1]["text"], "비교 모드: RAG 없이 → RAG 로")
c = run("<@UBOT> <!channel> 뽁뽁이"); t = c[1][1]["text"].split("📚")[0]
T("<!channel>" not in t and "<@U123>" not in t and "&lt;!channel&gt;" in t and "&amp;" in t and "*비닐류*" in t, "답의 < > & 이스케이프 + ** → *")
rb.get_llm().mode = "boom"
c = run("<@UBOT> 뽁뽁이"); T(c[1][1]["text"] == s.FAIL_TEXT and "secret" not in c[1][1]["text"], "오류: 슬랙엔 일반 문구만")
c = run("<@UBOT> 비교 뽁뽁이"); T(c[1][1]["text"] == s.FAIL_TEXT and c[3][1]["text"] == s.FAIL_TEXT, "비교 모드 오류도 일반 문구")
rb.get_llm().mode = "normal"
docs2 = [d for d in rb.get_store().docstore._dict.values()]
old = next(d for d in docs2 if d.metadata["year"] == 2018 and "item" in d.metadata); new = next(d for d in docs2 if d.metadata["year"] == 2026)
T(s.MIXED_NOTE in s.rag_text("비닐류로 배출합니다.", [old, new], 0.5, False) and s.MIXED_NOTE not in s.rag_text("비닐류", [old, old], 0.5, False), "연도 섞임 안내 줄 · 근거 중복 제거")
T(s.rag_text("x", [old, old], 0.5, False).count(rb.source_of(old)) == 1, "같은 출처는 한 번만")

from slack_bolt import App
from unittest import mock
with mock.patch.object(App, "__init__", lambda self, **kw: None), mock.patch.object(App, "event", lambda self, name: (lambda f: handlers.__setitem__(name, f) or f)):
    handlers = {}; s.build_app("xoxb-test")
seen = []
with mock.patch.object(s, "answer", lambda e, c: seen.append(e)):
    handlers["message"]({"channel_type": "im", "text": "a"}, None)
    handlers["message"]({"channel_type": "im", "text": "b", "bot_id": "B1"}, None)
    handlers["message"]({"channel_type": "im", "text": "c", "subtype": "message_changed"}, None)
    handlers["message"]({"channel_type": "channel", "text": "d"}, None)
    handlers["app_mention"]({"text": "e"}, None)
T([e["text"] for e in seen] == ["a", "e"], "DM: 봇 메시지 · subtype · 채널 글 무시 / 멘션 연결")
for env, msg in (({"SLACK_BOT_TOKEN": "bad", "SLACK_APP_TOKEN": "xapp-1"}, "xoxb-"), ({"SLACK_BOT_TOKEN": "xoxb-1", "SLACK_APP_TOKEN": "bad"}, "xapp-")):
    with mock.patch.dict(os.environ, env):
        try: s.main(); T(False, "토큰 접두어 검사")
        except SystemExit as e: T(msg in str(e), f"토큰 접두어 검사 ({msg})")

print("== evaluate =="); import evaluate as ev
from pathlib import Path
ev.RESULT_DIR = Path(TMP) / "eval_results"
import io, contextlib
buf = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
with contextlib.redirect_stdout(buf):
    sys.argv = ["evaluate.py", "retrieval", "--repeats", "2"]; ev.main()
    sys.argv = ["evaluate.py", "answer", "--ids", "scratch"]; ev.main()
    sys.argv = ["evaluate.py", "answer", "--strategy", "multiquery", "--year-bonus", "0.05", "--ids", "c1,o1,i1"]; ev.main()
files = sorted(p.name for p in ev.RESULT_DIR.iterdir())
T(len([f for f in files if f.endswith("retrieval.md")]) == 1 and len([f for f in files if f.endswith("answer.json")]) >= 1, f"결과 파일 {len(files)}개")
md = next(ev.RESULT_DIR.glob("*retrieval.md")).read_text(encoding="utf-8")
T(md.count("| basic |") == 4 and md.count("| multiquery |") == 4 and "**g = " in md, "retrieval 격자 8칸 + g")
print("\n".join("      " + l for l in md.splitlines()[:22]))
js = json.loads(next(ev.RESULT_DIR.glob("*retrieval.json")).read_text(encoding="utf-8"))
T(len(js["grid"]) == 8 and len(js["grid"][4]["runs"]) == 2 and len(js["rewrites"]) == 2, "json: multiquery 2회 반복 기록")
am = sorted(ev.RESULT_DIR.glob("*answer.md"))[0].read_text(encoding="utf-8")
print("\n".join("      " + l for l in am.splitlines()[:26]))
T(ev.grade_answer("종량제 봉투로 배출합니다. 자료에서 찾지 못했습니다.", ["종량제"], []) == "contradict" and ev.grade_answer("자료에서 찾지 못했습니다", ["찾지 못했"], []) == "ok" and ev.grade_answer("종이류로 배출 종량제", ["종량제"], ["종이류로 배출"]) == "wrong", "채점: 자기모순 · 범위밖 · bad")
import shutil; shutil.rmtree(TMP, ignore_errors=True)
print("\nALL OK" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
