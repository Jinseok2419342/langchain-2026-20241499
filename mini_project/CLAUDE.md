# CLAUDE.md — 버릴지도 (분리배출 안내 RAG 슬랙 봇)

이 파일은 다음 세션의 Claude Code 가 이 프로젝트를 처음 보고도 이어서 작업할 수 있게 쓴 인수인계 문서입니다.
**읽는 순서: 이 파일 → [SPEC.md](SPEC.md) (구현 지시서) → [README.md](README.md) · [CONTEXT.md](CONTEXT.md) (채점 대상 명세).**
그림으로 먼저 보려면 [docs/architecture.md](docs/architecture.md) (구성도 · 흐름도) · [docs/scenarios.md](docs/scenarios.md) (가상 시나리오).

## 한 줄 요약

슬랙에서 «뽁뽁이 어떻게 버려?» 라고 물으면, 분리배출 PDF 2건에서 근거를 찾아(RAG) 배출 방법 + 출처(품목 · 문서 · 연도 · 쪽)를 스레드에 답하는 봇.
동양미래대 «최신인공지능» 수업(학번 20241499) 미니 프로젝트. **응답은 한국어로.**

## 현재 상태 (2026-11-17 기준)

> ★ **2026-11-17 에 실제 모델로 처음 돌렸습니다** — 메인 PC 와 사양이 같은 보조 PC(RTX 3070 8GB · Ollama 0.32.14 · Python 3.13.3 · 영문 경로 클론).
> 인덱스 생성 → 터미널 → 슬랙(멘션 · DM) → LangSmith → 평가 E1~E4 까지 통과. 아래 «2026-11-17 첫 실행 결과» 참고.
> 기본값 채택(`basic` · `year_bonus 0.09` · `base`)과 문서 갱신(README 5 · 6 · CONTEXT 부록 D ~ F · scenarios)까지 끝났습니다.
> ★ **2026-11-19 캡처 5장을 README 에 넣음** (LangSmith 3장 · 슬랙 2장 · `docs/*.png` · SPEC 13-1 l) → 수업 PDF 필수 요건 전부 충족.
> **남은 것: 미결 8 (사용자가 보류) · 시나리오 8(Ollama 끈 상태) 실제 확인 (선택).**

| 단계 | 상태 |
|---|---|
| 10주차 명세 (README 1~4번 + CONTEXT.md) | ✅ 완료 · 제출됨 |
| 상세 구현 명세서 [SPEC.md](SPEC.md) | ✅ 완료 — 구현하며 달라진 점은 13-1절 (k: 임베딩 64개씩) |
| **코드 작성** (M1~M4 분량 · 파일 9개) | ✅ 작성 · **실제 모델로 검증** (2026-11-17) |
| 구성도 · 가상 시나리오 (`docs/`) | ✅ 작성 완료 — 시나리오의 답 · 거리 · 시간은 아직 **예상** 표시 → M5 에서 실측으로 |
| **M0 사전 준비** (모델 pull · `.env`) | ✅ 보조 PC 에서 완료 (메인 PC 는 따로 pull 필요) |
| **첫 실행** (인덱스 생성 → 터미널 → 슬랙) | ✅ 2026-11-17 — 슬랙 멘션 · DM · `검색` · `비교` · 빈 멘션 · 범위 밖 왕복 |
| 평가 실측 → 기본값 채택 (M4) | ✅ E1~E4 측정 (`eval_results/`) → `config.py` 기본값 `basic` · **`year_bonus 0.09`** · `base` (사용자 승인 2026-11-17). CONTEXT 부록 D · E 는 M5 에서 |
| README 5 · 6번 · 문서 갱신 · LangSmith 캡처 (M5) | ✅ 2026-11-17 — README 5 · 6번 작성 · 맨 위 그림 · 2 · 3 · 4번 실측 반영 / CONTEXT 분할 · 메타데이터 · 처리 흐름 · 관측 · 위험 갱신 + 부록 C 복구 · **D · E · F 추가** / `docs/scenarios.md` 예상 → 실측. 2026-11-19 캡처 5장 README 반영. **남은 것: 아래 미결 8(보류) · 시나리오 8(Ollama 끄기) 확인(선택)** |

### 2026-11-17 첫 실행 결과 (실측 · 보조 PC)

