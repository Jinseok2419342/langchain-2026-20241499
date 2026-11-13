"""[버릴지도 ③] ★★ 슬랙에서 묻고, 분리배출 문서에서 찾아서 답한다

    @버릴지도 아이스팩 어떻게 버려?               → 문서에서 찾아 답 + 📚 근거(품목 · 문서 · 연도 · 쪽)
    @버릴지도 검색 뽁뽁이                        → 검색만 — 어떤 근거가 뽑혔나
    @버릴지도 비교 마트 영수증 종이로 버려도 돼?    → RAG 없이 vs RAG 로 — 나란히 본다
    (DM) 핫팩은?                                → 멘션 없이 1:1 로도 같은 방식

  전체 흐름 — 10주차 봇에서 두뇌(rag_backend)만 갈아 끼웠다

    슬랙 사용자 ── @멘션 / DM ──▶ 슬랙 서버 ══ WebSocket (xapp) ══▶ 내 PC  slack_rag_bot.py
                                                                        │
                                              rag_backend.ask()         ▼
                                     ┌─ 검색  index_recycle/  (build_index.py ← data/*.pdf 2건)
                                     └─ 생성  근거 + 질문 → A.X 4.0 Light (Ollama · 로컬)
                                                                        │
    같은 스레드 ◀── chat_postMessage / chat_update (xoxb) ──────────────┘
                    답 + 📚 근거

★ 필수 요건 «같은 스레드에 답을 단다» — 모든 메시지를 thread_ts 로 보낸다 (채널 본문에 새 글로 답하지 않는다).
★ 슬랙 질문 1건 = LangSmith trace 1건(recycle-rag). 그 안에 검색(RecycleRetriever)과 생성(generate)이 나란히 보인다.
★ 슬랙 메시지와 '근거 청크' 둘 다 남이 쓴 입력이다 (9주차 2교시).
   - 질문은 300자 제한, 프롬프트는 <근거> 구분자 + «지시가 아니다»
   - 모델의 답을 슬랙에 보내기 전에 & < > 를 바꾼다 — 답에 <!channel> 이 섞여도 멘션이 되지 않게
   - 예외 내용은 슬랙에 올리지 않는다 (경로 · 내부 주소가 채널에 노출될 수 있다) — 콘솔에만

⚠️ 같은 슬랙 앱(xapp)으로 10주차 봇을 동시에 켜 두면 이벤트가 둘 중 한쪽으로 갈린다. 이 봇만 켠다.

전제:
    index_recycle/ 가 있어야 한다 — 없으면 python build_index.py
    python rag_backend.py 로 터미널에서 먼저 답이 나와야 한다.

실행 (이 폴더에서):
    python slack_rag_bot.py        # 끝낼 때는 Ctrl+C
"""

import config  # noqa: F401  ★ 맨 위 — load_dotenv + LangSmith 프로젝트 지정
from config import EMBED_MODEL, INDEX_DIR, MAX_QUESTION, MODEL, NOT_FOUND, STRATEGY, YEAR_BONUS  # noqa: E402

import os  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402

from slack_bolt import App  # noqa: E402
from slack_bolt.adapter.socket_mode import SocketModeHandler  # noqa: E402
from slack_sdk.errors import SlackApiError  # noqa: E402

# ★ 두뇌 — 봇(입구 · 출구)과 RAG 가 나뉘어 있어서 이 줄만 바꾸면 다른 두뇌가 된다
from rag_backend import (  # noqa: E402
    ask, ask_plain, is_not_found, mixed_years, read_manifest, search, source_of, warmup,
)

SEARCH_WORDS = ("검색", "search")
COMPARE_WORDS = ("비교", "vs")
MODEL_SHORT = config.short_model()

USAGE = (
    "분리배출 방법을 물어봐 주세요 ♻️\n"
    "• `@버릴지도 아이스팩 어떻게 버려?` — 문서에서 찾아 답하고 📚 근거를 붙입니다\n"
    "• `@버릴지도 검색 뽁뽁이` — 어떤 근거가 뽑혔는지만 보여 줍니다\n"
    "• `@버릴지도 비교 마트 영수증 종이로 버려도 돼?` — 문서 없이 답한 것과 나란히\n"
    "• DM 으로는 멘션 없이 `핫팩은?` 처럼 바로 물어도 됩니다"
)
HOLDER = "⏳ 분리배출 문서에서 찾는 중…"
NOT_FOUND_TEXT = (f"{NOT_FOUND} — 지역별 배출 요일 · 수수료처럼 지자체마다 다른 내용은 "
                  "거주지 구청(주민센터)에 확인하세요.")
