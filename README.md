# ETF AI 상담센터

> 사용자 질문을 분석하고 ETF 상품 DB·FAQ·시세·공시·뉴스를 조회하여 근거와 출처가 포함된 답변을 제공하는 AI 에이전트 챗봇

코멘토 AI 에이전트 개발 부트캠프 팀 프로젝트입니다.

2주차 개인 프로토타입을 바탕으로 팀 공용 개발 환경을 구성하고, ETF 정보·공시·뉴스 기능을 하나의 코드베이스로 통합했습니다.

고객사 내부 자료는 제공받지 않았으며, 공개 API와 공개 자료 기반 샘플 데이터로 구현했습니다.

**제출 기준일: 2026-11-21**

---

## 1. 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 프로젝트명 | ETF AI 상담센터 |
| 목적 | ETF 개념·상품정보·시세·공시·뉴스에 대한 근거 기반 질의응답 |
| 주요 사용자 | ETF 개념과 상품정보를 확인하려는 사용자 |
| 화면 | Streamlit |
| 프레임워크 | LangChain |
| LLM | OpenAI API, `gpt-5.4-mini` |
| 상품·FAQ 저장 | PostgreSQL |
| 벡터 검색 | PostgreSQL pgvector |
| 요청 로그 | MongoDB |
| 로컬 실행 환경 | Python 가상환경, Docker Compose |
| 배포 예정 플랫폼 | Microsoft Azure |
| GitHub | https://github.com/comento-aiagent-1/etf-ai-agent |

### 핵심 원칙

- 조회한 자료를 근거로 답변합니다.
- 가격·NAV에는 자료 기준일과 출처를 표시합니다.
- 기준일 종가를 실시간 가격으로 표현하지 않습니다.
- 확인되지 않은 상품정보와 수치를 추측하지 않습니다.
- 공시 제목만으로 구체적인 변경 내용을 단정하지 않습니다.
- 공개 자료 기반 샘플 서비스를 고객사 내부 DB 연동 서비스로 표현하지 않습니다.
- 특정 상품의 매수·매도를 추천하지 않습니다.

---

## 2. 팀 구성 및 역할

| 팀원 | 역할 | 주요 담당 업무 |
| --- | --- | --- |
| Streamlit 챗봇 화면 | 구현 완료 | FAQ 검색·카테고리 목록, 직접 질문 입력, 대화 화면 제공 |
| 설명 수준 맞춤 | 구현 완료 | 입문·초급·중급·고급 수준을 선택하고 질문에 적힌 수준도 우선 반영 |
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
사이드바에서 입문·초급·중급·고급 설명 수준을 선택할 수 있으며, 질문에
“ETF를 처음 접하는 입문자”처럼 배경지식이 드러나면 해당 표현을 우선 반영합니다.
설명 수준은 답변의 어휘와 용어 풀이 방식만 조정하며, 근거가 없는 정보를
추정해 답하지 않는 원칙은 동일하게 적용됩니다.

---

## 시스템 구조
| 조병관 | DS·팀장 | ETF 정보·공시 에이전트 개발 및 개선, 팀 진행 관리 |
| 김도윤 | PO | FAQ 전문 에이전트 개발 |
| 장나영 | AI 엔지니어 | 뉴스 에이전트 개발, 뉴스 도구 등록 및 화면 연동 |
| 한규진 | AI Solutions Architect·클라우드 엔지니어 | DB 구축, Docker 기반 공통 개발 환경 구성, 설정 안내 및 작업 환경 통일, Azure 배포 준비 |

기능별 개발은 각 담당자의 브랜치에서 진행하고, 공용 `dev` 브랜치에 병합하는 방식으로 협업했습니다.

---

## 3. 과제 요구사항별 진행 현황