| 항목 | 값 | 파일 |
|---|---|---|
| 인덱스 | 456청크 · 임베딩 6.6초 · 되읽기 «안경·선글라스 p.31» / 재귀 비교 135청크 3.0초 | `index_recycle/` · `index_recursive/` (gitignore) |
| 10주차 6문항 (`--ids scratch`) | **6/6** · 자기모순 0 (10주차와 같음) | `eval_results/20261117-145633-answer.md` |
| E1 분할 (basic · bonus 0 · 24문항) | 재귀 Top-1 **16** · Top-3 **19** → 구조 Top-1 **22** · Top-3 **23** | `…153339-retrieval` · `…153601-retrieval` |
| E2 전략 | multiquery Top-1 18~20 · Top-3 20~21 (3회) · 1.76초 ↔ basic 22 · 23 · 0.33초 → **basic** | `…153601-retrieval` |
| E3 year_bonus (g = 0.180) | 0: 22/23 · 연도충돌 top-1 2026 **2/4** / **0.5g(0.090): 23/23 · 4/4 · c1 ○** / 1g: 21/22 / 2g: 14/20 · c1 × | `…153601-retrieval` |
| 생성 30문항 | bonus 0 · base **28/30** / bonus 0.09 · base **28/30** / bonus 0 · recent 28/30 + 자기모순 1 / bonus 0.09 · recent **27/30** + 자기모순 1 → 프롬프트 **base 유지** | `…153652` · `…153846` · `…153750` · `…153940` (`-answer`) |
| 공통 오답 | **y2 생수병** — 검색 ×(사례집 p.13 «먹는 샘물» 을 못 찾음) → «유리병 수거함» 오답 / **i1 주입** — 프롬프트 누출은 없으나 «찾지 못했습니다» 대신 엉뚱한 품목 답 | 같음 |
| 시간 · VRAM | 첫 답(로딩 포함) 27.9초 · 워밍업 뒤 답 0.5~1.6초 · 봇 켠 직후 첫 슬랙 답 1.3초 · `nvidia-smi` **5.75~6.09 / 8 GB** | |
| LangSmith | 프로젝트 `recycle-bot-20241499` 에 `recycle-rag` · `recycle-plain` · `recycle-search` · `build-chunks` trace. 슬랙 질문은 metadata `slack_user` · `slack_channel` 있음 | |

- **MultiQuery 가 진 이유**: 다시 쓰기 프롬프트의 예시(«쓰봉 → 종량제봉투, 락앤락 → 플라스틱 밀폐용기»)를 A.X 가 거의 모든 질문에 끌어다 씀 («플라스틱 밀폐용기에 담긴 아이스팩 처리 방법»). 검색어 대신 답 문장을 쓰기도 함(«마트 영수증은 종이류로 분리배출해야 합니다.»). 프롬프트를 고치면 다시 잴 수 있음 — 지금은 «효과 없음» 으로 기록
- **`recent` 프롬프트**: y2 를 «찾지 못했습니다» 로 바꾸고(자기모순), bonus 0.09 와 함께 쓰면 y1 이 오답 → 채택 안 함
- **`year_bonus` 0.09 채택**: SPEC 7-3 의 `year_bonus` 규칙(«Top-3 가 줄지 않고 c1 이 깨지지 않는 값 중 연도충돌 2026 이 가장 많은 값»)으로 채택. 생성 정답은 28 = 28 로 같음 — README 의 «최신 사례 우선» 을 실제로 보여 주려고 사용자가 승인. `tests/offline_check.py` 검사도 0.09 로 바꿈
- ⚠️ `tests/offline_check.py` 는 가짜 임베딩으로 `index_recycle/` 을 **덮어씀** → 돌린 뒤에는 반드시 `python build_index.py` 로 실제 인덱스를 다시 만들 것 (manifest 의 `embed_model` 이 `fake-embed` 면 봇이 시작을 거부함)

**일정**: 13주차(11/27) 중간 점검 — 슬랙 왕복까지 · **14주차(12/4) 최종 제출**. 제출물 = 코드 + README + LangSmith 추적 캡처(필수).

### 검증한 것 / 못 한 것

| ✅ 검증함 | ❌ 아직 못 함 |
|---|---|
| 모델 없이: `build_index.py --check` 15항목 · `questions.py` · `tests/offline_check.py` 41항목 (Python 3.11 · **3.13.3** 둘 다) | 한글 경로에서의 저장 (`index.bytes` 경로) — **하지 않기로 함** (2026-11-19 사용자 판단: 평가 항목 아님 · 같은 사양의 보조 PC 에서 처음부터 세팅해 통과 · `faiss_io` 는 수업 제공 파일 그대로) |
| 실제 모델 (2026-11-17): 임베딩 · 인덱스 · 검색 · 생성 · 평가 E1~E4 — 위 «첫 실행 결과» | 슬랙 화면의 사용법 안내(빈 멘션) 문구 — 콘솔로는 분기만 확인. ℹ️ 안내 줄은 캡처(`docs/slack-compare.png`)로 확인함 |
| 실제 슬랙 왕복(멘션 · DM · 검색 · 비교 · 빈 멘션 · 범위 밖) · LangSmith trace · VRAM | Ollama 를 끈 상태의 오류 처리 (SPEC 6-5 · 선택). LangSmith · 슬랙 화면 캡처는 2026-11-19 완료 |
| 범위 밖 «찾지 못했습니다» 4/4 · i2(요리사) 거절 | **i1(시스템 프롬프트 출력 요구)** — 누출은 없으나 엉뚱한 품목 답 (오답) |

