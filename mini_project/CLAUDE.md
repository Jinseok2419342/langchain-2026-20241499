# CLAUDE.md — 버릴지도 (분리배출 안내 RAG 슬랙 봇)

이 파일은 다음 세션의 Claude Code 가 이 프로젝트를 처음 보고도 이어서 작업할 수 있게 쓴 인수인계 문서입니다.
**읽는 순서: 이 파일 → [SPEC.md](SPEC.md) (구현 지시서) → [README.md](README.md) · [CONTEXT.md](CONTEXT.md) (채점 대상 명세).**
구현은 **SPEC.md 를 따릅니다.** 이 파일은 요약과 현재 상태만 담습니다 — 세부 규칙 · 코드 · 수용 기준은 전부 SPEC 에 있습니다.

## 한 줄 요약

슬랙에서 «뽁뽁이 어떻게 버려?» 라고 물으면, 분리배출 PDF 2건에서 근거를 찾아(RAG) 배출 방법 + 출처(품목 · 문서 · 연도 · 쪽)를 스레드에 답하는 봇.
동양미래대 «최신인공지능» 수업(학번 20241499) 미니 프로젝트. **응답은 한국어로.**

## 현재 상태 (2026-11-13 기준)

| 단계 | 상태 |
|---|---|
| 10주차 명세 (README 1~4번 + CONTEXT.md) | ✅ 완료 · 제출됨 |
| 모델 선정 · 실측 (임베딩 · 생성 · VRAM) | ✅ 완료 (CONTEXT 부록 A · B · C) |
| 대상 문서 확보 · 파싱 확인 | ✅ 완료 (`data/`) |
| **상세 구현 명세서 [SPEC.md](SPEC.md)** | ✅ 완료 — 0~13장 · 마일스톤 M0~M5. 파서 코드는 실제 PDF 로, 검색기 코드는 가짜 모델로 검증 |
| **코드 구현** | ❌ **아직 없음 — 다음 작업 (SPEC 의 M0 부터)** |
| LangSmith 켜기 | ❌ 루트 `.env` 가 `LANGSMITH_TRACING=false` |
| 11주차 검색 개선 (MultiQuery · `year` 최신 우선) · 평가 | ❌ (SPEC 5-3절 · 7장) |
| 14주차 README 5 · 6번 + LangSmith 캡처 | ❌ (SPEC 8 · 9장) |

**일정**: 13주차(11/27) 중간 점검 — M0~M3 · **14주차(12/4) 최종 제출** — M4~M5. 제출물 = 코드 + README + LangSmith 추적 캡처(필수).

## 필수 요건 (어기면 감점 · 수업 2교시 §4-2 · §4-3 → SPEC 1장 R1~R14)

1. **슬랙으로 묻고 슬랙으로 답한다** — 채널 멘션 · DM → **같은 스레드에** 답. 터미널에서만 도는 건 요건 미충족
2. **RAG 또는 MCP** 하나 이상 → 이 프로젝트는 **RAG** (MCP · LangGraph 안 씀)
3. **LangChain 구현 + LangSmith 추적** 둘 다
4. **VRAM 8GB 에서 실제로 동작** (개발 PC: RTX 3070 8GB)
5. 피할 것: 12B 이상 모델 · 대량 크롤링 · 상용 API 상시 호출 · 범위 없는 챗봇
6. 토큰은 **루트 `.env` 에만**
7. **README 가 곧 점수**(발표 없음). 숫자는 추정 대신 **실측**으로 쓰는 것이 이 프로젝트의 원칙

## 사용자가 확정한 결정 (2026-11-13 · SPEC 0-2절)

- 구현 범위: **전체** — 기본 봇 + 검색 개선 + 평가 스크립트 + README 5 · 6번
- **MultiQuery** 와 **`year` 최신 우선 재정렬**은 반드시 구현. MMR · 하이브리드 · Self-Query · 본문 인용 번호는 넣지 않음
- 모델 설정은 전용 키 **`RECYCLE_MODEL` · `RECYCLE_EMBED_MODEL` + 코드 기본값**. 루트 `.env` 의 `MODEL` · `EMBED_MODEL` 은 건드리지 않음
- **OpenAI 백엔드 제거** — Ollama 만
- ⏳ **확정 대기**: LangSmith 프로젝트 이름을 `config.py` 가 정할지(SPEC 현재안 · 권장) 루트 `.env` 에 둘지(README · CONTEXT 현재 문구)

## 폴더 구조

