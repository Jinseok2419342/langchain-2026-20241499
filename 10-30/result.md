# tool_flow.py
python tool_flow.py
```
(venv) 
USER@102-09 MINGW64 ~/Desktop/최신인공/langchain_20241499/10-30 (main)
$ python tool_flow.py
질문      : 357 곱하기 4891은? 그리고 지금 몇 시야?
최종 답변 : 357를 4891로 곱한 결과는 1746087입니다.

현재 समय은 2026년 10월 30일 11시 45분 29초입니다.
```


python tool_flow.py -v
```
(venv) 
USER@102-09 MINGW64 ~/Desktop/최신인공/langchain_20241499/10-30 (main)
$ python tool_flow.py -v
모델: llama3.2:3b

── 모델이 보는 것 (함수 본문은 안 보인다) ★★ ──────────
  name        : multiply
  description : 두 정수를 곱한다. 정확한 곱셈이 필요할 때 사용한다.
  args        : {'a': {'title': 'A', 'type': 'integer'}, 'b': {'title': 'B', 'type': 'integer'}}

  name        : get_time
  description : 지정한 시간대의 현재 시각을 문자열로 반환한다.
  args        : {'timezone': {'default': 'Asia/Seoul', 'title': 'Timezone', 'type': 'string'}}

  ★★ 독스트링이 곧 프롬프트입니다.
        5주차 Field(description=...) 과 같은 발상입니다.

          """도시 이름을 받아 현재 날씨를 조회한다."""   ✅ 언제 쓰는지 명확
          """날씨 함수."""                             ❌ 모델이 못 고릅니다

============================================================ 

질문      : 357 곱하기 4891은? 그리고 지금 몇 시야?
content   : ''   ← 비어 있다! ★
tool_calls: [{'name': 'multiply', 'args': {'a': 357, 'b': 4891}, 'id': '45707092-e10e-4283-af18-c6f852ab3670', 'type': 'tool_call'}, {'name': 'get_time', 'args': {'timezone': 'Asia/Seoul'}, 'id': '2951b630-0754-44bd-adf2-c148c9b4e5a1','type': 'tool_call'}]

── ③ 실행 주체는 우리 코드입니다 (아래 로그는 우리가 찍은 것) ★★ ──
  실행 multiply({'a': 357, 'b': 4891}) → 1746087
    args 만 넘기면 : 1746087          ← 파이썬 값
    call 을 넘기면 : ToolMessage(content='1746087', tool_call_id='45707092-e10e-4283-af18-c6f852ab3670')
  실행 get_time({'timezone': 'Asia/Seoul'}) → 2026-10-30 11:47:00
    args 만 넘기면 : '2026-10-30 11:47:00'          ← 파이썬 값
    call 을 넘기면 : ToolMessage(content='2026-10-30 11:47:00', tool_call_id='2951b630-0754-44bd-adf2-c148c9b4e5a1')

messages 길이: 5  ← 대화 이력이 쌓인다 (5주차 MessagesPlaceholder 의 자리)
최종 답변 : 357를 4891로 곱한 결과는 1746087입니다.

현재 समय은 2026년 10월 30일 11시 47분입니다.

============================================================

관찰 포인트 ★

  1차 응답의 content 가 빈 문자열
        → "모델이 답을 안 했습니다. 도구를 달라고 한 겁니다"
  tool_calls 가 2개
        → 질문 하나에 도구 두 개를 요청할 수 있다
  함수 실행 로그
        → 우리 코드가 찍은 로그. 실행 주체가 우리임을 확인 ★★
  최종 답변의 계산이 정확
        → 1주차에서 틀렸던 계산이 맞게 나온다 (2교시 «1주차의 ✗ ③»)
          (LLM 은 계산기가 아니라 '다음 토큰 예측기' 였습니다)

  ⚠️ 도구가 또 필요하면 우리가 또 돌려야 합니다.
     → 13주차 ToolNode 가 이 for 문을 대신합니다. ★

============================================================
```

<br><br><br>

# tool 추가(tool_flow.py에)
글자 수 세기(count_letter) tool 추가
```
@tool
def count_letter(word: str, letter: str) -> int:
    """단어(word) 안에 특정 글자(letter)가 몇 번 나오는지 센다. 글자 수를 정확히 세야 할 때 사용한다."""
    print(f"    [우리 코드] count_letter 실행: word={word!r}, letter={letter!r}")
    return word.lower().count(letter.lower())
```

코드에 툴 추가 `TOOLS = {t.name: t for t in [multiply, get_time, count_letter]}` 하고서   
main에 질문도 변경 `question = "'banana' 안에 'a'가 몇 번 나오는지 세어줘."`

답변 `python tool_flow.py`
```
(venv) 
USER@102-09 MINGW64 ~/Desktop/최신인공/langchain_20241499/10-30 (main)
$ python tool_flow.py
질문      : 'banana' 안에 'a'가 몇 번 나오는지 세어줘.
    [우리 코드] count_letter 실행: word='banana', letter='a'
최종 답변 : 'banana' 안에 'a'가 3 번 나오는 거예요.
```