| 과제 요구사항 | 진행 상태 | 수행 내용 및 남은 작업 |
| --- | --- | --- |
| 팀 GitHub 저장소 구성 | 완료 | 팀 공용 저장소와 기능별 브랜치 운영 |
| 개인 프로토타입 통합 | 부분 완료 | ETF 정보·공시 개선사항과 뉴스 기능 병합, 신규 FAQ 전문 에이전트 통합은 미완료 |
| 역할 분담 | 완료 | 개발·DB·설계·클라우드 준비 업무 분담 |
| 개인 피드백 반영 | 부분 완료 | 상품 정규화, DB 선확인, 결과 검증, 캐싱 등 반영 |
| 인증정보 관리 | 보완 필요 | `.env` 추적 제외, 기존 커밋에 포함된 DB 비밀번호에 대한 교체·이력 정리 필요 |
| 클라우드 배포 | 미완료 | Azure 선정 및 배포 준비 단계, 접속 가능한 배포 URL 없음 |

### 제출 범위

이번 제출물은 로컬에서 실행하는 팀 통합 프로토타입입니다.

ETF 정보·공시·뉴스 기능은 `dev`에 병합했으며, 신규 FAQ 전문 에이전트와 Azure 배포는 완료하지 못했습니다.

---

## 4. 현재 구현 구조

현재 실행 구조는 LangChain 에이전트가 질문에 필요한 조회 도구를 선택하는 방식입니다.

전문 기능을 담당하는 모듈을 분리해 개발하고 있으며, 네 전문 에이전트의 공통 인터페이스와 별도 라우터를 갖춘 최종 구조로 확장할 예정입니다.

```text
사용자 질문
    ↓
Streamlit
    ↓
LangChain 에이전트
    ├─ ETF 상품 검색
    │    └─ PostgreSQL ETF 상품 DB
    │
    ├─ ETF 시세 조회
    │    └─ 상품 DB에서 정식 상품 확인
    │         └─ 금융위원회 시세 API
    │
    ├─ 공시 검색
    │    └─ 상품 DB에서 상품명·운용사 확인
    │         └─ DART 회사 고유번호 캐시
    │              └─ DART 공시 API
    │
    ├─ 뉴스 검색
    │    └─ Google 뉴스 RSS
    │
    └─ 기존 FAQ 검색
         └─ PostgreSQL pgvector
    ↓
조회 결과를 근거로 답변 생성
    ↓
출처·자료 기준일·원문 링크 표시

요청 처리 결과
    └─ MongoDB request_logs 저장
```

ETF 시세·공시 결과는 검증 함수를 거쳐 답변 근거로 사용합니다.

현재의 조회 결과 검증은 최종 자연어 답변 전체를 검토하는 독립 검토 에이전트와는 구분됩니다.

---

## 5. 전문 에이전트별 구현 내용

### 5.1 ETF 정보 에이전트

**담당: 조병관 / 상태: dev 병합 완료**

ETF 상품 기본정보와 최근 자료 기준일의 종가·NAV를 조회합니다.

- PostgreSQL 상품 DB 기반 상품정보 검색
- `KODEX200`, `코덱스 200`, `069500` 등의 입력 정규화
- DB에서 정식 상품명·종목코드를 확정한 뒤 시세 API 호출
- 상품 DB의 빈 항목을 응답에서 `미확인`으로 표시
- 종가·NAV·자료 기준일·출처 반환
- `real_time: false`로 비실시간 자료임을 명시
- DB에서 확인되지 않는 상품은 조회 불가 처리
- 한국 날짜 기준 동일 상품의 시세 조회 결과 캐싱

주요 파일:

```text
agent_tools.py
api_tools.py
etf_api.py
result_validator.py
src/services/product_catalog.py
src/services/time_service.py
```

### 5.2 공시 에이전트

**담당: 조병관 / 상태: dev 병합 완료**

상품명과 운용사를 확인한 뒤 DART에서 관련 공시 후보를 조회합니다.

- PostgreSQL에서 정식 상품명·운용사 확인
- 운용사명으로 DART 회사 고유번호 조회
- 회사 고유번호 목록을 로컬 캐시에 저장하고 재사용
- 기존 일부 KODEX 상품 중심의 제한 구조 확장
- 공시 제목·날짜·원문 링크 제공
- 상품명과 공시 제목의 일치 여부를 보수적으로 확인
- 공시 날짜·검색 기간·DART 원문 링크 검증
- 공시 제목만으로 변경 내용 추측 금지
- 한국 시간 기준 검색 기간 계산

