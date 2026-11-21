# ETF AI 상담센터

> **사용자 질문을 분석하고 ETF 상품 DB·FAQ·시세·공시 자료를 조회해 출처와 기준일이 포함된 답변을 제공하는 AI 에이전트 챗봇**

코멘토 AI 에이전트 개발 부트캠프 2주차 개인 프로토타입입니다.  
고객사 내부 자료는 별도로 제공받지 않았으며, **공개 API와 공개 자료 기반 샘플 데이터**로 기능과 데이터 흐름을 구현했습니다.

---

## 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 프로젝트명 | ETF AI 상담센터 |
| 개발자 | 조병관 |
| 목적 | ETF 입문 질문과 상품정보 질문에 근거 있는 답변 제공 |
| 주요 사용자 | ETF 개념과 상품정보를 확인하려는 투자자 |
| 화면 | Streamlit 웹 챗봇 |
| AI 프레임워크 | LangChain |
| LLM | OpenAI API (`gpt-5.4-mini`) |
| 데이터 저장 | CSV 원본 + PostgreSQL (pgvector) |
| 외부 데이터 | 금융위원회 ETF 시세 API, DART Open API |

### 핵심 원칙

- 수치에는 가능한 경우 **출처와 자료 기준일**을 함께 표시합니다.
- 조회되지 않은 가격·수익률·공시 내용은 만들어내지 않습니다.
- 기준일 종가를 오늘의 실시간 가격으로 표현하지 않습니다.
- 공시 제목만으로 구체적인 변경 내용을 단정하지 않습니다.
- 공개 자료 기반 프로토타입을 고객사 내부 DB 연동 서비스로 표현하지 않습니다.
- 특정 상품의 매수·매도를 추천하지 않습니다.

---

## 구현 기능

| 기능 | 상태 | 설명 |
| --- | --- | --- |
| Streamlit 챗봇 화면 | 구현 완료 | FAQ 검색·카테고리 목록, 직접 질문 입력, 대화 화면 제공 |
| 설명 수준 맞춤 | 구현 완료 | 입문·기본·심화 수준을 선택하고 질문에 적힌 수준도 우선 반영 |
| LangChain 오케스트레이터 | 구현 완료 | 질문을 분석해 필요한 전문 도구 선택 |
| ETF 상품 DB | 구현 완료 | 공개 자료 기반 ETF 상품 20개 저장 |
| FAQ DB | 구현 완료 | ETF 개념·가격·거래·비용·위험 FAQ 25개 저장 |
| ETF 상품 검색 | 구현 완료 | 상품명 또는 종목코드로 PostgreSQL 조회 |
| FAQ 검색 | 구현 완료 | 질문과 관련된 FAQ를 검색해 답변 근거로 활용 |
| ETF 시세 조회 | 구현 완료 | 공공데이터 API에서 최근 기준일 종가·NAV 조회 |
| DART 공시 조회 | 구현 완료 | 관련 공시 제목·접수일·원문 링크 제공 |
| 복합 도구 호출 | 구현 완료 | 시세와 공시를 함께 요청하면 두 도구 동시 호출 |
| 조회 결과 검증 | 구현 완료 | 상품명·날짜·수치·출처·공시 링크 검사 |
| 출처 표시 | 구현 완료 | 답변에 공식 자료 출처와 링크 표시 |
| 응답시간 기록 | 구현 완료 | 질문별 응답시간과 API 사용 여부를 MongoDB로 기록 |
| 독립 최종 검토 에이전트 | 추후 과제 | 최종 답변의 컴플라이언스와 출처를 별도 검토 |
| 뉴스 검색 | 구현 완료 | Google 뉴스 RSS로 최근 기사 제목·언론사·날짜·링크 제공 (API 키 불필요) |
| 클라우드 배포 | 추후 과제 | AWS 또는 Azure 배포 검토 |

---

### FAQ와 설명 수준

