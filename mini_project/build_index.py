"""[버릴지도 ①] 분리배출 PDF 2건으로 봇 전용 인덱스를 만든다

    data/*.pdf ─▶ ① 적재   PyPDFLoader — 1쪽 = Document 1개 (page 는 0부터 → +1)
               ─▶ ② 정리   머리말 · 쪽 번호 제거 (문서별 정규식) ★
               ─▶ ③ 분할   구역별 구조 단위 → 긴 것만 재귀 400/40 (2단 구성)
               ─▶ ④ 메타   source · page · year · doc_type · material · item · qa_date · section · chunk_id · splitter
               ─▶ ⑤ 임베딩 + 저장   KURE-v1 → FAISS → index_recycle/ (+ manifest.json)

  구역마다 «의미 단위» 가 달라서 splitter 하나로 통일하지 않는다.

    사례집 Q&A (6~46쪽)        1건 = 1청크        ← ★★ 날짜 순서대로 자르면 100건 중 24건이 틀린다
    가이드라인 FAQ (21~25쪽)   «Q :» 1개 = 1청크
    가이드라인 품목사전 (28~34쪽) 품목 1개 = 1청크
    가이드라인 본문 (3~20쪽)    쪽 단위 → 재귀 400/40

★ 이 PDF 들의 «파싱 난점» (1교시) 이 이 파일에 전부 들어 있다
  - 머리말: 가이드라인은 줄 **앞에 공백이 있는 꼴**이 절반 / 사례집은 원본 오탈자 «2026넌도» 가 35회
  - 2단 배치: 사례집은 메타(날짜 → 품목 라벨 → 번호)와 본문(질문 → 답)의 순서가 쪽 안에서 다르다
    → 품목 이름이 질문에 들어 있는지로 짝을 짓는다 (parse_qa_page)
  - 품목사전: 초성 줄 · 구분마크 줄 · 표 머리가 품목 사이에 섞여 뽑힌다

실행 (이 폴더에서):
    python build_index.py --show              # 임베딩 없이 요약표 + 구역별 표본 (즉시)
    python build_index.py --show qa_case      # 한 구역 전체를 한 줄씩 — 눈 확인용 (qa_case | faq | item_dict | guideline)
    python build_index.py --check             # 수용 기준을 assert 로 검사 (임베딩 없음 · 실패하면 종료 코드 1)
    python build_index.py                     # 인덱스 생성 → index_recycle/
    python build_index.py --mode recursive --out index_recursive   # 비교 기준(구조 분할 없이 재귀만) — 분할 A/B 용
"""

import config  # noqa: F401  ★ 맨 위 — LangSmith 프로젝트 이름을 라이브러리보다 먼저 정한다
from config import (  # noqa: E402
    CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR, DOCS, EMBED_MODEL, HERE, KO_SEPARATORS, MIN_BODY_CHARS, UNIT_MAX,
)

import argparse  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from difflib import SequenceMatcher  # noqa: E402
from pathlib import Path  # noqa: E402

from langchain_community.document_loaders import PyPDFLoader  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402
from langsmith import traceable, tracing_context  # noqa: E402

from faiss_io import load_index, save_index  # noqa: E402  ← 한글 경로 대비책 (10주차 3교시)

(GUIDE_PDF, GUIDE_YEAR, _), (QA_PDF, QA_YEAR, _) = DOCS
DOC_TYPES = ("qa_case", "faq", "item_dict", "guideline")
RECURSIVE = f"recursive-{CHUNK_SIZE}-{CHUNK_OVERLAP}"

# ── 구역 지도 (쪽 번호는 1부터) ─────────────────────────────────────
BODY_PAGES = range(3, 21)       # 가이드라인 본문 1~7장
FAQ_PAGES = range(21, 26)       # 8장 앱 FAQ
ITEM_PAGES = range(28, 35)      # 부록 품목사전   (26 과태료 표 · 27 사전 이용법은 버린다)
QA_PAGES = range(6, 47)         # 사례집 — 장 구분쪽 12개 + Q&A 쪽 29개
QA_CHAPTERS = {                 # 장 이름 → 건수 (합계 100) — --check 가 대조한다
    "종이·종이컵": 10, "종이팩": 3, "무색페트병": 4, "플라스틱류": 10, "비닐류": 10, "발포합성수지": 4,
    "유리·유리병": 5, "금속류": 8, "의류·잡화": 7, "전기전자제품": 10, "음식물": 10, "기타": 19,
}