검색 결과는 다음처럼 구분합니다.

| 상태 | 의미 |
| --- | --- |
| `found` | 상품명이 일치하는 공시 후보를 찾음 |
| `no_results` | 검색을 완료했지만 일치하는 공시가 없음 |
| `search_incomplete` | 검색 범위 전체를 확인하지 못한 상태 |

`search_complete`는 전체 검색 완료 여부를 나타냅니다. 후보를 찾았더라도 건수 제한에 도달해 검색을 멈췄다면 전체 검색은 미완료일 수 있습니다.

주요 파일:

```text
dart_api.py
api_tools.py
result_validator.py
src/services/product_catalog.py
src/services/time_service.py
```

### 5.3 뉴스 에이전트

**담당: 장나영 / 상태: dev 병합 완료**

Google 뉴스 RSS를 통해 ETF 관련 뉴스를 검색하고 챗봇 화면에 제공합니다.

- 뉴스 조회 모듈과 LangChain 도구 분리
- `langchain_agent.py`에 뉴스 검색 도구 등록
- Streamlit 뉴스 카드 추가
- 기사 제목·언론사·날짜·링크 제공
- 사용한 뉴스 도구 이름 표시
- 별도 뉴스 검사 파일 구성

기사 본문 전체는 수집하지 않습니다.

주요 파일:

```text
news_api.py
news_tools.py
check_news.py
langchain_agent.py
app.py
```

### 5.4 FAQ 전문 에이전트

**담당: 김도윤 / 상태: 로컬 구현, dev 통합 미완료**

기존 FAQ 25개와 벡터 검색 도구를 활용하는 별도 Agent 인터페이스를 개발했습니다.

담당자 공유 기준 구현 내용:

- `faq_agent.py`에서 기존 `search_faq` 도구 호출
- `success`, `message`, `results`, `sources` 반환 형식 구성
- 질문 길이 1~1000자 검증
- 결과 없음·검색 오류·비정상 도구 응답 처리
- FAQ 출처 메타데이터 정리
- 정상·오류·입력 검증 테스트 코드 작성
- OpenAI·PostgreSQL 선택형 연동 테스트 작성
- FAQ 카테고리·질문·키워드 검색 화면 개발
- 입문·기본·심화 설명 수준 선택 기능 개발
- 진단 로그 및 연동 문서 작성

현재 FAQ 담당자의 테스트는 Python 실행 환경 문제로 시작하지 못했으며, 실제 API·DB 연동도 검증하지 못했습니다. 변경사항은 로컬 작업 브랜치에 보존되어 있고 Push·PR·dev 병합은 진행하지 않았습니다.

기존 통합본의 `search_faq` 검색 기능은 존재하지만, 위 신규 FAQ 전문 에이전트와 화면 개선사항은 이번 제출 범위에 포함되지 않습니다.

---

## 6. 멘토 피드백 반영

| 피드백 | 반영 상태 | 내용 |
| --- | --- | --- |
| 상품 DB의 빈 값 명시 | 반영 | 응답에서 `미확인`으로 반환 |
| 상품명·종목코드 선확정 | 반영 | 정규화 및 DB 확인 후 시세·공시 조회 |
| 시세·공시 결과 검증 | 반영·개선 | 상품명, 날짜, 수치, 출처 URL, 공시 링크 확인 |
| DART 회사 고유번호 캐싱 | 반영 | 로컬 JSON 캐시 재사용 |
| 시세 결과 캐싱 | 반영 | 한국 날짜 기준 프로세스 메모리 캐시 |
| 한국 시간 기준 날짜 처리 | 일부 반영 | 시세 조회·공시 검색·결과 검증에 적용 |
| 질문별 운영 기록 | 구현 | MongoDB에 응답 시간·도구·처리 상태 등 저장 |
| 로그의 질문 원문 제거 | 미반영 | 현재 원문이 저장되므로 개인정보 최소화 필요 |
| 최근 대화 문맥 유지 | 미반영 | 후속 질문의 상품 대상을 유지하는 메모리 필요 |
| 별도 라우터 도입 | 예정 | 필요한 전문 기능만 호출하도록 개선 |
| 신규 FAQ 전문 에이전트 | 통합 대기 | 테스트 및 dev 병합 필요 |
| 평가 데이터셋 기반 성능 비교 | 예정 | 의도 분류·검색·응답 품질 평가 필요 |
| 의존성 버전 고정 | 보완 필요 | 재현 가능한 실행 환경 정리 필요 |