```
langchain_20241499/                ← git 저장소 루트 (github.com/Jinseok2419342/langchain-2026-20241499)
├── .env                           ← 토큰 · 설정. 절대 커밋 금지 (.gitignore 됨)
├── venv/                          ← 파이썬 가상환경 (.gitignore 됨)
├── 11-06/                         ← 10주차 실습 — 복사 출발점 ★ (수정 금지 · 읽기/복사만)
│   ├── slack_bot_mode/            ← 학칙 RAG 슬랙 봇: build_index.py · rag_backend.py · slack_rag_bot.py
│   ├── faiss_io.py                ← 한글 경로에서 FAISS 저장 · 읽기 → mini_project/ 로 **복사**해서 씀
│   ├── project_template/          ← 수업이 준 README · CONTEXT 템플릿
│   └── 1·2·3교시_*.pdf            ← 수업 자료 (요건 원문은 2교시 23~29쪽)
├── 11-13/                         ← 11주차 실습 — MultiQuery · 하이브리드 · 인용 예제 (참고용 · 수정 금지)
└── mini_project/                  ← ★ 이 프로젝트
    ├── README.md · CONTEXT.md     ← 명세 (채점 대상)
    ├── SPEC.md                    ← ★ 상세 구현 명세서 (구현은 이걸 따른다)
    ├── CLAUDE.md                  ← 이 파일
    ├── not_done_plan.md           ← SPEC 작성 때의 작업 메모 (내용은 SPEC 에 반영됨 · 참고용)
    ├── scratch_eval.py            ← 생성 모델 비교 실측 스크립트 (CONTEXT 부록 C 재현용 · 그대로 둠)
    └── data/
        ├── 분리배출_가이드라인.pdf        ← 커밋됨 (4.8MB · 36쪽)
        └── 분리배출_QA사례100_2026.pdf   ← ⚠️ 68MB · .gitignore 됨 → 없으면 아래 명령으로 받기
```

만들 파일 (SPEC 3-1절): `config.py` · `faiss_io.py`(복사) · `build_index.py` · `rag_backend.py` · `slack_rag_bot.py` · `questions.py` · `evaluate.py` · `requirements.txt` · `.env.example` · `index_recycle/`(gitignore) · `eval_results/` · `docs/`

### 문서 받기 (data/ 에 사례집이 없을 때 · PowerShell, mini_project 에서)

```powershell
Invoke-WebRequest "https://sustainability.korea.ac.kr/files/Separation%20and%20discharge%20guide%20for%20recycling%20items%20(Ministry%20of%20Environment).pdf" -OutFile "data\분리배출_가이드라인.pdf"
Invoke-WebRequest "https://www.kwaste.or.kr/lib/fileDownload.php?save_file=attachment_202605081124500.29008db5d7c61e61718f7a154de14539.pdf&file_name=QA100.pdf" -OutFile "data\분리배출_QA사례100_2026.pdf"
```
(사례집 원 게시글: 한국폐기물협회 공지 `https://www.kwaste.or.kr/community/01.php?admin_mode=read&no=6128` · 2026-11-13 에 위 링크로 68,862,868바이트 내려받기 확인)

## 환경 (개발 PC 기준 · SPEC 2장)

- **OS: Windows** · PowerShell / Git Bash. **경로에 한글(`최신인공`)이 있음** ← 아래 함정 1
- 파이썬: `..\venv\Scripts\python.exe` (3.13.3). 필요한 패키지는 설치돼 있음 — 새 패키지를 추가하지 않음
- `venv/` · `.env` · `index*/` · 사례집 PDF 는 gitignore 라 **다른 클론에는 없음** → 시작 전에 있는지 확인
- Ollama 0.32.14 · 모델:

| 모델 이름 (Ollama) | 용도 | 상태 |
|---|---|---|
| `hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M` | ★ **생성** (SKT A.X 4.0 Light 7B · 4.4GB) | ⚠️ 2026-11-13 `ollama list` 에 **없었음** → M0 에서 `ollama pull` |
| `hf.co/mykor/KURE-v1-gguf:Q8_0` | ★ **임베딩** (고려대 KURE-v1 · 1024차원 · 0.6GB) | ⚠️ 위와 같음 |
| `gemma3:4b` · `qwen3-embedding:0.6b` | 수업 기본 — **비교 기준으로만** | 설치됨 |
| `exaone3.5:2.4b` | 생성 모델 대체용 (`RECYCLE_MODEL` 로 교체 · 인덱스 재생성 불필요) | 설치됨 |