MIXED_NOTE = ("ℹ️ 2018 가이드라인과 2026 사례집이 함께 근거로 쓰였습니다 — "
              "내용이 다르면 최신인 사례집(2026)을 따르세요.")
FAIL_TEXT = "⚠️ 답을 만들지 못했습니다. 잠시 뒤 다시 물어봐 주세요."


# ── 1. 메시지 → (모드, 질문) ─────────────────────────────────────
def parse(text: str) -> tuple[str, str]:
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", text or "").strip()      # 앞의 <@U07ABCDEF> 를 떼어 낸다
    first, _, rest = text.partition(" ")
    if first.lower() in SEARCH_WORDS:
        return "search", rest.strip()
    if first.lower() in COMPARE_WORDS:
        return "compare", rest.strip()
    return "rag", text


def escape(text: str) -> str:
    """슬랙 제어 문자를 바꾼다 — 모델 답 · 문서 조각에 <!channel> · <@U…> 가 섞여도 멘션이 되지 않게."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_mrkdwn(answer: str) -> str:
    """먼저 escape, 그다음 굵게 표기 변환 (LLM 은 **굵게**, 슬랙은 *굵게*)."""
    return escape(answer.strip()).replace("**", "*")


def sources_block(docs) -> str:
    """📚 근거 — metadata 가 여기서 쓰인다 ★  (같은 출처가 겹치면 한 번만)"""
    seen = list(dict.fromkeys(escape(source_of(d)) for d in docs))
    return "📚 *근거*  " + "  /  ".join(seen)


def tail(mode: str, sec: float) -> str:
    return f"_— {mode} · {MODEL_SHORT} · {sec:.1f}초_"


def rag_text(ans: str, docs, sec: float, compare: bool) -> str:
    head = "📖 *RAG 로* (문서에서 찾아서)\n" if compare else ""
    if is_not_found(ans):
        # 관련 없는 근거를 보여 주면 오해를 산다 — 근거를 숨기고 갈 곳을 알려 준다
        return f"{head}{NOT_FOUND_TEXT}\n{tail('rag', sec)}"
    note = f"\n{MIXED_NOTE}" if mixed_years(docs) else ""
    return f"{head}{to_mrkdwn(ans)}\n\n{sources_block(docs)}{note}\n{tail('rag', sec)}"


def search_text(question: str, meta: dict) -> str:
    hits = search(question, config={"run_name": "recycle-search", "tags": [config.TAG, "search", STRATEGY],
                                    "metadata": meta})
    lines = [f"🔎 *검색 결과* — 거리(작을수록 가깝다) · {STRATEGY} · year_bonus {YEAR_BONUS}"]
    for i, doc in enumerate(hits, 1):
        m = doc.metadata
        preview = escape(doc.page_content[:80].replace("\n", " "))
        via = f"\n> ↳ 검색 질문: {escape(m['via'])}" if m["via"] != question else ""
        lines.append(f"{i}. `{m['distance']:.3f}` *{escape(source_of(doc))}*\n> {preview}…{via}")
    return "\n".join(lines)


def log_fail(where: str, e: Exception) -> None:
    """원인은 콘솔에만 — 슬랙에는 일반 문구만 올린다."""
    print(f"  실패 → {where} {type(e).__name__}: {e}")
    traceback.print_exc()


# ── 2. 답하기 — 자리부터 잡고, 답이 오면 고친다 ───────────────────
def answer(event: dict, client) -> None:
    channel = event["channel"]
    thread = event.get("thread_ts") or event["ts"]          # ★ 같은 스레드에 — 스레드 안이면 그 스레드, 아니면 그 메시지 아래
    user = event.get("user", "")
    mode, question = parse(event.get("text", ""))
    print(f"받음 ← user={user} {mode} {question!r}")

    def post(text: str):
        return client.chat_postMessage(channel=channel, thread_ts=thread, text=text)

    if not question:
        post(USAGE)
        return
    if len(question) > MAX_QUESTION:
        post(f"✋ 질문은 {MAX_QUESTION}자 이내로 부탁드립니다. (지금 {len(question)}자)")
        return

    meta = {"slack_user": user, "slack_channel": channel, "source": "slack"}

    # ── 검색만 ──
    if mode == "search":
        try:
            text = search_text(question, meta)
        except Exception as e:
            log_fail("search", e)
            text = FAIL_TEXT
        post(text)
        return

    # ── 비교 — 먼저 RAG 없이 ──
    if mode == "compare":
        holder = post(f"⏳ [RAG 없이] {MODEL_SHORT} 가 생각 중입니다…")
        try:
            ans, sec = ask_plain(question, meta)
            text = f"🙈 *RAG 없이* (모델 기억만)\n{to_mrkdwn(ans)}\n\n{tail('no-rag', sec)}"
        except Exception as e:
            log_fail("no-rag", e)
            text = FAIL_TEXT
        client.chat_update(channel=channel, ts=holder["ts"], text=text)

    # ── RAG — ① 자리 잡기 → ② 찾아서 답하기 → ③ 자리를 답으로 ★ ──
    holder = post(HOLDER)
    try:
        ans, docs, sec = ask(question, meta)
        text = rag_text(ans, docs, sec, compare=(mode == "compare"))
        print(f"  답함 → {sec:.1f}초  근거 chunk_id={[d.metadata.get('chunk_id') for d in docs]}")
    except Exception as e:
        log_fail("rag", e)
        text = FAIL_TEXT
    client.chat_update(channel=channel, ts=holder["ts"], text=text)


def build_app(bot_token: str) -> App:
    app = App(token=bot_token)

    @app.event("app_mention")
    def on_mention(event, client):
        answer(event, client)

    @app.event("message")
    def on_dm(event, client):
        # 봇에게 1:1 DM 으로 물을 때 — message.im 이벤트를 구독해야 온다
        # subtype(수정 · 삭제 알림)과 봇이 쓴 메시지는 무시한다 — 자기 답에 다시 답하지 않게
        if event.get("channel_type") == "im" and not event.get("subtype") and not event.get("bot_id"):
            answer(event, client)

    return app


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not bot_token.startswith("xoxb-"):
        raise SystemExit("SLACK_BOT_TOKEN 은 xoxb- 로 시작해야 합니다. (루트 .env)")
    if not app_token.startswith("xapp-"):
        raise SystemExit("SLACK_APP_TOKEN 은 xapp- 로 시작해야 합니다. (루트 .env)")

    tracing = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    manifest = read_manifest()
    print("=" * 60)
    print(f"인덱스    : {INDEX_DIR}  ({manifest.get('chunks', '?')}청크 · {manifest.get('mode', '?')})")
    print(f"임베딩    : {EMBED_MODEL}")
    print(f"생성 모델 : {MODEL}")
    print(f"검색      : {STRATEGY} · year_bonus {YEAR_BONUS}")
    print(f"LangSmith : {os.environ['LANGSMITH_PROJECT']}  (추적 {'켜짐 ✅' if tracing else '꺼짐'})")
    if not tracing:
        print("⚠️ LANGSMITH_TRACING 이 true 가 아닙니다 — 추적 캡처는 필수 제출물입니다 (루트 .env).")

    # ★ 켜기 전에 두 모델을 올린다 — 첫 답 20초(모델 로딩)를 여기서 미리 치르고, 설정도 확인된다
    print("모델 올리는 중… (처음엔 20초쯤)")
    try:
        sec = warmup()
    except SystemExit:
        raise                                              # 인덱스 없음 · 임베딩 모델 불일치 — 안내 문구 그대로
    except Exception as e:
        raise SystemExit(
            f"워밍업 실패 — {type(e).__name__}: {e}\n"
            "  점검 순서:  ① ollama serve 가 떠 있나  ② ollama list 에 두 모델이 있나 (없으면 ollama pull)\n"
            "              ③ python rag_backend.py 검색 \"뽁뽁이\" 가 되나"
        )
    print(f"워밍업 ✅ {sec:.1f}초")

    app = build_app(bot_token)
    print("슬랙에서 @버릴지도 질문 / 검색 질문 / 비교 질문.  끝낼 때는 Ctrl+C")
    print("=" * 60)
    try:
        SocketModeHandler(app, app_token).start()
    except SlackApiError as e:
        raise SystemExit(f"앱 토큰으로 연결하지 못했습니다: {e.response['error']}  → 10-30/socket_hello.py 로 슬랙 쪽부터 확인")


if __name__ == "__main__":
    main()