---

## 7. 데이터 구성

### ETF 상품 데이터

공개 자료 기반 ETF 상품 20개를 PostgreSQL에서 관리합니다.

주요 필드:

```text
product_code
product_name
asset_manager
asset_category
underlying_index
total_fee_percent
risk_grade
listing_date
top_holdings
holdings_date
source_name
source_url
source_date
verified_at
```

원본은 CSV로 관리합니다. 확인하지 않은 항목은 원본·DB에서 빈 값으로 유지하고, 상품 조회 응답에는 `미확인`으로 표시합니다.

출처·기준일이 비어 있는 항목은 추가 확인이 필요하며, 공식적으로 검증된 정보처럼 표현하지 않습니다.

### FAQ 데이터

공개 투자자 교육 자료 등을 참고한 FAQ 25개를 사용합니다.

- ETF 기본 개념
- 주식·일반 펀드와의 차이
- NAV·괴리율·추적오차
- 거래 방법
- 비용·분배금
- 환율 및 상품 위험
- 공시 확인 방법

FAQ 검색은 OpenAI `text-embedding-3-small`과 PostgreSQL pgvector를 사용합니다.

### 로그 데이터

저장 위치:

```text
MongoDB
└─ etf_agent
   └─ request_logs
```

현재 주요 기록 항목:

- 기록 시각
- 사용자 질문 원문
- 응답 시간
- 처리 결과
- 사용 도구 목록
- 시세 API 사용 여부
- 오류 유형

기록 시각은 UTC로 저장합니다. 한국 시간은 UTC에 9시간을 더해 확인할 수 있습니다.

현재 로그에는 질문 원문이 포함되므로, 공개 서비스 전에는 질문 길이·사용 도구·시간·상태 중심으로 저장 범위를 줄여야 합니다.

---

## 8. 기술 스택

| 영역 | 기술 | 사용 목적 |
| --- | --- | --- |
| 언어 | Python | API·DB·에이전트 처리 |
| 화면 | Streamlit | 챗봇 및 조회 결과 표시 |
| 프레임워크 | LangChain | LLM과 조회 도구 연결 |
| LLM | OpenAI API | 질문 해석, 도구 선택, 답변 생성 |
| 상품·FAQ DB | PostgreSQL | 정형 데이터 관리 |
| 벡터 검색 | pgvector | FAQ 의미 기반 검색 |
| 임베딩 | text-embedding-3-small | 검색용 벡터 생성 |
| 로그 DB | MongoDB | 요청·응답 시간·처리 상태 기록 |
| 로컬 DB 실행 | Docker Compose | 공통 DB 환경 구성 |
| 시세 | 금융위원회 증권상품시세정보 API | 기준일 종가·NAV 조회 |
| 공시 | DART Open API | 펀드 공시 제목·링크 검색 |
| 뉴스 | Google 뉴스 RSS | ETF 관련 뉴스 검색 |
| 협업 | GitHub | 기능별 브랜치·PR·dev 통합 |
| 배포 예정 | Microsoft Azure | 클라우드 서비스 실행 |

---

## 9. 주요 프로젝트 파일