- 루트 `.env` (값은 출력하지 말 것):

| 키 | 현재 | 할 일 |
|---|---|---|
| `SLACK_BOT_TOKEN` · `SLACK_APP_TOKEN` · `LANGSMITH_API_KEY` | 있음 | 그대로 |
| `LANGSMITH_TRACING` | `false` | **`true` 로** (사용자 확인 후) |
| `EMBED_MODEL` | `qwen3-embedding:0.6b` | **건드리지 않음** — 바꾸면 `11-06` · `11-13` 인덱스가 깨짐 |
| `RECYCLE_*` | 없음 | 넣지 않아도 됨 (코드 기본값). 모델 · 전략을 바꿔 잴 때만 |
| `LANGSMITH_PROJECT` | 없음 | SPEC 현재안은 **넣지 않음** (`config.py` 가 `recycle-bot-20241499` 로 지정) — 위 «확정 대기» |

## 설계 결정 요약 (자세한 건 SPEC · 바꾸려면 README · CONTEXT 도 같이)

- **문서 2건**: 환경부 가이드라인(2018 · 36쪽 · 기준) + 한국폐기물협회 Q&A 사례 100(2026 · 52쪽 · 최신 사례).
  2018 문서에는 «무색페트병» 이 0회 → 최신 우선이 필요 → `year` 메타데이터(**int**)
- **분할 = 구역별 구조 단위 → 긴 것만 재귀 400/40** (시험 파서 실측 합계 **460청크**)

  | 구역 | 단위 | 실측 | SPEC |
  |---|---|---|---|
  | 사례집 Q&A (6~46쪽) | 1건 = 1청크 · 본문 «품목: … / Q. … / A. …» | **100건** · 평균 151자 | 4-4절 |
  | 가이드라인 FAQ (21~25쪽) | «Q :» 1개 = 1청크 | **36건** · 평균 106자 | 4-5절 |
  | 가이드라인 품목사전 (28~34쪽) | 품목 1개 = 1청크 | **286건** · 평균 20자 | 4-6절 |
  | 가이드라인 본문 (3~20쪽) | 쪽 단위 → 재귀 400/40 + `section` | **38청크** · 평균 295자 | 4-7절 |

  버리는 쪽: 가이드라인 1 · 2 · 26(과태료 표) · 27 · 35 · 36 / 사례집 1~5 · 47~52 · 장 구분쪽 12개(장 이름 · 품목 목록만 읽음)
- **메타데이터**: `source` · `page`(int, 1부터) · `year`(int) · `doc_type`(qa_case/faq/item_dict/guideline) · `material` · `item` · `qa_date` · `section` · `chunk_id` · `splitter`.
  값이 없으면 키를 **넣지 않음**(None · 빈 문자열 금지). FAQ 에는 `material` · `item` 없음 (SPEC 4-8절)
- **인덱스**: FAISS + `faiss_io` · `index_recycle/` · **`manifest.json`** 에 임베딩 모델 기록 → 읽을 때 다르면 종료
- **검색**: `RecycleRetriever`(`BaseRetriever` 상속) — `basic` | `multiquery`, `year >= 2020` 이면 L2 거리에서 `year_bonus` 차감, top-3.
  **기본값(전략 · bonus)은 추측으로 정하지 않고 7장 평가 실측으로 채택** (같으면 단순한 쪽)
- **생성**: LCEL `RAG_PROMPT | ChatOllama(temperature=0.1, num_predict=300, num_ctx=4096, keep_alive="30m") | StrOutputParser`.
  프롬프트는 `scratch_eval.py` 의 `PROMPT` 를 **한 글자도 바꾸지 않고** 사용 (부록 C 의 6/6 이 이 문구로 잰 값)
- **출처 형식**: `안경·선글라스 · 사례집(2026) p.31` — 코드가 metadata 로 만듦. 근거에 2018 · 2026 이 섞이면 ℹ️ 안내 줄
- **슬랙**: 10주차 `slack_rag_bot.py` 구조 — 멘션 + DM, `thread_ts` 로 같은 스레드, `검색` · `비교` 모드, ⏳ 자리잡기 → `chat_update`, 300자 제한,
  «찾지 못했습니다» 면 근거 숨기고 구청 안내, 예외 내용은 콘솔에만, `&` `<` `>` 이스케이프, 시작 시 워밍업