⚠️ 가짜 임베딩은 글자 2-gram 해시라 **검색 순위에 의미가 없습니다.** `offline_check.py` 가 통과했다는 것은 «코드가 끝까지 돈다» 는 뜻이지 «답이 맞다» 는 뜻이 아닙니다.

## 필수 요건 (어기면 감점 · 수업 2교시 §4-2 · §4-3 → SPEC 1장 R1~R14)

1. **슬랙으로 묻고 슬랙으로 답한다** — 채널 멘션 · DM → **같은 스레드에** 답. 터미널에서만 도는 건 요건 미충족
2. **RAG 또는 MCP** 하나 이상 → 이 프로젝트는 **RAG** (MCP · LangGraph 안 씀)
3. **LangChain 구현 + LangSmith 추적** 둘 다
4. **VRAM 8GB 에서 실제로 동작** (메인 PC: RTX 3070 8GB)
5. 피할 것: 12B 이상 모델 · 대량 크롤링 · 상용 API 상시 호출 · 범위 없는 챗봇
6. 토큰은 **루트 `.env` 에만**
7. **README 가 곧 점수**(발표 없음). 숫자는 추정 대신 **실측**으로 쓰는 것이 이 프로젝트의 원칙

## 사용자가 확정한 결정 (SPEC 0-2절)

- 구현 범위: **전체** — 기본 봇 + 검색 개선 + 평가 스크립트 + README 5 · 6번
- **MultiQuery** 와 **`year` 최신 우선 재정렬**은 반드시 구현. MMR · 하이브리드 · Self-Query · 본문 인용 번호는 넣지 않음
- 모델 설정은 전용 키 **`RECYCLE_*` + 코드 기본값**. 루트 `.env` 의 `MODEL` · `EMBED_MODEL` 은 건드리지 않음
- **OpenAI 백엔드 제거** — Ollama 만
- ✅ LangSmith 프로젝트 이름은 `config.py` 가 `recycle-bot-20241499` 로 지정(`RECYCLE_LANGSMITH_PROJECT` 로 바꿀 수 있음) — 2026-11-17 승인 · README 체크리스트 · CONTEXT «관측» 도 고침 (미결 1)

## 폴더 구조

```
langchain_20241499/                ← git 저장소 루트 (github.com/Jinseok2419342/langchain-2026-20241499)
├── .env                           ← 토큰 · 설정. 절대 커밋 금지 (.gitignore 됨)
├── venv/                          ← 파이썬 가상환경 (.gitignore 됨)
├── 11-06/                         ← 10주차 실습 — 복사 출발점 (수정 금지 · 읽기/복사만)
├── 11-13/                         ← 11주차 실습 — MultiQuery · 하이브리드 · 인용 예제 (참고용 · 수정 금지)
└── mini_project/                  ← ★ 이 프로젝트 (모든 명령은 여기서 실행)
    ├── README.md · CONTEXT.md     ← 명세 (채점 대상)
    ├── SPEC.md                    ← 상세 구현 명세서
    ├── CLAUDE.md                  ← 이 파일
    ├── config.py                  ← 공용 상수 · 경로 · RECYCLE_* · LangSmith 프로젝트 지정 (모든 파일이 맨 먼저 import)
    ├── faiss_io.py                ← 11-06/faiss_io.py 를 그대로 복사 (한글 경로 대비 · 수정 금지)
    ├── build_index.py             ← PDF 2건 → 정리 → 구역별 구조 분할 → 메타데이터 → FAISS
    ├── rag_backend.py             ← 검색기(RecycleRetriever) · ask · ask_plain · search · source_of · warmup
    ├── slack_rag_bot.py           ← Socket Mode 봇 (입구 · 출구)
    ├── questions.py               ← 평가 문항 30개 (+ 자기 검사)
    ├── evaluate.py                ← retrieval | answer 측정 → eval_results/
    ├── requirements.txt · .env.example
    ├── tests/offline_check.py     ← 모델 없이 코드 경로 확인 (41항목)
    ├── docs/architecture.md       ← 구성도 · 프로세스 · 흐름도 (Mermaid 8개)
    ├── docs/scenarios.md          ← 가상 시나리오 8개 (Mermaid 8개)
    ├── docs/*.png                 ← 캡처 5장 (trace-rag · trace-retriever · trace-build · slack-thread · slack-compare)
    ├── scratch_eval.py            ← 10주차 생성 모델 비교 스크립트 (CONTEXT 부록 C 재현용 · 그대로 둠)
    ├── not_done_plan.md           ← SPEC 작성 때의 작업 메모 (내용은 SPEC 에 반영됨 · 지워도 됨)
    ├── index_recycle/             ← build_index.py 가 만듦 (gitignore · 아직 없음)
    ├── eval_results/              ← evaluate.py 가 만듦 (커밋함 · 아직 없음)
    └── data/
        ├── 분리배출_가이드라인.pdf        ← 커밋됨 (4.8MB · 36쪽)
        └── 분리배출_QA사례100_2026.pdf   ← ⚠️ 68MB · gitignore → 없으면 아래 명령으로 받기
```

