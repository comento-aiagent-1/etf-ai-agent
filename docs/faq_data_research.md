# 국내 ETF 공식자료 조사 및 FAQ 출처 관리표

확인일은 2026-11-27 (한국시간)입니다. 아래 F026–F050 자료는 첫 추가 조사 기록이며, 현재 총 75개의 FAQ 중 나중에 추가한 F051–F075의 근거는 다음 절에 별도로 정리했습니다.

## 추가 조사: F051–F075

현재 CSV에는 총 75개가 있습니다. 이번 추가분은 삼성자산운용 KODEX의 ETF 투자기초가이드와 미래에셋자산운용 TIGER의 ETF 거래방법·아카데미·연금 안내에서 주제를 확인해 질문과 답변을 새로 작성했습니다. 각 행의 직접 출처는 [FAQ.csv](../data/source/FAQ.csv)에 기록했습니다. 확인한 공개 자료는 교육·상품 안내이며, 이 25개가 게시된 실제 고객 질문이거나 실제 질문 빈도가 높은 순서라는 공개 근거는 확인하지 못했습니다. 따라서 실제 빈도 순위가 아닌, 공식 공개 자료를 바탕으로 한 FAQ 큐레이션입니다.

| FAQ ID | 주제 | 출처 |
|---|---|---|
| F051–F052 | ETF 정의와 구성 자산 | [KODEX ETF 투자기초가이드 1화](https://m.samsungfund.com/etf/insight/guide/view01.do) |
| F053–F054, F056, F061–F062 | ETF 주문·확인 절차, 계좌, 구성종목 및 비용 | [TIGER ETF 거래방법](https://investments.miraeasset.com/tigeretf/ko/etfMethod/content.do) |
| F055, F057–F058, F060, F064 | 가격·NAV·괴리율·추적오차·호가·분배락 | [TIGER ETF 아카데미](https://investments.miraeasset.com/tigeretf/ko/academy/beginner/content.do) |
| F059, F063, F065–F073 | LP, 분배금, 상장폐지, 환헤지, 선물·합성·레버리지·인버스 및 거래시간 | [KODEX ETF 투자기초가이드 2–10화](https://m.samsungfund.com/etf/insight/guide.do) |
| F074–F075 | 연금계좌의 세금·ETF 투자 가능 범위 | [TIGER 연금제도 안내](https://investments.miraeasset.com/tigeretf/ko/pension/private/list.do) |

## 첫 추가 조사 당시 데이터와 확인한 건수

| 확인 위치 | 건수 |
|---|---:|
| 첫 추가 전 FAQ 원본 CSV 및 Streamlit의 CSV 대체 목록 | 25 |
| 저장소의 구형 SQLite `faq` 테이블 | 25 |
| 당시 PostgreSQL `faq` 테이블의 읽기 전용 조회 | 25 |
| 당시 Streamlit의 PostgreSQL 목록 | 25 |
| 첫 추가 후 FAQ 원본 CSV | 50 |

현재 확인한 파일과 DB에는 기존 FAQ가 각각 25개입니다. 27개로 집계됐다는 설명의 기준이나 원본은 확인되지 않았습니다. CSV에 새 행을 추가해도 정상 연결된 앱은 PostgreSQL에 등록된 항목만 목록에 표시하므로 CSV와 DB 건수가 달라질 수 있습니다.

## 조사 및 선정 기준

- 원본 본문에서 확인한 자료는 국내 5개 기관의 24개 문서입니다. 삼성자산운용(Kodex), 미래에셋자산운용(TIGER), KB자산운용(RISE), 미래에셋증권, 한국거래소의 공개 자료를 사용했습니다.
- 기관의 FAQ에 나온 질문과 질문 형식이 없는 투자 가이드·공시·설명서를 구분했습니다. 입수한 자료의 핵심 내용을 일상적인 한국어 질문과 짧은 답변으로 재작성했습니다. 이용자 질문 빈도 자료는 확인되지 않았습니다.
- 주문·결제, 환헤지, 해외 휴장, 상장폐지, 채권 등은 여러 자료를 비교했습니다. 일치하는 설명이라도 문서의 적용 시장과 상품 유형을 확인했습니다. 예를 들어 국내 ETF 주문·결제 안내의 숫자는 미국 상장 ETF에 적용하지 않았고, 만기채 상장폐지 공지의 날짜는 그 상품의 사례로만 참고했습니다.
- 기존의 ETF·NAV·괴리율·총보수·LP 정의와 일반 매매 방법은 그대로 보존했습니다. 새 행은 기존 내용과 가장 가까운 질문을 비교해 적용 범위, 판단 기준 또는 실제 사례가 달라지는 항목을 선정했습니다. 레버리지 원점 회귀 사례는 일간 배율 개념을 적용한 독자 계산입니다.
- 보유기간 과세와 ISA·연금 제한은 확인일과 적용 범위를 함께 적었습니다. 상품설명서에 나온 특정 수익률·거래 비용·위험 등급을 전체 상품에 넣지 않았습니다. 주 출처의 날짜가 일 단위로 확인되지 않으면 DB의 DATE 컬럼 호환을 위해 CSV에서 비워 두고 이 표에서 미확인 또는 월 단위로 표시했습니다.
- 삼성증권 거래 안내 웹페이지와 일부 한국거래소·RISE 웹페이지는 직접 열기에서 오류 또는 시간 초과가 발생했습니다. 확인된 원문에는 접근 가능한 한국거래소 공식 PDF와 RISE 투자설명서를 사용했습니다.

## 공식자료 목록

모든 행의 실제 확인일은 2026-11-27입니다. 자료 날짜는 본문에 기재된 작성기준일, 공지일 또는 약관 시행일을 사용했습니다.

| 자료 | 기관 | 원문 | 유형 | 자료 날짜 | 확인한 주제 |
|---|---|---|---|---|---|
| S01 | 미래에셋증권 | [국내주식 거래설명서](https://securities.miraeasset.com/hki/hki3032/n50.do) | 설명서 | 미확인 | 주문 방식과 국내 증권 결제의 체결·입고 구분 |
| S02 | 삼성자산운용 | [Kodex ETF 투자기초가이드 2화 · ETF 투자방법](https://m.samsungfund.com/etf/insight/guide/view02.do) | 교육 가이드 | 미확인 | 국내 상장 ETF 주문 절차와 정규장 시간 |
| S03 | 한국거래소 | [Guide to Trading in the Korean Stock Market](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf) | 거래소 제도 가이드 | 미확인 | 국내 증권시장의 주문 유형, 정규장 구간과 T+2 결제 |
| S04 | 미래에셋증권 | [해외주식 거래설명서](https://trading.securities.miraeasset.com/hki/hki3032/n03.do) | 설명서 | 미확인 | 해외시장별 통화, 거래시간, 주문·결제 유의사항 |
| S05 | 삼성자산운용 | [삼성 Kodex 중개형 ISA 투자 가이드북 · 부록 FAQ](https://www.samsungfund.com/upload/kodex/newsroom/2026011317101936.pdf) | 교육 가이드 내 공개 FAQ | 미확인 | 중개형 ISA에서 해외주식에 간접 투자하는 국내 상장 ETF와 직접 해외 거래의 차이 |
| S06 | 미래에셋증권 | [중개형 개인종합자산관리계좌(ISA) 설명서](https://securities.miraeasset.com/hki/hki3032/n20.do) | 설명서 | 미확인 | 중개형 ISA의 상품 선택과 과세 조건 |
| S07 | 삼성자산운용 | [ETF 연금술사 · 연금 계좌에서 투자할 수 없는 ETF](https://m.samsungfund.com/upload/kodex/newsroom/20261030155119262.pdf) | 교육 가이드 내 공개 FAQ | 미확인 | 연금저축과 퇴직연금의 레버리지·인버스 등 상품 제한 |
| S08 | 삼성자산운용 | [Kodex ETF 투자기초가이드 5화 · ETF 세금](https://www.samsungfund.com/etf/insight/guide/view05.do) | 교육 가이드 | 미확인 | 일반계좌에서의 매매차익·분배금 과세 구분과 과표기준가격 |
| S09 | 삼성자산운용 | [Kodex ETF 투자기초가이드 7화 · (H)와 (UH)](https://m.samsungfund.com/etf/insight/guide/view07.do) | 교육 가이드 | 미확인 | 환헤지 목표, 잔존 환위험과 헤지 비용 |
| S10 | KB자산운용 | [RISE 팔라듐선물(H) 간이투자설명서](https://www.riseetf.co.kr/upload/cdn/2026/01/29/20260129cae05c619534480.pdf) | 간이투자설명서 | 2026-01-01 | 상품 사례의 환헤지 목표와 한계, 해외시장 시차와 상장폐지 위험 |
| S11 | 삼성자산운용 | [Kodex 온가족 ETF 투자 패키지 북 · 월배당 Q&A](https://m.samsungfund.com/upload/kodex/newsroom/20260427141121713.pdf) | 교육 가이드 내 공개 FAQ | 2026-04 (월 단위 표기) | 분배금 지급 기준일과 결제, 분배락과 순자산가치 |
| S12 | 삼성자산운용 | [소득세법 시행령 개정에 따른 삼성 KODEX ETF 분배금 지급 방식 변경 안내](https://m.samsungfund.com/etf/lounge/notice-view.do?no=67815) | 운용사 공지 | 2025-06-20 | 대상 ETF의 펀드 내 재투자 방식과 현금 분배 정책 변경 |
| S13 | 미래에셋자산운용 | [TIGER 미국배당다우존스타겟커버드콜1호 투자설명서](https://www.tigeretf.com/upload/etf/20250304090531000354.pdf) | 투자설명서 | 2025-02-21 | 목표 분배율의 산정 대상과 실제 지급 차이, 콜옵션 매도 포지션 위험 |
| S14 | 삼성자산운용 | [KODEX 23-12 만기채 ETF 2종 상장폐지 예정 안내](https://www.samsungfund.com/etf/lounge/notice-view.do?no=56253) | 운용사 공지 | 2023-11-07 | 거래정지일과 해지상환금 지급일이 구분되는 실제 청산 사례 |
| S15 | 미래에셋자산운용 | [TIGER CD금리플러스액티브(합성) 투자설명서](https://www.tigeretf.com/upload/etf/20250228090901009939.pdf) | 투자설명서 | 2025-02-21 | 비교지수 초과성과 목표, 금리·채권 가격 관계, 스왑의 신용위험 |
| S16 | 삼성자산운용 | [Kodex 만기매칭형 국고채액티브 ETF 상품 자료](https://m.samsungfund.com/sheet/20231204/2ETFJ5_20231130.pdf) | 상품 자료 | 미확인 | 존속기한과 편입 채권 만기 매칭, 시장가격·매각 손실과 기대수익률 변동 |
| S17 | 삼성자산운용 | [KODEX 27-12 금융채(AA-이상)액티브 투자설명서](https://www.samsungfund.com/upload/invest/2ETFW5-A.pdf) | 투자설명서 | 2026-09-11 | 제2부 수익구조에서 YTM의 가중평균과 실제 성과 차이를 설명. 날짜는 같은 PDF의 간이투자설명서 작성기준일 |
| S18 | 삼성자산운용 | [Kodex ETF 투자기초가이드 8화 · 현물 ETF](https://www.samsungfund.com/etf/insight/guide/view08.do) | 교육 가이드 | 미확인 | 현물과 선물의 차이, 계약 교체와 롤오버 |
| S19 | 삼성자산운용 | [Kodex ETF 투자기초가이드 9화 · 합성 ETF](https://www.samsungfund.com/etf/insight/guide/view09.do) | 교육 가이드 | 미확인 | 스왑을 통한 지수 수익률 추종과 계약 상대방 신용위험 |
| S20 | 미래에셋증권 | [ETN 투자위험고지서](https://securities.miraeasset.com/hki/hki3051/n07.do) | 위험고지서 | 미확인 | ETF와 유사한 거래 방식에도 ETN에 발행사 신용위험이 있는 이유 |
| S21 | 삼성자산운용 | [미국 시장 휴장 안내 (2026-11-26)](https://www.samsungfund.com/etf/lounge/notice-view.do?no=81183) | 운용사 공지 | 2026-11-25 | 현지시장 휴장 중 iNAV 반영 한계와 호가·시장가격 괴리 |
| S22 | 삼성자산운용 | [Kodex ETF 투자기초가이드 10화 · 레버리지 ETF](https://www.samsungfund.com/etf/insight/guide/view10.do) | 교육 가이드 | 미확인 | 일간 배율과 여러 날의 누적 성과 차이 |
| S23 | 미래에셋증권 | [해외주식 소수단위 매매거래 설정약관](https://securities.miraeasset.com/public/hks4412/009/globalequity_decimal_terms.pdf) | 약관 | 2025-07-02 | 미국 상장 ETF 중 지정 종목의 소수단위 거래 허용. 날짜는 해당 약관의 시행일 |
| S24 | 미래에셋증권 | [해외주식 소수단위 매매거래 설명서](https://securities.miraeasset.com/hki/hki3032/n29.do) | 설명서 | 미확인 | 해외 소수단위 주문의 지정 종목과 서비스별 주문 방식 |

## 신규 FAQ별 출처 및 의미상 중복 검토

가까운 기존 FAQ는 삭제·통합 후보라는 뜻이 아니라 신규 항목의 차이를 검토할 때 대조한 질문입니다.

| 신규 ID | 사용자 질문 | 국내 투자자 적용 범위 | 주 출처 | 교차·보조 출처 | 대조한 기존 FAQ | 추가한 내용 |
|---|---|---|---|---|---|---|
| F026 | ETF 주문할 때 시장가와 지정가 중 뭐가 다른가요? | 국내 상장 ETF 일반 주문 | [S01](https://securities.miraeasset.com/hki/hki3032/n50.do) | [S03](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf) | F011·F014 | 일반 매매 절차나 스프레드 정의에서 다루지 않는 주문 가격과 체결 조건 |
| F027 | 한국에 상장된 ETF는 평소 몇 시부터 몇 시까지 거래돼요? | 한국거래소 정규장·평시 | [S02](https://m.samsungfund.com/etf/insight/guide/view02.do) | [S03](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf) | F011 | 매매 방법 대신 국내 정규장 운영 시간과 예외 |
| F028 | ETF가 오늘 팔렸는데 왜 출금 가능 금액에 바로 안 잡히나요? | 한국거래소 국내 상장 ETF 일반 결제 | [S03](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf) | [S01](https://securities.miraeasset.com/hki/hki3032/n50.do) | F011 | 주문과 체결 이후 결제·출금 시점 |
| F029 | 한국에 상장된 미국주식 ETF와 미국 거래소의 ETF는 사는 방법이 같나요? | 한국 투자자가 국내·해외에서 거래할 때 | [S04](https://trading.securities.miraeasset.com/hki/hki3032/n03.do) | [S02](https://m.samsungfund.com/etf/insight/guide/view02.do), [S09](https://m.samsungfund.com/etf/insight/guide/view07.do) | F011·F022 | 외국 자산에 투자하는지와 어느 거래소에 상장됐는지를 구분 |
| F030 | 중개형 ISA에서 미국 거래소에 상장된 ETF를 직접 살 수 있나요? | 국내 중개형 ISA | [S05](https://www.samsungfund.com/upload/kodex/newsroom/2026011317101936.pdf) | [S06](https://securities.miraeasset.com/hki/hki3032/n20.do) | F011·F025 | 계좌별 직접 거래 자격 |
| F031 | 연금저축이나 IRP에서 레버리지·인버스 ETF도 살 수 있나요? | 국내 연금저축·퇴직연금 | [S07](https://m.samsungfund.com/upload/kodex/newsroom/20261030155119262.pdf) | — | F023 | 상품의 수익 구조 대신 연금계좌 매수 가능 여부 |
| F032 | 국내에서 산 ETF는 어떤 상품이든 팔 때 세금이 없나요? | 국내 개인 일반계좌 | [S08](https://www.samsungfund.com/etf/insight/guide/view05.do) | [S06](https://securities.miraeasset.com/hki/hki3032/n20.do) | F016·F017 | 운용·거래 비용과 별개인 일반계좌의 매매차익 과세 구조 |
| F033 | ETF 세금 설명에 나오는 과표기준가격은 뭘 뜻하나요? | 국내 개인 일반계좌의 보유기간 과세 대상 | [S08](https://www.samsungfund.com/etf/insight/guide/view05.do) | — | F006·F007 | 순자산 평가나 시장 거래가격과 다른 과세 계산 기준 |
| F034 | ETF 이름에 H가 붙으면 환율 영향이 완전히 없어지나요? | 국내 상장 해외자산 ETF | [S09](https://m.samsungfund.com/etf/insight/guide/view07.do) | [S10](https://www.riseetf.co.kr/upload/cdn/2026/01/29/20260129cae05c619534480.pdf) | F022 | 환율 위험의 존재를 넘어 H 표기와 헤지 효과의 한계 |
| F035 | 월배당 ETF를 분배락일에 처음 사도 이번 분배금을 받나요? | 국내 상장 월분배 ETF의 일반 결제 | [S11](https://m.samsungfund.com/upload/kodex/newsroom/20260427141121713.pdf) | [S03](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf) | F018·F019 | 분배금의 정의나 지급 보장 대신 특정 회차의 수령 자격 |
| F036 | 분배금 받은 날 ETF 가격이 좀 빠졌는데 전부 손해인가요? | 국내 상장 현금 분배형 ETF | [S11](https://m.samsungfund.com/upload/kodex/newsroom/20260427141121713.pdf) | [S13](https://www.tigeretf.com/upload/etf/20250304090531000354.pdf) | F007·F018 | 순자산과 거래가격 차이의 원인 중 분배락 및 투자 손익 계산 |
| F037 | 이름에 TR이 붙었던 ETF가 왜 현금 분배금을 주기도 하나요? | 삼성자산운용 공지의 전환 대상 | [S12](https://m.samsungfund.com/etf/lounge/notice-view.do?no=67815) | — | F018·F019 | 현금 지급 여부와 구별되는 펀드 내부 재투자·정책 변경 |
| F038 | ETF에 적힌 분배율이 높으면 제 수익률도 그만큼 높다는 뜻인가요? | 국내 상장 ETF의 목표 분배율 표시 | [S13](https://www.tigeretf.com/upload/etf/20250304090531000354.pdf) | [S11](https://m.samsungfund.com/upload/kodex/newsroom/20260427141121713.pdf) | F019 | 지급 확실성 대신 분배율과 개인 투자 성과의 차이 |
| F039 | 가지고 있는 ETF가 상장폐지되면 투자금은 어떻게 되나요? | 국내 상장 ETF 해지 사례 | [S14](https://www.samsungfund.com/etf/lounge/notice-view.do?no=56253) | [S10](https://www.riseetf.co.kr/upload/cdn/2026/01/29/20260129cae05c619534480.pdf) | F021·F024 | 일반 손실·공시 설명을 넘어 상장폐지 후 정산 흐름 |
| F040 | 액티브 ETF는 지수 따라가는 ETF와 뭐가 달라요? | 국내 상장 ETF의 운용 유형 | [S15](https://www.tigeretf.com/upload/etf/20250228090901009939.pdf) | — | F004·F005 | 기초지수 정의나 운용사 역할이 아닌 두 운용 목표 비교 |
| F041 | 금리가 오르면 채권 ETF 가격은 왜 내려갈 수 있나요? | 국내 상장 채권형 ETF | [S15](https://www.tigeretf.com/upload/etf/20250228090901009939.pdf) | [S17](https://www.samsungfund.com/upload/invest/2ETFW5-A.pdf) | F021 | 일반 원금손실 안내보다 구체적인 금리와 채권 가격의 관계 |
| F042 | 만기가 있는 채권 ETF는 일반 채권 ETF와 무엇이 달라요? | 국내 상장 만기매칭 채권형 ETF | [S16](https://m.samsungfund.com/sheet/20231204/2ETFJ5_20231130.pdf) | [S14](https://www.samsungfund.com/etf/lounge/notice-view.do?no=56253) | F004·F025 | 추종지수나 일반 선택 기준에 없는 존속기한과 만기 매칭 전략 |
| F043 | 채권 ETF 화면에 표시되는 YTM이 제가 받는 확정 수익률인가요? | 국내 상장 채권형 ETF의 YTM 지표 | [S17](https://www.samsungfund.com/upload/invest/2ETFW5-A.pdf) | [S16](https://m.samsungfund.com/sheet/20231204/2ETFJ5_20231130.pdf) | F021·F025 | 확정 이익 여부를 넘어 표시 만기수익률의 해석 |
| F044 | 국제유가가 올랐는데 원유 ETF가 같은 폭으로 오르지 않는 이유는 뭔가요? | 국내 상장 선물형 ETF | [S18](https://www.samsungfund.com/etf/insight/guide/view08.do) | [S10](https://www.riseetf.co.kr/upload/cdn/2026/01/29/20260129cae05c619534480.pdf) | F004·F010 | 일반 추종지수·추적오차 대신 선물 계약 교체의 영향을 설명 |
| F045 | 이름에 합성이라고 붙은 ETF는 어떤 위험이 더 있나요? | 국내 상장 합성 ETF | [S19](https://www.samsungfund.com/etf/insight/guide/view09.do) | [S15](https://www.tigeretf.com/upload/etf/20250228090901009939.pdf) | F021·F025 | 일반 투자 위험 대신 스왑 계약의 거래상대방 위험 |
| F046 | 이름이 비슷한 ETF와 ETN은 같은 상품인가요? | 국내 상장 ETF·ETN | [S20](https://securities.miraeasset.com/hki/hki3051/n07.do) | — | F002·F003 | 개별 주식이나 비상장 펀드가 아닌 ETN과 비교 |
| F047 | 미국 시장이 쉬는 날인데 한국의 미국주식 ETF 가격은 왜 움직여요? | 한국만 개장한 경우의 국내 상장 해외 ETF | [S21](https://www.samsungfund.com/etf/lounge/notice-view.do?no=81183) | [S10](https://www.riseetf.co.kr/upload/cdn/2026/01/29/20260129cae05c619534480.pdf) | F007·F008·F009 | 가격지표 정의 대신 해외 휴장과 국내 개장의 비동시 상황 |
| F048 | 지수가 이틀 만에 제자리면 2배 레버리지 ETF도 제자리인가요? | 일간 2배 추종의 가상 계산 | [S22](https://www.samsungfund.com/etf/insight/guide/view10.do) | — | F023 | 기존의 일간 배율 개념을 적용하는 원점 회귀 계산 사례 |
| F049 | 미국에 상장된 ETF도 1주보다 적게 살 수 있어요? | 국내 증권사의 미국 상장 ETF 소수단위 거래 | [S23](https://securities.miraeasset.com/public/hks4412/009/globalequity_decimal_terms.pdf) | [S24](https://securities.miraeasset.com/hki/hki3032/n29.do) | F012 | 국내 기본 거래 단위와 구분되는 해외 상장 ETF의 별도 서비스 |
| F050 | 커버드콜 ETF는 분배금을 만들면서 어떤 대가를 치르나요? | 국내 상장 커버드콜 ETF의 구조 | [S13](https://www.tigeretf.com/upload/etf/20250304090531000354.pdf) | — | F018·F019 | 분배금 자체의 정의 대신 옵션 프리미엄과 상승·하락 위험의 관계 |

## 데이터 경로와 DB 반영

- 앱은 읽기 전용으로 PostgreSQL `faq`를 우선 조회하며, DB 조회 오류 시 [원본 CSV](../data/source/FAQ.csv)를 표시합니다. 원본 CSV의 데이터 열은 `faq_id, category, question, answer, keywords, source_name, source_url, source_date, verified_at`입니다.
- 기존 [build_database.py](../build_database.py)는 CSV를 검사하고 FAQ·상품을 ID 기준으로 한 트랜잭션에서 추가하거나 갱신합니다. 동일한 행은 건너뛰고 CSV에 없는 기존 DB 행은 보존합니다. 기존 데이터에 영향이 없도록 승인된 개발 DB에서 F026–F050의 충돌 여부와 상품 CSV의 변경 가능성을 먼저 확인하세요.
- 개발 DB의 대상과 백업을 확인한 뒤 `python build_database.py`로 적재합니다. 출력의 FAQ 처리 건수와 변경 건수, DB 전체 건수를 별도로 확인합니다. CSV 밖의 기존 FAQ가 있을 수 있으므로 DB의 총 건수는 50보다 클 수 있습니다.
- 그다음 `python build_embeddings.py`를 실행합니다. 이 스크립트는 FAQ와 상품을 대상으로 내용 해시와 갱신 시각을 비교하며, 모델과 차원이 일치하는 변경 문서의 벡터만 교체합니다. 한 트랜잭션에서 처리하므로 오류 시 롤백되며, OpenAI 호출 동안 잠금과 비용이 발생할 수 있어 승인된 개발 DB에서 검증합니다.
- 기존 벡터 검색은 `text-embedding-3-small` 1,536차원과 PostgreSQL pgvector의 코사인 유사도를 사용합니다. 최신 원본에 대응하는 벡터만 대상으로 `FAQ_MIN_SIMILARITY` 이상 상위 3개를 반환합니다. 설정을 바꾸지 않았으며 이 변경에는 데이터 적재 및 임베딩 실행을 포함하지 않았습니다.
- 비밀번호 과거 노출의 교체 상태는 미확인입니다. 검색 평가 데이터셋·정확도 측정 및 코드 정리는 후속 단계입니다.
