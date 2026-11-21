# FAQ 에이전트 연결

라우터의 `route_question(question, client)`은 원래 질문과 OpenAI 클라이언트를 받아 `routes`(경로 목록)와 `etf_name`(상품명 또는 `"none"`)을 반환합니다. FAQ 경로가 포함되면 원래 질문을 `faq_agent.run_faq_agent`에 전달합니다.

```python
from faq_agent import run_faq_agent
from orchestrator import route_question

# client는 팀 라우터에서 사용 중인 OpenAI 클라이언트입니다.
question = "ETF와 주식은 어떻게 달라?"
route = route_question(question, client)
if "faq" in route["routes"]:
    faq_response = run_faq_agent(question)
    # faq_response를 서비스의 최종 응답에 합칩니다.
```

`run_faq_agent(question)`은 앞뒤 공백을 제외하고 1~1000자인 질문 문자열을 받습니다. 내부에서 `search_faq.invoke({"user_question": question})`을 호출하고, 도구가 반환한 JSON 문자열을 파이썬 딕셔너리로 변환합니다.

| 키 | 타입 | 내용 |
|---|---|---|
| `success` | `bool` | FAQ 검색 결과가 있으면 `True` |
| `message` | `str` | 성공, 검색 결과 없음, 입력 오류 또는 검색 불가 안내 |
| `results` | `list[dict]` | 유사도순으로 최대 3개의 FAQ. 각 결과에 저장된 답변, 유사도, 출처 정보 포함 |
| `sources` | `list[dict]` | 결과의 출처 정보. 값이 있는 `faq_id`, `source_name`, `source_url`, `source_date`, `verified_at`를 포함 |

검색 결과가 없거나 오류가 발생하면 `success=False`이고 두 목록은 비어 있습니다. 날짜는 기존 도구가 반환한 ISO 형식 문자열을 사용합니다. 각 항목에는 실제 데이터에 있는 필드만 포함됩니다.

## Streamlit 상담 실행

VS Code에서 **터미널 → 새 터미널**을 열고, 프로젝트 가상환경에 기존 의존성이 설치되어 있으면 다음 명령으로 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

FAQ 목록은 기존 FAQ CSV를 다섯 가지 주제로 묶어 보여줍니다. 답변과 관련 FAQ는 PostgreSQL에 저장된 FAQ 벡터 검색 결과를 사용합니다. 선택한 FAQ는 바로 검색하고, 자유 질문은 `consultation.consult`에서 기존 라우터를 호출합니다. `include_product=True` 옵션으로 단일 상품 조회와 비교 미지원 안내를 추가합니다. 기존 두 인자 호출은 기존 경로 목록과 상품명 범위를 사용합니다.

자료가 있으면 설명 모델에는 질문, 선택한 설명 수준, 조회에 성공한 자료가 전달됩니다. 시세는 공공데이터의 자료 기준일 가격입니다. 사용 가능한 공시 원문과 출처 링크는 화면의 참조 자료 영역에 표시됩니다.

## 테스트

프로젝트 의존성이 설치된 환경에서 아래 명령을 실행합니다.

```powershell
python -m unittest discover -s tests -p test_faq_agent.py -v
python -m unittest discover -s tests -p test_consultation.py -v
```

이 테스트는 라우터의 OpenAI 응답과 FAQ의 외부 호출을 테스트용 값으로 대체합니다.

실제 연결 테스트에는 유효한 OpenAI 설정과 FAQ 데이터 및 임베딩이 준비된 PostgreSQL/pgvector가 필요합니다. 알려진 FAQ 질문 하나를 검색합니다.

```powershell
$env:FAQ_RUN_LIVE_TESTS = "1"
try {
    python -m unittest discover -s tests -p test_faq_agent_live.py -v
} finally {
    Remove-Item Env:FAQ_RUN_LIVE_TESTS
}
```