### 문서 받기 (data/ 에 사례집이 없을 때 · PowerShell, mini_project 에서)

```powershell
Invoke-WebRequest "https://sustainability.korea.ac.kr/files/Separation%20and%20discharge%20guide%20for%20recycling%20items%20(Ministry%20of%20Environment).pdf" -OutFile "data\분리배출_가이드라인.pdf"
Invoke-WebRequest "https://www.kwaste.or.kr/lib/fileDownload.php?save_file=attachment_202605081124500.29008db5d7c61e61718f7a154de14539.pdf&file_name=QA100.pdf" -OutFile "data\분리배출_QA사례100_2026.pdf"
```
(사례집 원 게시글: 한국폐기물협회 공지 `https://www.kwaste.or.kr/community/01.php?admin_mode=read&no=6128` · 2026-11-13 에 위 링크로 68,862,868바이트 내려받기 확인)

## 다음 할 일 — 첫 실행 순서 (0~7번은 2026-11-17 보조 PC 에서 통과 · 8번은 2026-11-19 캡처까지 완료)

> 메인 PC 에서 다시 돌릴 때도 이 순서. 0번(모델 pull · 사례집 PDF)은 PC 마다 필요. 8번 전에 `year_bonus` 채택을 사용자에게 확인.

```powershell
cd mini_project
$env:PYTHONUTF8=1
```

| # | 명령 | 통과 조건 | 막히면 |
|---|---|---|---|
| 0 | `ollama pull hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M` · `ollama pull hf.co/mykor/KURE-v1-gguf:Q8_0` · 루트 `.env` 의 `LANGSMITH_TRACING=true` · `ollama ps` 로 GPU 비우기 · 10주차 봇 끄기 | `ollama list` 에 두 줄 | SPEC 2-2절 |
| 1 | `python build_index.py --check` | 15항목 ✅ (임베딩 없음) | 사례집 PDF 가 없으면 위 «문서 받기» |
| 2 | `python tests/offline_check.py` | `ALL OK` (41항목 · 모델 없음) | 패키지 버전 차이 — 메인 PC 는 Python 3.13 · 이 검사는 3.11 에서 돌렸음 |
| 3 | `python build_index.py` | `✅ 저장` + 되읽기 확인 줄에 «안경·선글라스 p.31» · `index_recycle/manifest.json` 생김 | 한글 경로면 `index.bytes` 로 저장되는 것이 정상 |
| 4 | `python rag_backend.py "뽁뽁이는 어떻게 버려요?"` · `검색 "선글라스"` · `비교 "마트 영수증은 종이로 버려도 돼?"` | 검색 1~3위에 정답 품목 · 답 · 근거 줄 | 검색이 엉뚱하면 임베딩 모델 · manifest 부터 |
| 5 | `python evaluate.py answer --ids scratch` | 10주차와 같은 6문항 — **6/6 이 나오는지** (CONTEXT 부록 C 와 비교) | 6/6 이 아니면 분할이 바뀐 영향 — 어느 문항인지 `eval_results/` 에서 확인 |
| 6 | `python slack_rag_bot.py` → 슬랙에서 멘션 · DM · `검색` · `비교` · 빈 멘션 | SPEC 6-5절 체크리스트 · LangSmith 에 `recycle-rag` trace · `nvidia-smi` 8GB 미만 | 봇이 답을 안 하면 `10-30/socket_hello.py` 로 슬랙 쪽부터 |
| 7 | `python build_index.py --mode recursive --out index_recursive` → `python evaluate.py retrieval --index index_recursive` → `python evaluate.py retrieval` → `python evaluate.py answer` (→ `--prompt recent`) | E1~E4 결과가 `eval_results/` 에 | SPEC 7-3절 채택 규칙 |
| 8 | 채택한 값을 `config.py` 기본값에 반영 → README 5 · 6번 · CONTEXT 부록 D · E · `docs/scenarios.md` 의 «예상» 을 실제 출력으로 → LangSmith 캡처 7장 | SPEC 8-2절 · 9장 | 캡처는 **사용자가 직접** · 무료 플랜 14일 → 제출 직전에 |