- **LangSmith**: 프로젝트 `recycle-bot-20241499` · 질문 1건 = trace `recycle-rag`(아래 `RecycleRetriever` + `generate`) · 전처리 `@traceable` · 태그 `rag`/`no-rag`/`eval`

## 실측 결과 요약 (근거 데이터 · 자세한 건 CONTEXT 부록)

- 임베딩(재귀 400/40 · **181청크** · 일상 말투 15문항): Top-3 정답 qwen3 **12/15** → KURE **15/15**. qwen3 실패 = 뽁뽁이 · 아이스팩 · 핫팩(동의어)
- 생성(KURE top-3 · 6문항): gemma3:4b **4/6**(자기모순 2회) → A.X **6/6**, 답당 0.4~0.7초, 첫 호출 20초(로딩)
- VRAM: A.X 4.6GB + KURE 0.38GB → nvidia-smi **5.6GB / 8GB**
- 위 15문항 원본은 저장소에 없음 → SPEC 7장의 새 문항 세트(씨앗 24 → 30)로 기준과 개선안을 함께 다시 잼

## 함정 (이미 밟았거나 실측으로 확인한 것 · 전체 18개는 SPEC 12장)

1. **한글 경로 + FAISS** — `store.save_local()` 이 RuntimeError. 반드시 `faiss_io.save_index` / `load_index` (`index.bytes` 로 저장되는 것이 정상)
2. **머리말 정규식은 문서별로 2개** (SPEC 4-3절 · 둘 다 `re.M`):
   ```python
   HDR_G = re.compile(r"^[ \t]*(?:재활용품 분리배출[ \t]*\d*|\d+[ \t]*재활용품 분리배출)[ \t]*$", re.M)
   HDR_Q = re.compile(r"^[ \t]*(?:2026[넌년]도 내 손안의 분리배출 앱|Q&A 사례 100)[ \t]*$", re.M)
   ```
   ⚠️ `scratch_eval.py` 의 `HDR`(예전에 여기 «검증됨» 이라 적었던 것)은 **쓰지 말 것** — 가이드라인 머리말 34줄 중 17줄이 남고(줄 앞 공백),
   «숫자 1~2자리 줄» 삭제가 사례집의 **사례 번호 줄**까지 지움. 사례집 원본 오탈자 «2026**넌**도» 35회 + «2026년도» 15회는 둘 다 잡아야 함
3. **사례집을 날짜 순서대로 자르면 100건 중 24건이 틀림** — 2단 배치라 메타(날짜 → 라벨 → 번호)와 본문(Q → A)의 순서가 쪽 안에서 다름.
   → **품목 이름이 질문에 들어 있는지로 짝짓기** (SPEC 4-4절 참고 구현 · 100건 · 경고 0 확인)
4. **품목사전** — 30자 미만 필터를 걸면 286개 중 239개가 사라짐(필터는 본문에만). 초성 줄은 14글자만 지움(낫 · 못 · 컵 … 은 품목).
   2단 배치로 이웃 항목이 섞여 **뜻이 틀어진 4건**은 `ITEM_DROP` 으로 제외 (SPEC 4-6절)
5. **임베딩 모델이 달라도 오류가 안 남** — qwen3 와 KURE 가 둘 다 1024차원 → `manifest.json` 비교가 유일한 장치
6. **`config` 를 langchain · langsmith 보다 먼저 import** — 아니면 LangSmith 프로젝트 이름이 안 먹음
7. **`year_bonus` 부작용** — «뽁뽁이» 의 정답은 2018 문서인데 2026 사례집에 «은박 에어캡(뽁뽁이)» 라는 다른 품목이 있음. 값이 크면 이쪽이 올라옴
8. **Ollama 가 안 쓰는 모델도 5분간 GPU 에 남김** — qwen3-embedding:0.6b 가 같이 떠 있으면 7.2GB 까지 참. 측정 전 `ollama ps` → `ollama stop <모델>`
9. **토큰 검사를 접두어(`xoxb-`)로 하면 안 됨** — 봇 코드의 접두어 검사에 걸림. SPEC 1장 «토큰 누출 검사» 의 식 사용
10. **콘솔 cp949** — 스크립트 시작에 `sys.stdout.reconfigure(encoding="utf-8")`, PowerShell 은 `$env:PYTHONUTF8=1`
11. **10주차 봇과 동시 실행 금지** — 같은 `SLACK_APP_TOKEN` 이면 이벤트가 둘로 갈림
12. `pypdf` 직접 호출과 `PyPDFLoader` 는 쪽 끝 공백이 달라 글자 수 · 재귀 청크 수가 1씩 다를 수 있음(181 ↔ 182) → 구현은 `PyPDFLoader`, 문서에는 구현 출력값
13. `langchain_community` DeprecationWarning — 무시 (동작 무관) · `gemma3:4b` 는 Ollama 도구 호출 미지원(MCP 를 붙일 일이 생기면 모델부터 확인)