```text
etf-ai-agent/
├─ app.py
├─ langchain_agent.py
├─ agent_tools.py
├─ api_tools.py
├─ etf_api.py
├─ dart_api.py
├─ news_api.py
├─ news_tools.py
├─ result_validator.py
├─ build_database.py
├─ build_embeddings.py
├─ check_agent_tools.py
├─ check_langchain_agent.py
├─ check_news.py
├─ compose.yaml
├─ requirements.txt
├─ README.md
├─ .env.example
├─ .gitignore
├─ .streamlit/
├─ database/
│  ├─ schema.sql
│  └─ migrations/
├─ data/
│  ├─ source/
│  │  ├─ etf_products.csv
│  │  └─ FAQ CSV
│  └─ cache/
│     └─ dart_corp_codes.json
├─ docs/
│  └─ deployment.md
└─ src/
   ├─ db/
   │  ├─ postgres.py
   │  └─ mongo.py
   └─ services/
      ├─ product_catalog.py
      ├─ time_service.py
      ├─ embeddings.py
      ├─ vector_search.py
      └─ request_logger.py
```

FAQ 원본 CSV의 실제 파일명은 저장소와 `build_database.py` 설정을 따릅니다.

`data/cache/`는 실행 중 자동 생성되며 Git 추적 대상에서 제외합니다. 신규 `faq_agent.py` 관련 파일은 통합 대기 상태이므로 위 통합본 목록에서 제외했습니다.

---

## 10. 설치 및 실행

### 10.1 코드 받기

```powershell
git clone https://github.com/comento-aiagent-1/etf-ai-agent.git
cd etf-ai-agent
git checkout dev
```

이미 저장소가 있다면 로컬 변경사항을 확인한 후 최신 `dev`를 받습니다.

```powershell
git status
git checkout dev
git pull origin dev
```

### 10.2 가상환경 및 라이브러리

가상환경이 없을 때 생성합니다.

```powershell
py -m venv .venv
```

라이브러리를 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 10.3 환경변수

프로젝트 루트에 `.env` 파일을 만들고 `.env.example`에 정의된 항목을 설정합니다.

필요한 주요 항목:

```text
OPENAI_API_KEY
ETF_DATA_API_KEY
DART_API_KEY

POSTGRES_DB
POSTGRES_HOST
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_PORT

MONGO_ROOT_USERNAME
MONGO_ROOT_PASSWORD
MONGO_HOST
MONGO_PORT
MONGO_DB

FAQ_MIN_SIMILARITY
```

실제 API 키와 DB 비밀번호는 저장소·제출물에 포함하지 않습니다.

기존 DB가 있는 경우 `.env`의 비밀번호만 바꿔서는 DB 계정 비밀번호가 변경되지 않습니다. 현재 사용 중인 DB 계정과 설정을 함께 맞춰야 합니다.

### 10.4 로컬 DB 실행

Docker Desktop을 실행한 뒤 프로젝트 루트에서 실행합니다.

```powershell
docker compose up -d --wait
```

상태를 확인합니다.

```powershell
docker compose ps
```

PostgreSQL과 MongoDB가 정상 실행 중인지 확인합니다.

기존 볼륨에 스키마 변경을 적용하는 방법은 `docs/deployment.md`를 참고합니다.

### 10.5 데이터 적재

```powershell
.\.venv\Scripts\python.exe build_database.py
```

현재 데이터 구성:

```text
ETF 상품: 20개
FAQ: 25개
```

반복 실행 시 변경 건수는 데이터 상태에 따라 달라집니다.

### 10.6 임베딩 생성

```powershell
.\.venv\Scripts\python.exe build_embeddings.py
```

공개 상품·FAQ 텍스트를 OpenAI 임베딩 API로 전송합니다. API 사용량에 따른 비용이 발생할 수 있습니다.

### 10.7 도구 검사

```powershell
.\.venv\Scripts\python.exe check_agent_tools.py
```

```powershell
.\.venv\Scripts\python.exe check_news.py
```

```powershell
.\.venv\Scripts\python.exe check_langchain_agent.py
```

### 10.8 챗봇 실행

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

터미널에 표시되는 `Local URL`을 엽니다.

```text
http://localhost:8501
```

실제 포트는 터미널 출력에 따릅니다. 종료할 때는 실행 중인 터미널에서 `Ctrl+C`를 누릅니다.