첫 화면에서 FAQ를 카테고리별로 확인하거나 질문·키워드로 검색할 수 있습니다.
목록에 원하는 내용이 없으면 하단 채팅 입력창에 질문을 직접 작성하면 됩니다.
사이드바에서 입문·기본·심화 설명 수준을 선택할 수 있으며, 질문에
“ETF를 처음 접하는 입문자”처럼 배경지식이 드러나면 해당 표현을 우선 반영합니다.
설명 수준은 답변의 어휘와 용어 풀이 방식만 조정하며, 근거가 없는 정보를
추정해 답하지 않는 원칙은 동일하게 적용됩니다.

---

## 시스템 구조

```text
사용자
  ↓
Streamlit 챗봇
  ↓
LangChain 오케스트레이터
  ├─ search_etf_product
  │    └─ PostgreSQL ETF 상품 DB 20개
  │
  ├─ search_faq
  │    └─ PostgreSQL FAQ DB 25개
  │
  ├─ get_etf_price
  │    └─ 금융위원회 ETF 시세 API
  │
  └─ search_etf_disclosure
       └─ DART Open API
  ↓
조회 결과 검증
  ↓
OpenAI 근거 기반 답변 생성
  ↓
출처·기준일·원문 링크 표시
```

### 질문 처리 예시

```text
질문: ETF와 주식은 어떻게 달라?
선택 도구: search_faq
```

```text
질문: TIGER 미국S&P500의 운용사와 기초지수를 알려줘
선택 도구: search_etf_product
```

```text
질문: KODEX 200의 최근 종가와 NAV를 알려줘
선택 도구: get_etf_price
```

```text
질문: KODEX 200의 종가와 관련 공시를 같이 알려줘
선택 도구: get_etf_price + search_etf_disclosure
```

---

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| 언어 | Python |
| 화면 | Streamlit |
| AI 프레임워크 | LangChain |
| LLM 연동 | `langchain-openai`, OpenAI Responses API |
| LLM 모델 | `gpt-5.4-mini` |
| 데이터베이스 | PostgreSQL + pgvector, MongoDB (응답 로그) |
| 원본 데이터 | CSV |
| ETF 시세 | 금융위원회 증권상품시세정보 API |
| 공시 | DART Open API |
| 환경변수 | `python-dotenv` |
| HTTP 통신 | `requests` |

CrewAI는 여러 역할의 에이전트가 순차적으로 협업하는 구조에 적합하지만, 이번 프로토타입은 하나의 오케스트레이터가 여러 조회 도구를 선택하는 구조이므로 LangChain을 사용했습니다.

---

## 프로젝트 구조

```text
eft_chatbot_demo/
├─ app.py                    # Streamlit 챗봇 화면
├─ langchain_agent.py        # LangChain 메인 오케스트레이터
├─ agent_tools.py            # ETF 상품 DB·FAQ 검색 도구
├─ api_tools.py              # ETF 시세·DART 공시 도구
├─ etf_api.py                # 금융위원회 ETF 시세 API 호출
├─ dart_api.py               # DART 공시 검색
├─ result_validator.py       # API 조회 결과 검증
├─ build_database.py         # CSV를 PostgreSQL에 적재
├─ requirements.txt          # 설치 라이브러리
├─ README.md
├─ .env.example              # API 키 입력 형식 예시
├─ .streamlit/
│  └─ config.toml            # Streamlit 화면 테마
├─ data/
│  ├─ etf_chatbot.db         # 이전 SQLite 데이터 (현재 앱에서 미사용)
│  └─ source/
│     ├─ etf_products.csv    # ETF 상품 20개 원본
│     └─ faq.csv             # ETF FAQ 25개 원본
└─ src/
   ├─ db/                   # PostgreSQL·MongoDB 공통 연결
   └─ services/request_logger.py # MongoDB 응답 로그 저장
```

다음 파일과 폴더는 보안과 용량 문제로 공유·제출하지 않습니다.

```text
.env
.venv/
__pycache__/
*.pyc
logs/
```

---

## 데이터 구성

### ETF 상품 DB

