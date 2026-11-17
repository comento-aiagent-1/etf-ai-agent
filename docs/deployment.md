# 로컬 PostgreSQL / MongoDB 실행

프로젝트 루트의 `compose.yaml`은 pgvector 0.8.7을 포함한 PostgreSQL 17과 공식 MongoDB 8.0 이미지를
사용합니다. DB별 커스텀 이미지가 필요하지 않아 별도 Dockerfile 빌드 없이 실행합니다.
Docker Desktop을 Linux 컨테이너 모드로 실행한 뒤 아래 명령을 사용하세요.

```powershell
docker compose up -d --wait
docker compose ps
```

첫 실행에는 이미지를 다운로드합니다. 두 서비스가 `healthy`이면 준비가 끝났습니다.
`.env` 없이도 로컬 개발 기본값으로 실행됩니다. 설정을 바꾸려면 `.env.example`의
DB 항목을 기존 `.env`에 추가하세요. 기존 API 키가 있는 `.env`를 덮어쓰지 마세요.
이 구성은 로컬 개발용이며 포트를 `127.0.0.1`에만 공개합니다.

## 로컬 접속 정보

| 항목 | PostgreSQL | MongoDB |
| --- | --- | --- |
| 호스트 | `127.0.0.1` | `127.0.0.1` |
| 포트 | `5432` | `27017` |
| 데이터베이스 | `etf_agent` | `etf_agent` (첫 데이터 저장 시 생성) |
| 사용자 | `etf_user` | `etf_admin` |
| 비밀번호 | `local_postgres_password` | `local_mongo_password` |
| 인증 DB | 해당 없음 | `admin` |

기본값 기준 접속 URI:

```text
postgresql://etf_user:local_postgres_password@127.0.0.1:5432/etf_agent
mongodb://etf_admin:local_mongo_password@127.0.0.1:27017/etf_agent?authSource=admin
```

`.env`에서 계정이나 포트를 변경했다면 접속 정보도 함께 바꾸세요.
URI에 사용하는 사용자명/비밀번호의 특수문자는 URL 인코딩이 필요합니다.
MongoDB 계정은 로컬 개발용 관리자 계정입니다.

현재 챗봇 조회(`agent_tools.py`)와 CSV 적재(`build_database.py`)는 PostgreSQL을 사용합니다.
두 모듈은 `src/db/postgres.py`의 공통 접속 설정을 사용합니다.
FAQ는 질문 임베딩과 저장된 FAQ 벡터의 코사인 유사도로 검색합니다.
PostgreSQL은 최초 실행 시 아래 스키마를 생성하며,
MongoDB의 `request_logs` 컬렉션과 시각 인덱스는 첫 로그 저장 시 생성합니다.

## PostgreSQL 스키마 적용

`database/schema.sql`을 초기화 SQL로 마운트합니다. 빈 PostgreSQL 볼륨에서는
첫 실행에 pgvector 확장과 `etf_products`, `faq`, `document_chunks` 테이블이 생성됩니다.
상품·FAQ 컬럼은 기존 CSV를 기준으로 정의했습니다. 날짜는 `DATE`, 수수료는
`NUMERIC`이므로 이후 적재 코드에서 빈 날짜를 `NULL`로 변환해야 합니다.

기존 볼륨에는 초기화 SQL이 자동 실행되지 않습니다. 이미 실행한 환경에서는
이미지를 교체한 후 다음 명령으로 기존 데이터를 보존하며 스키마를 적용하세요.

```powershell
docker compose up -d --wait postgres
'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/001-schema.sql # apply schema' | docker compose exec -T postgres sh
```

이 스크립트는 트랜잭션으로 실행하며 재실행해도 데이터를 삭제하지 않습니다.
`CREATE TABLE IF NOT EXISTS`는 기존 테이블 구조를 수정하지 않으므로,
추후 컬럼 변경은 별도 마이그레이션으로 관리해야 합니다.

`document_chunks`는 상품 또는 FAQ 한 건에 연결하며 본문, 내용 해시, 임베딩,
모델명과 차원을 저장합니다. 원본 삭제 시 연결된 청크도 삭제됩니다.
모델은 `text-embedding-3-small`, 차원은 1,536으로 통일했습니다.
컬럼은 다른 모델과의 향후 공존을 위해 `vector`로 유지하며 실제 차원을 검사합니다.
해당 모델·차원의 부분 HNSW 인덱스를 생성합니다. 현재 소규모 FAQ 검색은
정확한 코사인 검색 후 FAQ별 최고 점수로 묶으므로 HNSW 사용을 강제하지 않습니다.
검색은 모델·차원·원본 수정 시각이 일치하는 벡터만 사용합니다.
내용이나 출처가 변경되면 임베딩 생성 스크립트를 다시 실행하세요.
`updated_at`은 UPDATE 시 트리거로 자동 갱신됩니다.