# ── ② 정리 규칙 — 머리말은 문서별로 따로 ★ ──────────────────────────
#   ⚠️ scratch_eval.py 의 HDR 을 쓰면 안 된다: 가이드라인 머리말 34줄 중 17줄이 남고(줄 앞 공백),
#      «숫자 1~2자리 줄» 삭제가 사례집의 사례 번호 줄까지 지운다 (번호는 Q&A 파서의 닻이다).
HDR_G = re.compile(r"^[ \t]*(?:재활용품 분리배출[ \t]*\d*|\d+[ \t]*재활용품 분리배출)[ \t]*$", re.M)
HDR_Q = re.compile(r"^[ \t]*(?:2026[넌년]도 내 손안의 분리배출 앱|Q&A 사례 100)[ \t]*$", re.M)
HDR_LEFT = re.compile(r"내 손안의 분리배출 앱|^\s*(?:재활용품 분리배출\s*\d*|\d+\s*재활용품 분리배출)\s*$", re.M)

# 구현 중 모은 부가 정보 — --show · --check 가 읽는다 (청크 metadata 에는 넣지 않는 것들)
REPORT: dict = {}


def _lines(text: str, header: re.Pattern) -> list[str]:
    """머리말을 지우고, 줄마다 앞뒤 공백을 떼고, 빈 줄을 버린다."""
    return [line.strip() for line in header.sub("", text).splitlines() if line.strip()]


def _summary(docs) -> dict:
    """LangSmith 에 청크를 통째로 올리지 않고 «몇 개 · 어떤 모양» 만 남긴다."""
    if not isinstance(docs, list) or not docs:
        return {"count": 0}
    lens = [len(d.page_content) for d in docs]
    return {
        "count": len(docs), "avg_len": sum(lens) // len(lens), "max_len": max(lens),
        "samples": [{"text": d.page_content[:100], "metadata": d.metadata} for d in docs[:3]],
    }


def _in_summary(inputs: dict) -> dict:
    return {k: (f"{len(v)} pages" if isinstance(v, list) else v) for k, v in inputs.items()}


def _traced(name: str):
    return traceable(name=name, process_inputs=_in_summary, process_outputs=lambda out: _summary(out))


# ── ① 적재 + ② 정리 ────────────────────────────────────────────────
def load_pdf(name: str) -> list[Document]:
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(
            f"PDF 가 없습니다: {path}\n"
            "  → 받는 법은 CLAUDE.md «문서 받기» (사례집은 68MB 라 저장소에 없습니다)"
        )
    return PyPDFLoader(str(path)).load()


@_traced("clean-pages")
def clean_pages(pages: list[Document], kind: str) -> list[Document]:
    """쪽 범위를 고르고 머리말을 지운다. kind = body | faq | item | qa"""
    pick = {"body": BODY_PAGES, "faq": FAQ_PAGES, "item": ITEM_PAGES, "qa": QA_PAGES}[kind]
    header = HDR_Q if kind == "qa" else HDR_G
    out = []
    for doc in pages:
        page_no = doc.metadata.get("page", 0) + 1            # PyPDFLoader 는 0 부터 센다
        if page_no in pick:
            out.append(Document(page_content="\n".join(_lines(doc.page_content, header)),
                                metadata={"page": page_no}))
    return out


def _sub_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
                                          separators=KO_SEPARATORS)


def _unit(text: str, meta: dict, unit_name: str) -> list[Document]:
    """구조 단위 1개 → 청크. UNIT_MAX 를 넘을 때만 재귀로 다시 자른다 (splitter 에는 실제 적용된 것만 적는다)."""
    meta = {k: v for k, v in meta.items() if v not in (None, "")}     # ⚠️ 값이 없는 키는 넣지 않는다
    if len(text) <= UNIT_MAX:
        return [Document(page_content=text, metadata={**meta, "splitter": unit_name})]
    return [Document(page_content=piece, metadata={**meta, "splitter": f"{unit_name}→{RECURSIVE}"})
            for piece in _sub_splitter().split_text(text)]


# ── ③-1 사례집 Q&A — 1건 = 1청크 ★★ ────────────────────────────────
DATE = re.compile(r"(20\d\d-\d\d-\d\d)\s*$")
NUM = re.compile(r"^(\d{1,2})(?:\s+(\S.*))?$")
SENT_END = re.compile(r"[.?!]\s*$")
TOC_LINE = re.compile(r"^\d{2}\.\s*(\S.*)$")


def _norm(s):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", s or "")