---

## 11. 시연 및 검증

| 구분 | 시험 질문 | 확인 항목 |
| --- | --- | --- |
| 상품 DB | TIGER 미국S&P500의 운용사와 기초지수를 알려줘 | 상품 DB 조회 및 저장된 정보 반환 |
| 상품 정규화 | 코덱스 200의 종가를 알려줘 | 정식 상품명·종목코드 확정 |
| 종목코드 | 069500의 종가와 NAV를 알려줘 | KODEX 200으로 연결 |
| 시세 | KODEX 200의 최근 종가와 NAV를 알려줘 | 기준일·종가·NAV·출처 표시 |
| 공시 | KODEX 200 관련 공시 알려줘 | 제목·날짜·원문 링크 제공 |
| 운용사 확장 | TIGER 미국S&P500 관련 공시 알려줘 | DB 운용사 기반 DART 검색 |
| 뉴스 | KODEX 200 관련 최신 뉴스 알려줘 | 뉴스 도구 호출 및 기사 정보 표시 |
| 복합 질문 | KODEX 200의 종가와 관련 공시를 같이 알려줘 | 두 도구 호출 및 결과 통합 |
| 기존 FAQ | ETF와 주식은 어떻게 달라? | 기존 FAQ 검색 도구 동작 확인 |
| 미지원 상품 | 달토끼 우주여행 ETF의 종가를 알려줘 | 확인되지 않은 수치 생성 방지 |

복합 질문에서 여러 도구를 선택하는 기능은 구현했으나, 이를 모든 호출이 병렬 실행된다는 의미로 사용하지 않습니다.

### 현재까지 확인한 동작

- 상품명·종목코드 정규화
- ETF 종가·NAV 및 자료 기준일 반환
- 시세·공시 복합 질문 처리
- DART 공시 후보 제목·링크 제공
- TIGER 상품의 공시 검색 도구 호출
- MongoDB 요청 로그 저장

뉴스 기능은 담당자가 `dev` 병합을 완료한 상태입니다. 최종 제출 커밋에서 다른 기능과 함께 회귀 테스트가 필요합니다.

신규 FAQ 전문 에이전트는 테스트 미실행·미통합 상태이며, 전체 시스템의 정량적인 정확도와 응답속도 목표 달성 여부는 아직 평가하지 않았습니다.

---

## 12. 보안 점검 현황

`.env` 파일 자체는 Git에서 무시되고 추적되지 않습니다.

다만 FAQ 통합 전 점검에서 기존 DB 환경 구축 커밋 `a17f5de04595`에 현재 `.env`와 일치하는 PostgreSQL·MongoDB 비밀번호가 포함된 사실을 확인했습니다.

해당 커밋은 기존 `dev` 이력에 포함되어 있습니다.

제출 설명 작성 시점에 다음 조치의 완료 여부는 확인되지 않았습니다.

- 실제 PostgreSQL·MongoDB 계정 비밀번호 교체
- 각 개발 환경의 `.env` 갱신
- 코드·설정 파일의 실제 비밀번호 및 기본값 제거
- 기존 Git 이력 정리 범위와 방법 합의

기존 이력 처리는 통합 담당자가 팀과 조율하여 진행할 예정입니다. FAQ 변경사항은 로컬에 보존되어 있으며, 보안 조치 및 실행 환경 확인 후 테스트·Push·병합을 진행합니다.

---

## 13. 클라우드 배포 현황

### 선정 플랫폼

Microsoft Azure를 사용하기로 결정했습니다.

한규진이 클라우드 엔지니어 역할을 함께 맡아 로컬 DB 환경과 공통 실행 환경을 구성하고 배포를 준비했습니다.

### 현재 상태

**Azure 배포는 완료하지 못했습니다.**

현재 확인된 실행 범위는 로컬 Docker DB와 Streamlit입니다.