## 다음 할 일 (SPEC 10장 마일스톤 · 앞 단계 수용 기준을 통과한 뒤 다음으로)

| 단계 | 내용 | 수용 기준 |
|---|---|---|
| **M0** | 모델 pull 2건 · `.env` 의 `LANGSMITH_TRACING=true` · GPU 비우기 · 10주차 봇 끄기 | SPEC 2-2절 |
| **M1** | `config.py` · `faiss_io.py` · `build_index.py` (`--show` · `--check` · `--mode recursive`) | 4-10절 — Q&A 정확히 100 · FAQ 36 |
| **M2** | `rag_backend.py` — 터미널에서 6문항 6/6 · trace 확인 | 5-7절 |
| **M3** | `slack_rag_bot.py` · 슬랙 왕복 · VRAM 재측정 → **11/27 중간 점검 전까지** | 6-5절 |
| **M4** | `questions.py`(30문항) · `evaluate.py` · E1~E4 실험 → 기본값 채택 · CONTEXT 부록 D · E | 7-4절 |
| **M5** | README 5 · 6번 · 문서 갱신 · LangSmith 캡처 7장 → **12/4 제출** | 8-2절 · 9장 |

**사용자가 직접 해야 하는 일** (그 차례에 멈추고 요청): 모델 pull · `.env` 변경 승인 / `--show qa_case` 100줄 눈 확인 / 슬랙에서 질문 · 화면 캡처 / LangSmith 캡처 / 커밋 · 푸시 승인

## 사용자 확인이 필요한 미결 사항 (SPEC 13장)

채점 문서(README · CONTEXT)라 임의로 고치지 않고 남겨 둔 것입니다. 구현하며 문서를 갱신할 때(SPEC 9-3절) 함께 정리합니다.

1. **LangSmith 프로젝트 이름 위치** — `config.py`(SPEC) ↔ 루트 `.env`(README 체크리스트 · CONTEXT «관측»)
2. **README 3번 «사용자의 질문이 외부 API 로 나가지 않고»** — LangSmith 추적을 켜면 질문 · 근거 · 답이 LangSmith 에 기록됨. «추론은 로컬 · 추적 기록은 LangSmith» 로 고쳐야 정확
3. **사례집 발행일** — CONTEXT «2026.05» ↔ PDF 판권 «2026년 3월 26일»
4. **CONTEXT 부록 C «마트 영수증» 행의 A.X 답** — 뒷부분이 첫 커밋부터 잘려 있음. M2 에서 `scratch_eval.py` 를 다시 돌려 채움
5. 구현 후 실측값으로 바꿀 숫자 — 품목사전 243 → 286 안팎 · FAQ 평균 113자 → 106자 · 본문 «재질 소절» → «쪽 단위 + `section`» · `material` 용도(필터 → 심어 둠)
6. README 그림과 CONTEXT 그림의 출처 예시가 서로 다름 → 실제 출력으로 통일

## 작업 규칙

- README · CONTEXT 의 숫자를 바꾸면 **두 문서를 같이** 고칠 것 (VRAM · 정답 수 등이 양쪽에 있음). SPEC 과 달라지면 SPEC 13장에 적을 것
- 새 숫자는 **실제로 돌려서** 얻은 것만 적을 것. 추정이면 «계산» 이라고 표시. 효과가 없었으면 없었다고 적을 것
- 한 번에 하나만 바꾸고 잴 것 (임베딩 · 분할 · 검색 전략 · 프롬프트)
- `11-06/` · `11-13/` 의 파일과 인덱스는 수정하지 말 것 (읽기 · 복사만)
- 토큰 · 키를 코드 · 로그 · 커밋 · 슬랙 메시지에 넣지 말 것. `.env` 내용을 출력하지 말 것. 68MB PDF 커밋 금지
- 커밋 · 푸시, 파일 삭제, `.env` 수정은 **사용자에게 확인받고** 할 것
- 커밋 메시지는 한국어, 기존 형식(`mini_project: …`, `week10: …`)을 따름