## 접속 확인

프로젝트 가상환경에서 CSV 적재를 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build_database.py
```

스크립트는 프로젝트 루트의 `.env`를 읽으며 프로세스 환경변수가 우선합니다.
`POSTGRES_HOST` 기본값은 `127.0.0.1`이고 나머지 DB 설정은 Compose와 같습니다.
두 CSV를 모두 검증한 후 하나의 트랜잭션으로 적재합니다. 키가 같으면 변경된
행만 갱신하며 CSV에 없는 기존 행은 삭제하지 않습니다. 재실행 시 변경이 없으면
`changed=0`이 표시됩니다. 빈 값은 `NULL`, 날짜는 ISO 날짜, 수수료는 십진수입니다.
잘못된 입력이나 DB 오류는 종료 코드 1로 실패하며 부분 적재를 방지합니다.
스키마는 미리 적용해야 합니다. CSV 적재 후 아래 임베딩 생성 명령을 실행하세요.

컨테이너에 설정된 계정으로 PostgreSQL 쿼리를 실행합니다.

```powershell
'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"' | docker compose exec -T postgres sh
```

MongoDB는 기본 사용자 기준으로 다음 명령을 실행한 뒤 비밀번호를 입력합니다.
사용자를 변경했다면 `etf_admin`도 변경하세요.

```powershell
docker compose exec mongodb mongosh --username etf_admin --authenticationDatabase admin --password
```

접속 후 `db.runCommand({ ping: 1 })`을 실행해 `ok: 1`을 확인합니다.

## 로그 및 종료

앱 응답 로그는 `MONGO_DB`(기본 `etf_agent`)의 `request_logs`에 저장됩니다.
`MONGO_HOST` 기본값은 `127.0.0.1`이며 포트와 계정은 Compose와 같은 환경변수를
사용합니다. 변경 후 앱 프로세스를 재시작하면 캐시된 연결이 새 설정을 사용합니다.
기존 가상환경에는 `pip install -r requirements.txt`로 `pymongo`를 설치하세요.

각 문서에는 `_id`(요청 UUID), `created_at`(UTC), `question`, `elapsed_seconds`,
`result`, `status`(`success`/`empty_answer`/`error`), `error_type`, `used_tools`,
`used_etf_api`가 저장됩니다. 응답시간에는 로그 저장 시간이 포함되지 않습니다.
`created_at` 인덱스로 최신 로그를 조회합니다. 자동 삭제 정책은 설정하지 않았습니다.
MongoDB 연결과 저장에는 2초 제한을 두며 실패하면 답변을 유지하고 알림을 표시합니다.
실패 로그는 자동 재전송하지 않으며 기존 CSV는 자동 이전하지 않습니다.

위 MongoDB 접속 명령으로 `mongosh`에 들어가 최신 5건을 확인할 수 있습니다.
DB 이름을 변경했다면 아래 이름도 변경하세요.

```javascript
db.getSiblingDB("etf_agent").request_logs.find().sort({created_at: -1}).limit(5)
```

외부 LLM 호출 없이 로그 저장과 장애 처리를 검증합니다. 테스트가 만든 문서만
삭제하며 기존 로그는 유지합니다.

```powershell
$env:RUN_MONGO_TESTS = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_request_logger.py"
Remove-Item Env:RUN_MONGO_TESTS
```

```powershell
docker compose logs --tail 100 postgres mongodb
docker compose down
```

`down`으로 컨테이너를 제거해도 named volume의 데이터는 유지됩니다.
다음 실행에 기존 데이터를 다시 사용합니다. 컨테이너만 잠시 멈추려면
`docker compose stop`, 다시 시작하려면 `docker compose start`를 사용하세요.

**DB 데이터를 모두 삭제하고 초기화할 때만** 다음을 실행하세요.

```powershell
docker compose down -v
docker compose up -d --wait
```

초기 계정과 PostgreSQL DB 이름 설정은 빈 볼륨의 최초 실행에만 적용됩니다.
기존 데이터가 있다면 `.env`만 변경해도 DB 계정이 바뀌지 않습니다.
데이터를 유지하려면 DB에서 계정을 변경하고, 삭제해도 되는 경우에만 위 초기화를 사용하세요.

## 실행 문제

- 엔진 연결 오류: Docker Desktop을 시작하고 Linux 엔진 준비를 기다리세요.
- 포트 충돌: `.env`에 `POSTGRES_PORT=5433` 또는 `MONGO_PORT=27018`을 지정한 뒤
  `docker compose up -d --wait`를 다시 실행하세요.
- 시작 실패: `docker compose logs --tail 100 postgres mongodb`로 원인을 확인하세요.

공식 이미지 문서: [PostgreSQL](https://hub.docker.com/_/postgres),
[MongoDB](https://hub.docker.com/_/mongo).
벡터 확장 및 이미지: [pgvector](https://github.com/pgvector/pgvector).

## 임베딩 생성과 벡터 검색

기존 DB에는 다음 마이그레이션을 먼저 적용하세요. 아래 명령은 기본 계정 기준이며
`.env`에서 계정이나 DB 이름을 바꿨다면 `-U`와 `-d`도 변경해야 합니다.

```powershell
Get-Content -Raw database/migrations/001_vector_search.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U etf_user -d etf_agent
```

새 볼륨은 `schema.sql`에서 동일한 변경을 자동 적용합니다. 기존 벡터의
`source_updated_at`은 미설정 상태이므로 다음 명령으로 재생성해야 검색에 포함됩니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build_database.py
.\.venv\Scripts\python.exe build_embeddings.py
```