**처음 실행에서 깨질 가능성이 있던 곳 → 2026-11-17 확인 결과**

1. **`keep_alive`** — ✅ 정수 `1800` 을 Ollama 가 받음 (`ollama ps` 에 «29 minutes from now»)
2. **A.X 의 다시 쓰기 출력 형식** — ❌ 줄바꿈 형식은 지키지만 **내용이 문제**: 프롬프트 예시(종량제봉투 · 플라스틱 밀폐용기)를 거의 모든 질문에 섞고, 답 문장 · «다음 검색 질문을 사용할 수 있습니다:» 같은 설명 줄도 냄 → E2 에서 basic 보다 나쁨
3. **`is_not_found` 의 60자 기준** — ✅ 범위 밖 4문항 · 슬랙 «강남구» 모두 «자료에서 찾지 못했습니다.» 한 문장
4. **검색 품질** — ✅ 짧은 품목사전 청크가 오히려 유리 (구조 Top-3 23/24 ↔ 재귀 19/24)
5. **`year_bonus` 의 눈금** — g = **0.180** (구조) · 0.134 (재귀). 0.5g = 0.090 이 후보
6. **슬랙 이벤트** — ✅ `bot_id` 거르기로 자기 답에 다시 답하지 않음. DM 은 `im:history` scope 가 없어 처음엔 안 왔음 (함정 17)

**사용자가 직접 해야 하는 일** (그 차례에 멈추고 요청): 모델 pull · `.env` 변경 승인 / `--show qa_case` 100줄 눈 확인 / 슬랙에서 질문 · 화면 캡처 / LangSmith 캡처 / 커밋 · 푸시 승인

## 환경 (메인 PC 기준 · SPEC 2장)

- **OS: Windows** · PowerShell / Git Bash. **경로에 한글(`최신인공`)이 있음** ← 함정 1
- 파이썬: `..\venv\Scripts\python.exe` (3.13.3). 필요한 패키지는 설치돼 있음 — 새 패키지를 추가하지 않음
- `venv/` · `.env` · `index*/` · 사례집 PDF 는 gitignore 라 **다른 클론에는 없음**
- Ollama 0.32.14 · 모델:

| 모델 이름 (Ollama) | 용도 | 상태 |
|---|---|---|
| `hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M` | ★ **생성** (SKT A.X 4.0 Light 7B · 4.4GB) | ⚠️ 2026-11-13 `ollama list` 에 **없었음** → pull |
| `hf.co/mykor/KURE-v1-gguf:Q8_0` | ★ **임베딩** (고려대 KURE-v1 · 1024차원 · 0.6GB) | ⚠️ 위와 같음 |
| `gemma3:4b` · `qwen3-embedding:0.6b` | 수업 기본 — **비교 기준으로만** | 설치됨 |
| `exaone3.5:2.4b` | 생성 모델 대체용 (`RECYCLE_MODEL` 로 교체 · 인덱스 재생성 불필요) | 설치됨 |

- 루트 `.env` (값은 출력하지 말 것 · 키 이름은 [.env.example](.env.example)):

| 키 | 현재 | 할 일 |
|---|---|---|
| `SLACK_BOT_TOKEN` · `SLACK_APP_TOKEN` · `LANGSMITH_API_KEY` | 있음 | 그대로 |
| `LANGSMITH_TRACING` | `false` | **`true` 로** (사용자 확인 후) |
| `EMBED_MODEL` · `MODEL` | 다른 주차 실습용 | **건드리지 않음** — 이 프로젝트는 읽지 않음 |
| `RECYCLE_*` | 없음 | 넣지 않아도 됨. 바꿔서 잴 때만 |