def _lcs(a, b):
    """한글 · 영문 · 숫자만 남긴 뒤의 최장 공통 부분 문자열 길이."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b)).size


def _split_blocks(seg):
    """본문 구간 → [(질문, 답)]. «? 로 끝나는 줄» 이 질문의 끝이다."""
    groups = []
    for k, line in enumerate(seg):
        if line.endswith("?"):
            if groups and k == groups[-1][1] + 1:
                groups[-1][1] = k                      # 연달은 ? 줄은 한 질문
            else:
                groups.append([k, k])
    starts = []
    for a, b in groups:
        s = a
        while s > 0 and not SENT_END.search(seg[s - 1]):
            s -= 1                                     # 앞 줄이 문장 끝이 아니면 그 줄도 질문
        starts.append([s, b])
    if starts:
        starts[0][0] = 0                               # 구간 앞머리는 첫 질문에 붙인다 (11쪽)
    out = []
    for n, (s, b) in enumerate(starts):
        e = starts[n + 1][0] if n + 1 < len(starts) else len(seg)
        out.append((" ".join(seg[s:b + 1]), " ".join(seg[b + 1:e])))
    return out


def parse_qa_page(text, page_no, chapter, toc):
    """사례집 한 쪽 → ([사례 dict], chapter, 경고 목록).  (SPEC 4-4절 — 실제 PDF 에서 100건 · 경고 0 확인)

    2단 배치 때문에 메타(날짜 → 라벨 → 번호)와 본문(질문 → 답)의 순서가 쪽 안에서 다르다.
    그래서 «품목 이름이 질문에 들어 있는가» 로 짝을 짓는다 — 쪽당 최대 4건이라 순열을 전부 본다.
    """
    lines = [l.strip() for l in HDR_Q.sub("", text).splitlines() if l.strip()]
    lines = [l for k, l in enumerate(lines) if not (k < 2 and l == str(page_no))]     # 쪽 번호 줄
    if not any(DATE.search(l) for l in lines):                     # 날짜 없는 쪽 = 장 구분쪽이거나 버릴 쪽
        items = [m.group(1) for l in lines if (m := TOC_LINE.match(l))]
        if items and page_no in QA_PAGES:
            chapter = next(l for l in lines if not l.isdigit())
            toc[chapter] = items
        return [], chapter, []
    flat = []
    for l in lines:                                                # 줄 끝에 붙은 날짜 떼기 (11 · 13쪽)
        m = DATE.search(l)
        flat += [l[:m.start()].strip(), m.group(1)] if m and l != m.group(1) else [l]
    metas, segs, cur, i, warns = [], [], [], 0, []
    while i < len(flat):
        if DATE.fullmatch(flat[i]):
            label, j, num, tail = [], i + 1, None, None
            while j < len(flat) and j <= i + 5:
                if m := NUM.match(flat[j]):
                    num, tail = int(m.group(1)), m.group(2)        # 번호 뒤에 글이 붙으면 본문의 첫 줄 (31쪽)
                    break
                label.append(flat[j])
                j += 1
            if num is None:
                warns.append("사례 번호 없음")
                cur.append(flat[i])
                i += 1
                continue
            metas.append({"qa_date": flat[i], "label": " ".join(label), "num": num})
            if cur:
                segs.append(cur)
            cur = [tail] if tail else []
            i = j + 1
        else:
            cur.append(flat[i])
            i += 1
    if cur:
        segs.append(cur)
    qa = [x for seg in segs for x in _split_blocks(seg)]
    if len(qa) != len(metas):
        return [], chapter, warns + [f"Q&A {len(qa)} ≠ 메타 {len(metas)}"]   # → 이 쪽은 재귀로 fallback
    for m in metas:
        names = toc.get(chapter, [])
        # 라벨보다 목차를 우선 — 라벨은 줄이 쪼개지고 표기가 다른 것이 있다 (택배봉투 ↔ 택배 비닐)
        m["item"] = names[m["num"] - 1] if m["num"] <= len(names) else m["label"]

    def name(mi, s):
        return max(_lcs(metas[mi]["item"], s), _lcs(metas[mi]["label"], s))

    def score(p):
        return sum(10 * name(mi, qa[bi][0]) + name(mi, qa[bi][1]) for bi, mi in enumerate(p))

    best = max(itertools.permutations(range(len(metas))), key=score)   # 동점이면 문서 순서가 먼저
    return [{**metas[mi], "q": qa[bi][0], "a": qa[bi][1]} for bi, mi in enumerate(best)], chapter, warns


@_traced("split-qa-cases")
def split_qa_cases(pages: list[Document]) -> list[Document]:
    chunks, rows, warnings, fallback_pages = [], [], [], []
    chapter, toc = None, {}
    for doc in pages:
        page_no = doc.metadata["page"]
        cases, chapter, warns = parse_qa_page(doc.page_content, page_no, chapter, toc)
        warnings += [f"p.{page_no} {w}" for w in warns]
        base = {"source": QA_PDF, "page": page_no, "year": QA_YEAR, "doc_type": "qa_case", "material": chapter}
        if not cases and any(DATE.search(l) for l in doc.page_content.splitlines()):
            # 메타 수 ≠ Q&A 수 — 구조로 못 자른 쪽은 재귀로 떨어뜨린다 (인덱스는 만들어진다)
            fallback_pages.append(page_no)
            for piece in _sub_splitter().split_text(doc.page_content):
                chunks.append(Document(page_content=piece, metadata={**base, "splitter": RECURSIVE}))
            continue
        for c in sorted(cases, key=lambda c: c["num"]):
            # 품목 이름을 본문에도 넣는다 — 질문에 품목명이 안 나오는 사례가 있고, 검색에 걸리게 하려고
            text = f"품목: {c['item']}\nQ. {c['q']}\nA. {c['a']}"
            chunks += _unit(text, {**base, "item": c["item"], "qa_date": c["qa_date"]}, "qa-unit")
            rows.append({"page": page_no, "chapter": chapter, "num": c["num"], "item": c["item"],
                         "qa_date": c["qa_date"], "q": c["q"], "a": c["a"]})
    REPORT["qa"] = {"rows": rows, "warnings": warnings, "fallback_pages": fallback_pages, "toc": toc}
    return chunks


# ── ③-2 가이드라인 FAQ — «Q :» 1개 = 1청크 ──────────────────────────
FAQ_Q = re.compile(r"^Q\s*:")
FAQ_SUBTITLES = {"종이류", "종이팩", "유리병", "페트병", "플라스틱류", "스티로폼류", "비닐류", "기타"}


@_traced("split-faq")
def split_faq(pages: list[Document]) -> list[Document]:
    """재질 소제목은 쪽 맨 위에 몰려 뽑혀 문항과 줄이 안 맞는다 → material 을 넣지 않는다 (틀린 값보다 없는 값)."""
    chunks = []
    for doc in pages:                                   # 쪽을 넘는 문항 없음 (실측) — 쪽마다 닫는다
        cur: list[str] = []

        def flush():
            if cur:
                meta = {"source": GUIDE_PDF, "page": doc.metadata["page"], "year": GUIDE_YEAR, "doc_type": "faq"}
                chunks.extend(_unit("\n".join(cur), meta, "faq-unit"))

        for line in doc.page_content.splitlines():
            if re.sub(r"\s", "", line) in FAQ_SUBTITLES or line.startswith("08."):
                continue
            if FAQ_Q.match(line):
                flush()
                cur = [line]
            elif cur:
                cur.append(line)                        # «A :» · «Best) / Good) / Bad)» 줄이 답에 포함된다
        flush()
    return chunks


# ── ③-3 가이드라인 품목사전 — 품목 1개 = 1청크 ──────────────────────
INITIALS = set("가나다라마바사아자차카타파하")         # ⚠️ 한 글자 줄 전체가 아니다 — 낫 · 못 · 컵 … 은 품목
MARKS = ("종이 종이팩 금속캔 고철 유리병 플라스틱 비닐 발포합성 의류 가전제품 대형 음식물 유해 불연성 "
         "종량제 종량제봉투 전용함 전문시설 주의 재질별분리").split()
MARK_LINES = set(MARKS) | {a + b for a in MARKS for b in MARKS}       # «대  형대  형» 처럼 둘이 붙은 것
ITEM_END = re.compile(r"(배출|처리|가능|참고)(한다)?\.?$")
# 배출방법이 시작되는 어휘 — 그 앞까지가 품목 이름
METHOD_START = tuple(
    "종량제 쓰레기 대형폐기물 대형페기물 대형가전 폐가전제품 고철 종이류 종이팩 플라스틱 불연성 음식물류 "
    "전용수거함 전문처리시설 재질에 내부를 내용물을 의류 비닐로 비닐류 유리병류 크기에 다른 단, 모두 사용한 "
    "수거원이 기름에 구입처 폐식용유 분리하여 물에 금속캔 생선뼈는 -".split()
)
MATERIAL_RULES = [                                      # 배출방법 글에서 가장 먼저 나오는 키워드로
    (("종량제",), "종량제"),
    (("대형가전", "폐가전", "가전제품"), "폐가전제품"),
    (("대형폐기물", "대형페기물", "대형으로"), "대형폐기물"),
    (("고철",), "고철"),
    (("금속캔",), "금속캔"),
    (("종이팩",), "종이팩"),
    (("종이류",), "종이류"),
    (("플라스틱",), "플라스틱류"),
    (("비닐",), "비닐류"),
    (("유리병",), "유리병류"),
    (("불연성",), "불연성폐기물"),
    (("음식물",), "음식물"),
    (("의류",), "의류"),
    (("전용수거함", "폐식용유"), "전용수거함"),
    (("전문처리시설", "구입처", "중고센터", "판매처"), "전문시설"),
]
# 2단 배치로 이웃 항목의 글이 섞여 **뜻이 틀어진** 항목 — 인덱스에서 뺀다 (본문 부분 문자열)
ITEM_DROP = (
    "수거 대상품목이 아님 압력솥",            # 31쪽 — 앞 구절이 다른 항목의 글
    "수거 대상품목이 아님 전지",              # 32쪽
    "(여러재질이 섞인 경우 종량제 봉투로 배출) 장롱",   # 32쪽 — 두 항목이 합쳐짐
    "전기장판 대형폐기물로 배출(전기이불담요 포함) 전기밥솥",   # 32쪽
)


def item_name(text: str) -> str:
    """«나무젓가락 종량제봉투로 배출» → «나무젓가락». 배출방법 시작 어휘를 못 찾으면 빈 문자열."""
    tokens = text.split()
    for i in range(1, len(tokens)):
        if tokens[i].startswith(METHOD_START):
            return " ".join(tokens[:i])
    return ""


def item_material(method: str) -> str:
    hits = [(method.find(k), name) for keys, name in MATERIAL_RULES for k in keys if k in method]
    return min(hits)[1] if hits else ""


@_traced("split-item-dict")
def split_item_dict(pages: list[Document]) -> list[Document]:
    chunks, dropped, icon_only = [], [], 0
    for doc in pages:
        keep = []
        for line in doc.page_content.splitlines():
            bare = re.sub(r"\s", "", line)
            if line.startswith("※") or bare == "품목구분배출방법" or bare in MARK_LINES:
                continue                                # 주석 · 표 머리 · 구분마크 줄
            if len(bare) == 1 and bare in INITIALS:
                continue                                # 초성 줄
            keep.append(line)
        cur: list[str] = []
        for k, line in enumerate(keep):
            nxt = keep[k + 1] if k + 1 < len(keep) else ""
            if line.startswith("대상"):
                # «국자 / 대상 : 금속 국자 …» — 배출 방법이 아이콘뿐이라 글이 없다 → 품목 이름째 버린다
                icon_only += bool(cur)
                cur = []
                continue
            cur.append(line)
            if ITEM_END.search(line) and not nxt.startswith("-"):
                text = " ".join(cur)                    # 두 줄짜리 품목명이 자연히 이어진다
                cur = []
                if any(bad in text for bad in ITEM_DROP):
                    dropped.append(f"p.{doc.metadata['page']} {text}")
                    continue
                name = item_name(text)
                meta = {"source": GUIDE_PDF, "page": doc.metadata["page"], "year": GUIDE_YEAR,
                        "doc_type": "item_dict", "item": name,
                        "material": item_material(text[len(name):] if name else text)}
                chunks += _unit(text, meta, "item-line")    # ⚠️ 30자 필터 금지 — 평균 20자
    REPORT["item"] = {"dropped": dropped, "icon_only": icon_only}
    return chunks


# ── ③-4 가이드라인 본문 — 쪽 단위 → 재귀 ────────────────────────────
# 그림 속 글자 조각 때문에 소절 제목 줄을 규칙으로 못 잡는다 → 목차로 확인한 «쪽 → 소절» 표
PAGE_SECTION = {   # 쪽: (section, material — 한 쪽에 재질이 둘 이상이면 넣지 않는다)
    3: ("1. 분리배출 왜 해야 하나요?", ""), 4: ("1. 분리배출 왜 해야 하나요?", ""),
    5: ("2. 생활계 폐기물 분류 및 배출 방법", ""),
    6: ("3.1 종이류", "종이류"), 7: ("3.2 종이팩·종이컵", "종이팩"),
    8: ("3.3 금속캔 · 3.4 고철류", ""), 9: ("3.5 유리병류", "유리병류"),
    10: ("3.6 페트병 · 3.7 플라스틱류 · 3.8 비닐류", ""),
    11: ("3.9 발포합성수지(스티로폼)", "발포합성수지"), 12: ("3.10 기타", ""),
    13: ("3.11 재활용품 분리배출 세부요령", ""), 14: ("3.11 재활용품 분리배출 세부요령", ""),
    15: ("3.11 재활용품 분리배출 세부요령", ""),
    16: ("4. 폐가전제품 및 대형폐기물", ""),
    17: ("5. 음식물류폐기물", "음식물"), 18: ("5. 음식물류폐기물", "음식물"),
    19: ("6. 유해폐기물", "유해폐기물"),
    20: ("7. 가연성폐기물 및 불연성폐기물 / 기타폐기물", ""),
}


@_traced("split-guideline")
def split_guideline(pages: list[Document]) -> list[Document]:
    chunks = []
    for doc in pages:
        section, material = PAGE_SECTION[doc.metadata["page"]]
        meta = {"source": GUIDE_PDF, "page": doc.metadata["page"], "year": GUIDE_YEAR,
                "doc_type": "guideline", "section": section, "material": material}
        meta = {k: v for k, v in meta.items() if v != ""}
        for piece in _sub_splitter().split_text(doc.page_content):
            if len(piece) >= MIN_BODY_CHARS:
                chunks.append(Document(page_content=piece, metadata={**meta, "splitter": f"page→{RECURSIVE}"}))
    return chunks


# ── 비교 기준 — 구조 분할 없이 재귀만 (분할 A/B 의 «A») ─────────────
def split_recursive_only(guide: list[Document], qa: list[Document]) -> list[Document]:
    """분할 **하나만** 다르게: 구조 모드와 같은 쪽 · 같은 정리 → 쪽마다 재귀 400/40."""
    chunks = []
    plan = [(clean_pages(guide, "body"), GUIDE_PDF, GUIDE_YEAR, "guideline"),
            (clean_pages(guide, "faq"), GUIDE_PDF, GUIDE_YEAR, "faq"),
            (clean_pages(guide, "item"), GUIDE_PDF, GUIDE_YEAR, "item_dict"),
            (clean_pages(qa, "qa"), QA_PDF, QA_YEAR, "qa_case")]
    for pages, source, year, doc_type in plan:
        for doc in pages:
            page_no = doc.metadata["page"]
            lines = doc.page_content.splitlines()
            if doc_type == "qa_case":
                if not any(DATE.search(l) for l in lines):
                    continue                                        # 장 구분쪽 — 구조 모드도 버린다
                lines = [l for k, l in enumerate(lines) if not (k < 2 and l == str(page_no))]
            for piece in _sub_splitter().split_text("\n".join(lines)):
                if len(piece) >= MIN_BODY_CHARS:
                    chunks.append(Document(page_content=piece, metadata={
                        "source": source, "page": page_no, "year": year, "doc_type": doc_type,
                        "splitter": RECURSIVE}))
    return chunks


# ── ④ 묶기 ─────────────────────────────────────────────────────────
@_traced("build-chunks")
def build_chunks(mode: str = "structure") -> list[Document]:
    """① 적재 → ② 정리 → ③ 구역별 분할 → ④ chunk_id 부여.  mode = structure | recursive"""
    guide, qa = load_pdf(GUIDE_PDF), load_pdf(QA_PDF)                # ①
    if mode == "recursive":
        chunks = split_recursive_only(guide, qa)
    else:
        chunks = (split_guideline(clean_pages(guide, "body"))        # ②③
                  + split_faq(clean_pages(guide, "faq"))
                  + split_item_dict(clean_pages(guide, "item"))
                  + split_qa_cases(clean_pages(qa, "qa")))
    for i, chunk in enumerate(chunks):                               # ④
        chunk.metadata["chunk_id"] = i
    return chunks


# ── 보기 · 검사 ────────────────────────────────────────────────────
def stats(chunks: list[Document]) -> dict:
    out = {}
    for t in DOC_TYPES:
        lens = [len(c.page_content) for c in chunks if c.metadata["doc_type"] == t]
        out[t] = {"count": len(lens), "avg": round(sum(lens) / len(lens)) if lens else 0,
                  "max": max(lens, default=0)}
    return out


def print_summary(chunks: list[Document], mode: str) -> None:
    lens = [len(c.page_content) for c in chunks]
    print(f"분할 방식 : {mode}")
    print(f"{'구역':<10} {'청크':>5} {'평균':>6} {'최대':>6}")
    for t, s in stats(chunks).items():
        print(f"{t:<10} {s['count']:>5} {s['avg']:>5}자 {s['max']:>5}자")
    print(f"{'합계':<10} {len(chunks):>5} {sum(lens) // len(lens):>5}자 {max(lens):>5}자")
    print("splitter  :", dict(Counter(c.metadata["splitter"] for c in chunks)))
    qa, item = REPORT.get("qa"), REPORT.get("item")
    if qa:
        print(f"사례집    : 경고 {len(qa['warnings'])}건 · fallback 쪽 {qa['fallback_pages'] or '없음'}")
        for w in qa["warnings"]:
            print("   ⚠️", w)
    if item:
        print(f"품목사전  : 아이콘뿐이라 버린 품목 묶음 {item['icon_only']} · ITEM_DROP 제외 {len(item['dropped'])}건")
        for d in item["dropped"]:
            print("   ✂", d)


def show(chunks: list[Document], which: str | None) -> None:
    if which is None:                                   # 구역별 표본 3개
        for t in DOC_TYPES:
            print(f"\n── {t} ──")
            for c in [c for c in chunks if c.metadata["doc_type"] == t][:3]:
                print("  ", c.metadata)
                print("     ", c.page_content[:150].replace("\n", " / "))
        return
    if which == "qa_case" and REPORT.get("qa"):         # 100줄 — 품목과 질문이 맞는지 눈으로 본다 ★
        print("\n쪽 · 번호 · 품목 · 날짜 · 질문 → 답")
        for r in REPORT["qa"]["rows"]:
            print(f"p.{r['page']:<2} #{r['num']:<2} {r['item']:<14} {r['qa_date']}  {r['q'][:40]} → {r['a'][:25]}")
        return
    for c in chunks:
        if c.metadata["doc_type"] == which:
            m = c.metadata
            tag = " · ".join(str(m[k]) for k in ("item", "material", "section") if k in m)
            print(f"p.{m['page']:<2} [{tag}] {c.page_content.replace(chr(10), ' / ')[:110]}")


def check(chunks: list[Document]) -> list[str]:
    """수용 기준(SPEC 4-10절) 중 기계로 볼 수 있는 것. 실패한 항목의 설명 목록을 돌려준다."""
    fails: list[str] = []

    def expect(ok: bool, what: str) -> None:
        print(("  ✅ " if ok else "  ❌ ") + what)
        if not ok:
            fails.append(what)

    s, qa, item = stats(chunks), REPORT["qa"], REPORT["item"]
    expect(s["qa_case"]["count"] == 100, f"사례집 Q&A 정확히 100건 (지금 {s['qa_case']['count']})")
    by_chapter: dict[str, list[int]] = {}
    for r in qa["rows"]:
        by_chapter.setdefault(r["chapter"], []).append(r["num"])
    expect({k: len(v) for k, v in by_chapter.items()} == QA_CHAPTERS, "장별 건수가 목차와 일치 (12개 장)")
    expect(all(sorted(v) == list(range(1, len(v) + 1)) for v in by_chapter.values()), "장마다 번호가 1..n 으로 빠짐없이")
    expect(not qa["fallback_pages"] and not qa["warnings"], "사례집 fallback 0쪽 · 경고 0건")
    faq = [c for c in chunks if c.metadata["doc_type"] == "faq"]
    expect(len(faq) == 36, f"FAQ 정확히 36건 (지금 {len(faq)})")
    expect(all(re.search(r"^A\s*:", c.page_content, re.M) for c in faq), "모든 FAQ 단위에 «A :» 줄이 있음")
    expect(s["item_dict"]["count"] >= 270, f"품목사전 270건 이상 (지금 {s['item_dict']['count']})")
    expect(len(item["dropped"]) == len(ITEM_DROP), f"ITEM_DROP {len(ITEM_DROP)}건이 모두 걸림 (지금 {len(item['dropped'])})")
    expect(s["guideline"]["count"] >= 30, f"가이드라인 본문 30건 이상 (지금 {s['guideline']['count']})")
    need = ("source", "page", "year", "doc_type", "chunk_id", "splitter")
    expect(all(all(k in c.metadata for k in need) for c in chunks), "모든 청크에 필수 키 6개")
    expect(all(type(c.metadata["year"]) is int and type(c.metadata["page"]) is int for c in chunks),
           "year · page 가 int")
    expect(all(v not in (None, "") for c in chunks for v in c.metadata.values()), "metadata 에 None · 빈 문자열 없음")
    expect([c.metadata["chunk_id"] for c in chunks] == list(range(len(chunks))), "chunk_id 가 0부터 차례로")
    expect(not any(HDR_LEFT.search(c.page_content) for c in chunks), "머리말이 남은 청크 0개")
    expect(all(c.page_content.startswith("품목: ") and "\nQ. " in c.page_content and "\nA. " in c.page_content
               for c in chunks if c.metadata["splitter"] == "qa-unit"), "Q&A 청크가 «품목 / Q. / A.» 꼴")
    return fails


# ── ⑤ 임베딩 + 저장 ────────────────────────────────────────────────
def save(chunks: list[Document], out_dir: Path, mode: str) -> None:
    from langchain_community.vectorstores import FAISS
    from langchain_core.tracers.langchain import wait_for_all_tracers
    from langchain_ollama import OllamaEmbeddings

    emb = OllamaEmbeddings(model=EMBED_MODEL)
    print(f"\n임베딩  : {EMBED_MODEL} — {len(chunks)}청크, 잠시 걸립니다…")
    start = time.perf_counter()
    try:
        store = FAISS.from_documents(chunks, emb)       # ★ from_texts 가 아니다 — metadata 를 지킨다
    except Exception as e:
        raise SystemExit(
            f"임베딩 실패 — {type(e).__name__}: {e}\n"
            f"  → ollama 가 켜져 있나?  모델이 있나?  ollama pull {EMBED_MODEL}"
        )
    how = save_index(store, out_dir)
    # ★ qwen3-embedding 과 KURE-v1 은 둘 다 1024차원 — 모델이 달라도 오류 없이 엉뚱한 결과가 나온다.
    #    읽는 쪽(rag_backend.get_store)이 이 파일의 embed_model 을 대조한다.
    manifest = {
        "embed_model": EMBED_MODEL, "mode": mode, "chunks": len(chunks),
        "by_doc_type": {t: s["count"] for t, s in stats(chunks).items()},
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 저장 : {out_dir}  (방식: {how} · {time.perf_counter() - start:.1f}초)")

    hit = load_index(out_dir, emb).similarity_search("선글라스 버리는 법", k=1)[0]
    print(f"   되읽기 확인: {hit.metadata.get('item', '?')} p.{hit.metadata.get('page')} | "
          f"{hit.page_content[:50].replace(chr(10), ' ')}…")
    wait_for_all_tracers()                              # trace 가 올라갈 시간을 준다
    print("\n다음:  python rag_backend.py 검색 \"뽁뽁이\"   →   python slack_rag_bot.py")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="분리배출 PDF 2건 → FAISS 인덱스")
    ap.add_argument("--show", nargs="?", const="", choices=("", *DOC_TYPES), help="임베딩 없이 청크를 본다")
    ap.add_argument("--check", action="store_true", help="수용 기준을 검사한다 (임베딩 없음)")
    ap.add_argument("--mode", choices=("structure", "recursive"), default="structure")
    ap.add_argument("--out", default=None, help="저장할 폴더 이름 (mini_project/ 아래 · index 로 시작)")
    args = ap.parse_args()
    dry_run = args.show is not None or args.check

    # 보기 · 검사는 추적에 올리지 않는다 — LangSmith 에는 «실제로 인덱스를 만든» 실행만 남긴다
    with tracing_context(enabled=False) if dry_run else tracing_context():
        chunks = build_chunks(args.mode)
    print_summary(chunks, args.mode)

    if args.check:
        if args.mode != "structure":
            raise SystemExit("--check 는 구조 분할(--mode structure)에만 씁니다.")
        print("\n── 수용 기준 검사 ──")
        fails = check(chunks)
        print(f"\n{'✅ 모두 통과' if not fails else f'❌ {len(fails)}건 실패'}")
        if fails:
            raise SystemExit(1)
    if args.show is not None:
        show(chunks, args.show or None)
    if dry_run:
        return

    out_name = args.out or (config.INDEX_DIR.name if args.mode == "structure" else "index_recursive")
    if not out_name.startswith("index"):
        raise SystemExit("--out 은 index 로 시작해야 합니다 (.gitignore 의 mini_project/index*/ 에 걸리게).")
    save(chunks, HERE / out_name, args.mode)


if __name__ == "__main__":
    main()