| 항목 | 상태 |
| --- | --- |
| 로컬 PostgreSQL·pgvector 실행 | 확인 |
| 로컬 MongoDB 실행 | 확인 |
| 로컬 Streamlit 실행 | 확인 |
| Azure 배포 플랫폼 선정 | 완료 |
| Azure 앱·DB 실행 환경 구성 | 완료 확인 안 됨 |
| 외부 접속 URL | 없음 |
| 클라우드 통합 테스트 | 미실시 |

### 남은 배포 작업

1. 실제 인증정보 교체 및 비밀정보 관리 정비
2. FAQ 전문 에이전트 통합과 실행 검증
3. Azure 앱 호스팅 및 DB 구성 확정
4. 앱 환경변수와 DB 연결 설정
5. 배포 및 외부 접속 확인
6. 시세·공시·뉴스·FAQ 통합 시험
7. 오류·로그·재시작 동작 확인

FAQ 미통합과 Azure 미배포는 각각 미완료 항목으로 관리합니다.

---

## 14. 현재 한계와 후속 계획

### 현재 한계

- 고객사 내부 데이터 대신 공개 자료 기반 샘플을 사용합니다.
- 일부 상품 필드와 출처·기준일은 추가 확인이 필요합니다.
- 시세는 공공데이터의 최근 기준일 값이며 실시간 가격이 아닙니다.
- DART 검색은 제목 일치 기반 후보 검색이므로 공시 누락 가능성이 있습니다.
- 공시 원문 본문 분석·변경 내용 요약은 구현하지 않았습니다.
- 뉴스 검색은 Google 뉴스 RSS 형식과 검색 결과에 의존합니다.
- 신규 FAQ 전문 에이전트는 통합하지 못했습니다.
- 최근 대화를 활용하는 세션 메모리는 구현하지 않았습니다.
- 독립적인 최종 답변 검토 에이전트는 구현하지 않았습니다.
- 로그에 질문 원문이 저장됩니다.
- DB 인증정보 노출에 대한 후속 조치가 필요합니다.
- Azure 배포와 클라우드 검증은 완료하지 못했습니다.

### 후속 계획

- 전문 에이전트 입력·출력 형식 통일
- 질문 의도를 먼저 판단하는 라우터 도입
- 필요한 전문 기능만 선택적으로 호출
- 최근 대화 및 마지막 ETF 상품을 유지하는 메모리 추가
- 최종 답변의 출처·기준일·유의 문구 검토
- 질문 원문을 최소화한 운영 로그 구성
- 예상 질문 평가셋을 활용한 검색·분류 성능 평가
- 응답 시간 및 오류율 비교
- Azure 배포 및 운영 검증

---

## 15. 과제 제출 구성

이번 제출은 멘토가 제시한 다음 세 항목에 맞춰 정리했습니다.

1. 팀 GitHub 저장소 구성 및 개인 프로토타입 통합
2. 멘토 피드백을 반영한 기능 추가·개선
3. 클라우드 플랫폼 선정 및 배포 진행 현황

### 제출 자료

- 팀 GitHub 저장소 링크
- 제출 기준 `dev` 커밋 ID
- README의 구현·미완료 현황
- 로컬 챗봇 실행 및 주요 기능 시연 화면
- Azure 미배포 사유와 후속 계획

제출 기준 커밋은 아래 명령으로 확인합니다.

```powershell
git rev-parse HEAD
```

### 공유·제출 제외 항목

```text
.env
.venv/
__pycache__/
*.pyc
data/cache/
logs/
.git/
```

실행에 필요한 소스코드·스키마·마이그레이션·공개 CSV·설정 예시는 포함합니다.

---

## 16. 참고 자료

- 금융위원회 증권상품시세정보  
  https://www.data.go.kr/data/15094806/openapi.do

- DART Open API  
  https://opendart.fss.or.kr/

- 한국거래소  
  https://open.krx.co.kr/

- 전국투자자교육협의회  
  https://www.kcie.or.kr/

- LangChain 공식 문서  
  https://docs.langchain.com/

- Streamlit 공식 문서  
  https://docs.streamlit.io/

- 코멘토 클라우드 플랫폼을 활용한 LLM 서비스 배포 튜토리얼  
  멘토 제공 자료