- 환경 변수로 바꿀 수 있는 것: `RECYCLE_MODEL` · `RECYCLE_EMBED_MODEL` · `RECYCLE_STRATEGY`(basic\|multiquery) · `RECYCLE_YEAR_BONUS` · `RECYCLE_PROMPT`(base\|recent) · `RECYCLE_INDEX` · `RECYCLE_LANGSMITH_PROJECT`.
  ⚠️ «실행 한 번 = 설정 하나» — 인덱스 · 모델을 한 번만 읽어 계속 쓰므로 실행 중에는 바뀌지 않음

## 구현 요약 (자세한 건 SPEC · 그림은 docs/architecture.md)

- **문서 2건**: 환경부 가이드라인(2018 · 36쪽 · 기준) + 한국폐기물협회 Q&A 사례 100(2026 · 52쪽 · 최신 사례).
  2018 문서에는 «무색페트병» 이 0회 → 최신 우선이 필요 → `year` 메타데이터(**int**)
- **분할 = 구역별 구조 단위 → 긴 것만 재귀 400/40** — 구현 실측 **456청크**

  | 구역 | 단위 | 실측 (`--check`) | 함수 |
  |---|---|---|---|
  | 사례집 Q&A (6~46쪽) | 1건 = 1청크 · 본문 «품목: … / Q. … / A. …» | **100** · 평균 151자 | `split_qa_cases` · `parse_qa_page` |
  | 가이드라인 FAQ (21~25쪽) | «Q :» 1개 = 1청크 | **36** · 평균 106자 | `split_faq` |
  | 가이드라인 품목사전 (28~34쪽) | 품목 1개 = 1청크 | **282** · 평균 20자 (`ITEM_DROP` 4건 제외) | `split_item_dict` |
  | 가이드라인 본문 (3~20쪽) | 쪽 단위 → 재귀 400/40 + `section` | **38** · 평균 295자 | `split_guideline` |

  비교용 재귀 인덱스(`--mode recursive`): **135청크 · 평균 307자**
- **메타데이터**: `source` · `page`(int) · `year`(int) · `doc_type`(qa_case/faq/item_dict/guideline) · `material` · `item` · `qa_date` · `section` · `chunk_id` · `splitter`.
  값이 없으면 키를 **넣지 않음**. FAQ 에는 `material` · `item` 없음
- **인덱스**: FAISS + `faiss_io` · `index_recycle/` · **`manifest.json`** 에 임베딩 모델 기록 → 읽을 때 다르면 종료
- **검색** (`rag_backend.py`): `RecycleRetriever`(`BaseRetriever`) = `rewrite_queries`(multiquery 일 때만) → `candidates`(질문마다 10개 · 같은 청크는 최소 거리) → `rank`(year ≥ 2020 이면 거리 − `year_bonus` · 상위 3개).
  돌려주는 청크의 metadata 에 `distance` · `adjusted` · `via` 를 덧붙임(복사본에). **기본값 `basic` · `0` — 평가 실측 전에는 바꾸지 않음**
- **생성**: LCEL `RAG_PROMPTS["base"] | ChatOllama(temperature=0.1, num_predict=300, num_ctx=4096, keep_alive=1800) | StrOutputParser`.
  `base` 프롬프트는 `scratch_eval.py` 의 `PROMPT` 와 **글자 단위로 같음** (부록 C 의 6/6 이 이 문구로 잰 값). `recent` 는 E4 실험용
- **출처 형식**: `안경·선글라스 · 사례집(2026) p.31` — 코드가 metadata 로 만듦(`source_of`)
- **슬랙** (`slack_rag_bot.py`): 멘션 + DM, 전부 `thread_ts` 로(같은 스레드), `검색` · `비교` 모드, ⏳ 자리잡기 → `chat_update`, 300자 제한,
  «찾지 못했습니다» 면 근거 숨기고 구청 안내, 근거에 2018 · 2026 이 섞이면 ℹ️ 안내 줄, 예외 내용은 콘솔에만, `&` `<` `>` 이스케이프, 봇 메시지 무시, 시작 시 워밍업
- **LangSmith**: 프로젝트 `recycle-bot-20241499` · trace `recycle-rag`(아래 `RecycleRetriever` + `generate`) · `recycle-plain` · `recycle-search` · `build-chunks` · 태그 `rag`/`no-rag`/`search`/`eval`
- **평가** (`evaluate.py`): `retrieval` = 전략 × `year_bonus`(0 · 0.5g · 1g · 2g) 격자 · multiquery 3회 반복 / `answer` = `must` · `bad` · 자기모순 채점.
  옵션 `--index` · `--model` · `--prompt` · `--strategy` · `--year-bonus` · `--ids`(`scratch` = 10주차 6문항) · `--repeats` · `--no-multiquery`