공개 상품정보를 기준으로 ETF 20개를 구성했습니다.

주요 필드:

- 종목코드
- 상품명
- 운용사
- 자산 유형
- 기초지수
- 총보수
- 위험등급
- 상장일
- 주요 구성종목
- 자료 출처
- 자료 기준일 또는 확인일

확인하지 않은 항목은 추측해서 채우지 않고 빈 값으로 유지합니다.

### FAQ DB

한국거래소와 전국투자자교육협의회 등 공개 자료를 참고해 FAQ 25개를 구성했습니다.

주요 범위:

- ETF 기본 개념
- 주식·일반 펀드와의 차이
- NAV·괴리율·추적오차
- 거래 방법과 LP
- 총보수와 분배금
- 환율 위험
- 레버리지·인버스 상품
- 공시 확인 방법

FAQ는 OpenAI `text-embedding-3-small`(1,536차원)과 PostgreSQL pgvector로 의미 기반 검색을 수행합니다.
상품코드·상품명 조회는 정확한 SQL 검색을 유지합니다. 상품 벡터도 저장하지만 현재 상품 조회 도구에서는 사용하지 않습니다.
첫 사용과 CSV 변경 후에는 아래 임베딩 생성 명령을 실행해야 합니다.

---

## 설치 및 실행

### Docker로 로컬 PostgreSQL / MongoDB 실행

Docker Desktop을 실행한 뒤 프로젝트 루트에서 다음 명령으로 두 DB를 시작합니다.

```powershell
docker compose up -d --wait
```

기본 접속 포트는 PostgreSQL `5432`, MongoDB `27017`입니다.
계정, 환경변수, 종료 및 초기화 방법은 [로컬 DB 실행 안내](docs/deployment.md)를 참고하세요.
현재 앱의 상품·FAQ 조회는 PostgreSQL, FAQ 벡터 검색은 pgvector, 응답 로그는 MongoDB를 사용합니다.

### 1. 프로젝트 폴더 이동

```powershell
cd C:\eft_chatbot_demo
```

### 2. 가상환경 생성

가상환경이 없는 경우에만 실행합니다.

```powershell
py -m venv .venv
```

### 3. 라이브러리 설치

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. 환경변수 설정

`.env.example`을 참고해 프로젝트 최상단에 `.env`를 만듭니다.

```text
OPENAI_API_KEY=발급받은_OpenAI_API_키
ETF_DATA_API_KEY=발급받은_공공데이터포털_키
DART_API_KEY=발급받은_DART_키
```

실제 API 키는 GitHub 또는 과제 제출 ZIP에 포함하지 않습니다.

### 5. PostgreSQL 데이터 적재

Docker DB와 스키마가 준비된 상태에서 CSV 원본을 PostgreSQL에 적재합니다.
기존 볼륨의 스키마 적용 방법은 [로컬 DB 실행 안내](docs/deployment.md)를 참고하세요.
앱은 적재한 PostgreSQL 데이터를 조회합니다. 이전 SQLite 파일은 갱신하지 않습니다.

```powershell
.\.venv\Scripts\python.exe build_database.py
```

정상적인 결과:

```text
PostgreSQL import complete
ETF: processed=20, changed=20, total=20
FAQ: processed=25, changed=25, total=25
```

### 6. LangChain 도구 확인

먼저 `.env`에 유효한 `OPENAI_API_KEY`를 설정한 뒤 상품·FAQ 임베딩을 생성합니다.
이 작업은 저장된 공개 상품·FAQ 텍스트를 OpenAI API로 전송하며 사용량에 따라 과금됩니다.

```powershell
.\.venv\Scripts\python.exe build_embeddings.py
```

재실행 시 변경 없는 문서는 API를 호출하지 않습니다. 기존 DB에서는
[벡터 검색 설정 안내](docs/deployment.md)의 마이그레이션을 먼저 적용하세요.
FAQ 검색 시에도 질문 임베딩을 생성하므로 OpenAI API 연결이 필요합니다.