프로젝트 `.env`의 `OPENAI_API_KEY`가 필요합니다. 상품·FAQ 텍스트와 검색 질문이
OpenAI 임베딩 API로 전송되며 API 사용 비용이 발생합니다. 키를 소스에 넣지 마세요.
모델·차원은 `src/services/embeddings.py`의 상수로 고정해 생성과 검색을 통일했습니다.
모델을 바꾸면 검색 설정과 인덱스도 함께 수정하고 임베딩을 다시 생성해야 합니다.

본문은 최대 1,000자, 중첩 100자로 나누고 SHA-256 내용 해시와 원본 수정 시각을 저장합니다.
변경된 문서만 재생성하며 짧아진 문서의 오래된 청크는 제거합니다.
전체 작업은 하나의 DB 트랜잭션이며 API 오류 시 DB 변경을 롤백합니다.
이미 호출한 API 사용량은 롤백되지 않습니다. 생성 중 원본 수정은 잠시 대기할 수 있습니다.

FAQ는 같은 모델·차원이며 원본 수정 시각이 일치하는 청크만 검색하고,
FAQ별 최고 유사도 순으로 최대 3건을 반환합니다. `match_score`는 코사인 유사도입니다.
최소값은 `.env`의 `FAQ_MIN_SIMILARITY`(기본 0.3, 허용 0~1)로 조정합니다.
이 값은 초기 설정이며 실제 관련/무관 질문 평가로 보정해야 합니다.
검색 질문은 1~1,000자입니다. API 오류·누락된 벡터·유사도 미달 시 실패 결과를 반환하고
다른 검색 방식으로 조용히 전환하지 않습니다. 상품 정보 조회는 기존 SQL 방식을 유지합니다.

모의 API와 PostgreSQL 임시 테이블로 재실행, 변경분 갱신, 오래된 벡터 제외,
모델 분리, 실패 시 롤백을 검증할 수 있습니다.

```powershell
$env:RUN_POSTGRES_TESTS = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_embeddings.py"
Remove-Item Env:RUN_POSTGRES_TESTS
```

모델 설명: [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings).

실제 API와 저장된 벡터로 한국어 질문 3개 및 무관한 질문 1개를 점검합니다.
이 검사는 소규모 동작 확인이며 전체 검색 품질 평가를 대체하지 않습니다.

```powershell
.\.venv\Scripts\python.exe check_vector_search.py
```

## PostgreSQL 조회 검증

Streamlit 화면 코드를 실제 API·DB와 함께 실행하는 전체 흐름 검증:

```powershell
.\.venv\Scripts\python.exe check_app_e2e.py
```

상품·FAQ 질문을 입력하고 답변, 도구 호출, MongoDB 로그를 확인합니다.
로그 저장 장애와 에이전트 오류는 모의 주입으로 점검하며 DB 서버를 중지하지 않습니다.
실제 OpenAI API 비용이 발생하고 테스트 요청 로그는 MongoDB에 남습니다.
Streamlit AppTest 검사이므로 브라우저의 시각적 레이아웃 검사는 포함하지 않습니다.

실제 상품·FAQ 도구를 확인합니다. `check_agent_tools.py`의 FAQ 검색은
OpenAI 임베딩 API를 호출합니다. 통합 테스트는 모의 임베딩을 사용합니다.

```powershell
.\.venv\Scripts\python.exe check_agent_tools.py
$env:RUN_POSTGRES_TESTS = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*tools.py"
Remove-Item Env:RUN_POSTGRES_TESTS
```

통합 테스트는 접속 세션의 임시 테이블을 사용하며 기존 상품·FAQ 데이터를 변경하지 않습니다.