## 10주차 실측 (근거 데이터 · 자세한 건 CONTEXT 부록 — 구현 뒤의 측정값은 아직 없음)

- 임베딩(재귀 400/40 · **181청크** · 일상 말투 15문항): Top-3 정답 qwen3 **12/15** → KURE **15/15**
- 생성(KURE top-3 · 6문항): gemma3:4b **4/6**(자기모순 2회) → A.X **6/6**, 답당 0.4~0.7초, 첫 호출 20초(로딩)
- VRAM: A.X 4.6GB + KURE 0.38GB → nvidia-smi **5.6GB / 8GB**
- ⚠️ 위는 **구조 분할 전**(재귀 181청크)의 값. 지금 인덱스는 456청크라 같은 숫자가 나온다는 보장이 없음 → «다음 할 일» 5 · 7번으로 다시 잼

## 함정 (밟았거나 실측으로 확인한 것 · 전체는 SPEC 12장)

1. **한글 경로 + FAISS** — `store.save_local()` 이 RuntimeError. 반드시 `faiss_io.save_index` / `load_index` (`index.bytes` 로 저장되는 것이 정상)
2. **머리말 정규식은 문서별로 2개** (`build_index.py` 의 `HDR_G` · `HDR_Q`). ⚠️ `scratch_eval.py` 의 `HDR` 은 **쓰지 말 것** — 가이드라인 머리말 34줄 중 17줄이 남고, 사례집의 **사례 번호 줄**까지 지움
3. **사례집을 날짜 순서대로 자르면 100건 중 24건이 틀림** — 2단 배치. 품목 이름으로 짝짓기(`parse_qa_page`). 파서를 고치면 반드시 `--check`
4. **품목사전** — 30자 필터 금지(평균 20자). 초성 줄은 14글자만 지움(낫 · 못 · 컵 … 은 품목). 뜻이 틀어진 4건은 `ITEM_DROP`
5. **임베딩 모델이 달라도 오류가 안 남** — qwen3 와 KURE 가 둘 다 1024차원 → `manifest.json` 비교가 유일한 장치
6. **`config` 를 langchain · langsmith 보다 먼저 import** — 아니면 LangSmith 프로젝트 이름이 안 먹음. `evaluate.py` 는 `--index` · `--model` · `--prompt` 를 그보다도 먼저 읽음
7. **`keep_alive` 는 정수** — `OllamaEmbeddings` 는 `"30m"` 을 받지 않음(ValidationError). `config.KEEP_ALIVE = 1800`
8. **`year_bonus` 부작용** — «뽁뽁이» 의 정답은 2018 문서인데 2026 사례집에 «은박 에어캡(뽁뽁이)» 라는 다른 품목이 있음. 감시 문항 `c1`
9. **다시 쓰기 프롬프트의 예시에 평가 문항의 품목을 넣지 말 것** — 점수가 부풀려짐 (지금 예시: 쓰봉 · 락앤락)
10. **평가 문항을 고치면 `python questions.py`** — 정답 위치가 실제 청크에 있는지 검사. 틀린 정답 위치로 재면 숫자가 전부 거짓
11. **Ollama 가 안 쓰는 모델도 5분간 GPU 에 남김** — 측정 전 `ollama ps` → `ollama stop <모델>`
12. **토큰 검사를 접두어(`xoxb-`)로 하면 안 됨** — 봇 코드의 접두어 검사에 걸림. SPEC 1장 «토큰 누출 검사» 의 식 사용
13. **콘솔 cp949** — 스크립트는 `sys.stdout.reconfigure(encoding="utf-8")` 를 함. PowerShell 은 `$env:PYTHONUTF8=1`
14. **10주차 봇과 동시 실행 금지** — 같은 `SLACK_APP_TOKEN` 이면 이벤트가 둘로 갈림
15. `pypdf` 직접 호출과 `PyPDFLoader` 는 쪽 끝 공백이 달라 글자 수 · 재귀 청크 수가 1씩 다를 수 있음 → 문서에는 구현 출력값
16. **임베딩을 한 요청에 456개 보내면 Ollama 0.32.14 러너가 간헐적으로 죽음** (`…/tokenize: connection refused` · 3회 중 2회) → `build_index.py` 는 `EMBED_BATCH = 64` 개씩 보냄 (2026-11-17 · SPEC 13-1 k)
17. **DM 이 안 오면 봇 토큰 scope 에 `im:history` 가 있는지** — `app_mentions:read` 만 있으면 멘션만 됨. scope 추가 후 **Reinstall to Workspace** 필요. App Home 의 Messages Tab 도 켤 것
18. **슬랙의 실제 봇 이름은 `@Jinseok-20241499-Bot`** — 문서의 `@버릴지도` 는 별명. `@봇 @버릴지도 검색 …` 처럼 두 번 쓰면 `검색` · `비교` 모드가 안 걸림
19. 보조 PC 의 Ollama 는 PATH 에 없음 (`%LOCALAPPDATA%\Programs\OllamaAIClass\ollama.exe`) — `evaluate.py` 가 `ollama ps` 를 부르므로 `$env:Path += ";$env:LOCALAPPDATA\Programs\OllamaAIClass"` 후 실행
20. PowerShell 에서 한글이 깨지면 `[Console]::OutputEncoding=[Text.Encoding]::UTF8` (`PYTHONUTF8` 만으로는 파이프 출력이 깨짐)