```powershell
.\.venv\Scripts\python.exe check_agent_tools.py
```

뉴스 검색 도구는 API 키 없이 바로 확인할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe check_news.py
```

### 7. LangChain 오케스트레이터 확인

```powershell
.\.venv\Scripts\python.exe check_langchain_agent.py
```

### 8. Streamlit 챗봇 실행

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

터미널에 표시된 Local URL을 브라우저에서 엽니다.

```text
http://localhost:8501
```

포트가 이미 사용 중이면 다른 번호로 실행될 수 있으므로 터미널에 표시된 실제 주소를 확인합니다.

---

## 시연 질문

| 구분 | 질문 | 기대 결과 |
| --- | --- | --- |
| FAQ | `ETF와 주식은 어떻게 달라?` | FAQ DB 검색 후 출처가 포함된 설명 |
| 상품 DB | `TIGER 미국S&P500의 운용사와 기초지수를 알려줘` | 상품 DB에서 운용사·기초지수 조회 |
| 시세 | `KODEX 200의 최근 종가와 NAV를 알려줘` | 종가·NAV·자료 기준일·출처 표시 |
| 공시 | `KODEX 200의 관련 공시를 알려줘` | DART 공시 제목·날짜·원문 링크 표시 |
| 복합 질문 | `KODEX 200의 종가와 관련 공시를 같이 알려줘` | 시세 API와 DART 도구 동시 호출 |
| 지원하지 않는 상품 | `달토끼 우주여행 ETF의 종가 알려줘` | 확인되지 않은 가격을 만들지 않고 조회 불가 안내 |

답변 아래에는 실제 작동한 전문 도구가 표시됩니다.

```text
작동한 전문 도구: ETF 시세 API · DART 공시 API
```

---

## 응답시간 기록

챗봇 질문이 처리되면 MongoDB의 다음 컬렉션에 기록됩니다.

```text
etf_agent.request_logs
```

기록 항목:

- 응답 시각
- 사용자 질문
- 응답 시간
- 성공 또는 오류 결과
- ETF 시세 API 사용 여부
- 요청 ID, 사용 도구 목록, 처리 상태, 오류 유형

시각은 UTC 날짜 타입으로 저장합니다. 로그 저장에는 2초 제한을 적용하며,
실패해도 답변은 유지하고 화면에 알림을 표시합니다. 실패한 로그의 자동 재전송이나
기존 CSV 로그의 자동 이전은 수행하지 않습니다.

이 자료는 이후 응답속도 평가와 오류 분석에 활용할 수 있습니다.

---

## 주요 구현 과정

### 1단계: OpenAI 기반 기본 챗봇

먼저 Streamlit에서 사용자의 질문을 입력받고 OpenAI API가 ETF 개념을 설명하는 기본 챗봇을 구현했습니다.

이 단계에서는 LLM이 일반 지식을 바탕으로 답변했으며, ETF 상품 데이터나 공시 자료는 연결하지 않았습니다.

### 2단계: ETF 시세 API 연결

공공데이터포털의 금융위원회 증권상품시세정보 API를 연결했습니다.

구현 내용:

- ETF 상품명을 기준으로 API 검색
- 상품명이 정확히 일치하는 데이터만 선택
- 가장 최근 자료 기준일의 종가와 NAV 반환
- 종목코드·출처 URL 함께 저장
- 기준일 종가를 실시간 가격으로 표현하지 않도록 제한

### 3단계: DART 공시 연결

DART Open API에서 운용사 공시를 조회한 뒤 ETF 상품명이 제목에 일치하는 공시 후보를 검색하도록 구현했습니다.

구현 내용:

- 운용사 고유번호 조회
- 최근 조회 기간의 펀드공시 검색
- 상품명 정규화 후 제목 일치 여부 검사
- 접수일·공시 제목·원문 링크 제공
- 공시 제목만으로 변경 내용을 추측하지 않도록 제한

### 4단계: 조회 결과 검증

외부 API 결과를 바로 LLM에 전달하지 않고 검증 함수를 거치도록 구성했습니다.

검증 항목:

- 요청한 ETF 상품명과 조회 결과의 일치 여부
- 종목코드 존재 여부
- 자료 기준일 형식
- 종가와 NAV의 숫자 형식
- 공식 출처와 출처 URL 존재 여부
- DART 공시 원문 링크 형식
- 공시 제목과 ETF 상품명의 일치 여부

검증을 통과하지 못한 자료는 답변에서 제외합니다.

### 5단계: 공개 자료 기반 샘플 DB 구축

멘토 피드백을 반영해 고객사 내부 자료 대신 공개 자료 기반 샘플 DB를 만들었습니다.

```text
ETF 상품 데이터: 20개
FAQ 데이터: 25개
```

CSV를 원본으로 관리하고 `build_database.py`를 실행하면 PostgreSQL의 `etf_products`, `faq`에 추가·갱신합니다. 변경 없는 행과 CSV에 없는 기존 행은 유지합니다.

### 6단계: LangChain 도구 구성

기존 Python 조회 함수를 LangChain 도구로 등록했습니다.

```text
search_etf_product       ETF 상품 DB 조회
search_faq               ETF FAQ DB 검색
get_etf_price            ETF 시세 API 조회
search_etf_disclosure    DART 공시 조회
```

각 도구는 역할이 겹치지 않도록 설명을 구분했습니다. 예를 들어 총보수와 기초지수는 상품 DB가 담당하고 종가와 NAV는 시세 API가 담당합니다.

### 7단계: 오케스트레이터 에이전트 구현

LangChain `create_agent`를 이용해 메인 오케스트레이터를 구성했습니다.

오케스트레이터는 질문을 분석해 하나 또는 여러 도구를 선택합니다.

```text
ETF 일반 개념 질문 → FAQ 도구
상품 기본정보 질문 → 상품 DB 도구
종가·NAV 질문 → 시세 API 도구
공시 질문 → DART 도구
종가와 공시 복합 질문 → 시세 API + DART 도구
```

### 8단계: Streamlit 화면 통합

별도 시험 파일에서 검증한 LangChain 에이전트를 기존 Streamlit 화면에 연결했습니다.

답변 아래에는 실제로 호출된 도구가 표시됩니다.

```text
작동한 전문 도구: ETF 시세 API · DART 공시 API
```

이를 통해 발표 시 질문 분석과 전문 도구 연계 과정을 화면에서 확인할 수 있습니다.

---

## 테스트 결과

### ETF 상품 DB 조회

질문:

```text
TIGER 미국S&P500의 운용사와 기초지수를 알려줘
```

결과:

```text
호출 도구: search_etf_product
운용사: 미래에셋자산운용
기초지수: S&P 500
```

### FAQ 조회

질문:

```text
ETF와 주식은 어떻게 달라?
```

결과:

```text
호출 도구: search_faq
관련 FAQ와 출처를 이용해 ETF와 주식의 차이 설명
```

### ETF 시세 조회

질문:

```text
KODEX 200의 최근 종가와 NAV를 알려줘
```

확인한 테스트 결과:

```text
호출 도구: get_etf_price
자료 기준일: 2026-11-12
종가: 84,240원
NAV: 84,204.32원
```

위 값은 테스트 당시 공공데이터 API에서 조회한 자료이며 실시간 가격이 아닙니다.

### ETF 시세·공시 복합 조회

질문:

```text
KODEX 200의 종가와 관련 공시를 같이 알려줘
```

결과:

```text
호출 도구: get_etf_price + search_etf_disclosure
답변 내용: 종가·NAV·자료 기준일·공시 제목·DART 원문 링크
```

하나의 질문에 두 전문 도구가 동시에 호출되고 결과가 하나의 답변으로 정리되는 것을 확인했습니다.

### 예외 질문

질문:

```text
달토끼 우주여행 ETF의 종가를 알려줘
```

기대 동작:

- 존재가 확인되지 않은 ETF의 수치를 생성하지 않음
- 조회할 수 없는 상품임을 안내
- 확인 가능한 상품명 또는 종목코드를 다시 요청

---

## 현재 제한사항

- 고객사 내부 ETF 상품 DB와 FAQ·VOC 자료는 사용하지 않았습니다.
- 공개 자료를 이용해 만든 샘플 프로토타입입니다.
- ETF 상품 DB의 일부 항목은 공식 자료 확인 전까지 비어 있을 수 있습니다.
- ETF 시세는 실시간 가격이 아니라 공공데이터의 최근 자료 기준일 값입니다.
- DART 공시 검색은 현재 삼성자산운용의 일부 KODEX 상품을 중심으로 지원합니다.
- DART 결과는 공시 제목이 상품명과 일치하는 후보이며 공시 본문을 직접 요약하지 않습니다.
- 뉴스 검색은 Google 뉴스 RSS를 사용합니다.
  - 네이버 검색 API는 2026년 하반기부터 개발자센터 신규 신청이 막혀(네이버클라우드 API HUB로 이관, 결제수단 등록 필요) 대안으로 선택했습니다.
  - 비공식 피드라 형식이 바뀔 수 있으며, Google은 피드를 개인·비상업적 용도로만 허용합니다. 상용 서비스 전환 시 공식 뉴스 API로 교체해야 합니다.
  - 기사 본문은 가져오지 않고 제목·언론사·날짜·링크만 제공합니다. 최근 7일(없으면 30일) 기사 중 최대 5건을 보여줍니다.
  - 구글 뉴스 링크는 매우 길어 LLM이 옮겨 쓰다 망가뜨릴 수 있으므로, LLM에는 짧은 표시(`NEWS_LINK_…`)만 주고 답변 완성 후 코드가 진짜 링크로 바꿉니다.
  - 기사를 가져오는 부분은 `news_api.py`에만 있어, 다른 뉴스 API로 바꿀 때 이 파일만 수정하면 됩니다.
- FAQ 벡터 검색의 최소 유사도는 초기값 0.3이며, 실제 질문 평가를 통한 조정이 필요합니다.
- 별도의 독립 최종 검토 에이전트는 아직 구현하지 않았습니다.
- 클라우드 배포는 현재 범위에 포함하지 않았습니다.
- 실제 VOC 대신 사용할 평가용 예상 질문 데이터셋은 추후 구성할 예정입니다.

---

## 이후 확장 방향

### 데이터

- ETF 상품정보 자동 갱신
- FAQ 벡터 검색 평가 데이터 확장과 유사도 기준 조정
- 예상 고객 질문 기반 평가 데이터셋 구축
- 뉴스 제목·요약·링크 수집
- 데이터 출처와 기준일 품질 관리

### 에이전트

- 최종 답변 검토 에이전트 분리
- 출처·기준일·컴플라이언스 자동 검사
- 질문 문맥을 유지하는 대화 메모리 추가

### 운영

- API 실패 자동 재시도
- 오류 유형별 로그 기록
- LangSmith 또는 별도 모니터링 도구 검토
- AWS 또는 Azure 배포

---

## 과제 제출

제출 파일명:

```text
2주차_프로토타입_조병관.zip
```

제출 ZIP에는 실행에 필요한 코드·설정 예시·DB·CSV만 포함하고 다음 항목은 제외합니다.

```text
.env
.venv/
__pycache__/
*.pyc
logs/
.git/
```

---

## 참고 자료

- [금융위원회 증권상품시세정보](https://www.data.go.kr/data/15094806/openapi.do)
- [DART Open API](https://opendart.fss.or.kr/)
- [한국거래소 ETF 시장 안내](https://open.krx.co.kr/)
- [전국투자자교육협의회 ETF 스쿨](https://www.kcie.or.kr/elearning/etf/102/)
- [LangChain 공식 문서](https://docs.langchain.com/oss/python/learn)
- [Streamlit 공식 문서](https://docs.streamlit.io/)
