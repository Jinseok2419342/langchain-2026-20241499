"""공용 설정 — 다른 파일은 langchain · langsmith 를 import 하기 **전에** 이 파일부터 import 한다.

  ★ 이유: LangSmith 는 환경 변수를 처음 읽을 때 기억해 둔다.
     여기서 프로젝트 이름을 정한 뒤에 라이브러리가 올라와야 trace 가 «recycle-bot-20241499» 로 간다.

  모델 · 전략은 전용 키 RECYCLE_* 로만 바꾼다 (루트 .env 의 MODEL · EMBED_MODEL 은 다른 주차 실습용이라 읽지 않는다).
  RECYCLE_* 는 «실행 한 번 = 설정 하나» — 인덱스와 모델을 한 번만 읽어 계속 쓰기 때문에 실행 중에는 바뀌지 않는다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()                                   # 루트 .env (위쪽 폴더로 올라가며 찾음)
# ★ LangSmith 프로젝트는 여기서 정한다 — 루트 .env 를 건드리지 않아 다른 주차 trace 와 안 섞임
os.environ["LANGSMITH_PROJECT"] = os.getenv("RECYCLE_LANGSMITH_PROJECT", "recycle-bot-20241499")

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
INDEX_DIR = HERE / os.getenv("RECYCLE_INDEX", "index_recycle")   # 평가에서 비교용 인덱스로 바꿀 때만

MODEL = os.getenv("RECYCLE_MODEL", "hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M")
EMBED_MODEL = os.getenv("RECYCLE_EMBED_MODEL", "hf.co/mykor/KURE-v1-gguf:Q8_0")

DOCS = [   # (파일, year, 출처에 쓸 짧은 이름)
    ("분리배출_가이드라인.pdf", 2018, "가이드라인"),
    ("분리배출_QA사례100_2026.pdf", 2026, "사례집"),
]
SHORT_NAME = {name: short for name, _, short in DOCS}

CHUNK_SIZE, CHUNK_OVERLAP = 400, 40
KO_SEPARATORS = ["\n\n", "\n", "다. ", ". ", " ", ""]
UNIT_MAX = 600          # 구조 단위(Q&A · FAQ · 품목)는 이 길이를 넘을 때만 재귀로 다시 자른다
MIN_BODY_CHARS = 30     # 가이드라인 **본문** 청크에만 적용 (품목사전은 평균 20자 — 걸면 대부분 사라진다)

TOP_K = 3               # 근거로 넘길 청크 수
FETCH_K = 10            # 재정렬 전에 넓게 가져올 후보 수
YEAR_RECENT = 2020      # 이 해 이후 문서를 «최신» 으로 본다
# ★ 아래 기본값은 evaluate.py 실측(2026-11-17)으로 채택한 값
#   YEAR_BONUS 0.09 = 0.5g (g = 0.180) — eval_results/20261117-153601-retrieval.md:
#     Top-3 23 → 23 (줄지 않음) · c1 ○ · 연도충돌 top-1 이 2026 2/4 → 4/4. 생성은 28/30 = 28/30 (…153652 ↔ …153846)
#   STRATEGY basic — multiquery 는 Top-3 20~21 로 오히려 낮고 5배 느림 (같은 파일)
#   PROMPT base — recent 는 27~28/30 + 자기모순 1 (…153750 · …153940)
YEAR_BONUS = float(os.getenv("RECYCLE_YEAR_BONUS", "0.09"))
STRATEGY = os.getenv("RECYCLE_STRATEGY", "basic")          # basic | multiquery
PROMPT_VARIANT = os.getenv("RECYCLE_PROMPT", "base")       # base | recent — E4 실험용 («더 최근 근거를 따른다» 한 줄)

TEMPERATURE, MAX_OUT, NUM_CTX = 0.1, 300, 4096
KEEP_ALIVE = 1800       # 초(30분) — Ollama 가 모델을 5분 만에 내리지 않게 (첫 답 20초 문제)
#                         ⚠️ 정수로 둘 것: OllamaEmbeddings 의 keep_alive 는 int 만 받는다 ("30m" 은 ValidationError)
NOT_FOUND = "자료에서 찾지 못했습니다"
MAX_QUESTION = 300
TAG = "recycle-bot"

STRATEGIES = ("basic", "multiquery")
if STRATEGY not in STRATEGIES:
    raise SystemExit(f"RECYCLE_STRATEGY 는 {' | '.join(STRATEGIES)} 중 하나여야 합니다 (지금: {STRATEGY!r})")


def short_model(name: str = MODEL) -> str:
    """«hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M» → «A.X-4.0-Light» (슬랙 꼬리 줄 · 로그용)."""
    return name.rsplit("/", 1)[-1].split(":", 1)[0].removesuffix("-gguf")