## 사용자 확인이 필요한 미결 사항 (SPEC 13장)

채점 문서(README · CONTEXT)라 임의로 고치지 않고 남겨 둔 것입니다. «다음 할 일» 8번에서 문서를 갱신할 때 함께 정리합니다.

1. ✅ **LangSmith 프로젝트 이름 위치** — `config.py` 로 확정(사용자가 «진행» 승인 · 2026-11-17). README 체크리스트 · CONTEXT «관측» 도 그렇게 고침
2. ✅ **README 3번 «외부 API» 문장** — «검색 · 생성 모두 로컬 · 질문이 외부 LLM API 로 나가지 않음» + «LangSmith 추적을 켜면 질문 · 근거 · 답이 LangSmith 에 기록됨» 단서로 고침 (사용자 승인 · 2026-11-19)
3. ✅ **사례집 발행일** — CONTEXT 를 «2026.03 (판권 발행일 2026-03-26 · 협회 공지 게시 2026-05-08)» 로 고침. 2026.05 는 첨부파일 이름(`attachment_20260508 1124…`)의 게시 시각 (사용자 승인 · 2026-11-19). `year` 메타데이터는 2026 그대로라 코드 · 인덱스 영향 없음
4. ✅ CONTEXT 부록 C «마트 영수증» 행 — 2026-11-17 `scratch_eval.py` 재실행 답으로 채움(각주로 밝힘)
5. ✅ 구현 실측값 — CONTEXT 분할 표에 «구현 결과» 표 추가(282 · 106자 · 456 · 쪽 단위 + `section`) · 메타데이터 표 갱신. 설계 때 시험 표(243 등)는 «설계 기록» 으로 남김
6. ✅ README 맨 위 그림 · CONTEXT 처리 흐름 그림 — 실제 출력 형식(«아이스팩 · 가이드라인(2018) p.31»)으로 통일 · «구현 예정» 삭제
7. ✅ README 5번 · 6번 작성 (2026-11-17 실제로 돌린 명령 · 결과)
8. ⏳ **슬랙 봇 표시 이름** — 문서 · 사용법 안내는 `@버릴지도`, 실제는 `@Jinseok-20241499-Bot`. (가) 앱 표시 이름을 바꿈 / (나) 안내 문구를 고침 → **사용자가 나중에 결정**. README 5-4절은 `@봇` 으로 적어 둠. 2026-11-19: 당분간 그대로 둠 — 기존 슬랙 앱 설정의 표시 이름이라 동작에는 문제 없음

## 작업 규칙

- README · CONTEXT 의 숫자를 바꾸면 **두 문서를 같이** 고칠 것. 코드가 SPEC 과 달라지면 SPEC 13-1절에 적을 것
- 새 숫자는 **실제로 돌려서** 얻은 것만 적을 것. 추정이면 «계산» · «예상» 이라고 표시. 효과가 없었으면 없었다고 적을 것
- 한 번에 하나만 바꾸고 잴 것 (임베딩 · 분할 · 검색 전략 · 프롬프트)
- 코드를 고치면 `python build_index.py --check` · `python tests/offline_check.py` 를 다시 돌릴 것
- `11-06/` · `11-13/` 의 파일과 인덱스는 수정하지 말 것 (읽기 · 복사만)
- 토큰 · 키를 코드 · 로그 · 커밋 · 슬랙 메시지에 넣지 말 것. `.env` 내용을 출력하지 말 것. 68MB PDF 커밋 금지
- 커밋 · 푸시, 파일 삭제, `.env` 수정은 **사용자에게 확인받고** 할 것
- 커밋 메시지는 한국어, 기존 형식(`mini_project: …`, `week10: …`)을 따름
