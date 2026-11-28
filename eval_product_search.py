"""상품명 검색 방식 비교 평가.

같은 평가 질문으로 아래 방식을 비교합니다. DB 없이 data/source/etf_products.csv만 사용합니다.

1. 기존 규칙      : 오타 대응 전 product_catalog 규칙 (정확히 일치·포함 관계)
2. 규칙 + 오타    : 지금 product_catalog.match_products (편집 거리 + 확인 요청)
3. BM25          : 상품명을 글자 2개씩 잘라 BM25로 1등 선택
4. 벡터 (선택)    : OpenAI 임베딩 코사인 유사도로 1등 선택
5. 하이브리드 (선택): BM25와 벡터 점수를 반반 섞어 1등 선택

    py eval_product_search.py            # 1~3
    py eval_product_search.py --vector   # 4~5 포함 (OpenAI API 호출, 약 60개 짧은 문장)

판정 기준
- 상품이 정해진 질문: 그 상품으로 연결되면 정답
- "확인" 질문: 추측하지 않고 사용자에게 확인을 요청하면 정답
- "없음" 질문(DB에 없는 상품): 어떤 상품에도 연결하지 않으면 정답
- 오인식: 정답이 아닌 상품으로 연결한 경우 (가장 위험한 실수)
"""
import csv
import math
import sys
from collections import Counter
from pathlib import Path

from src.services.product_catalog import (
    match_products,
    normalize_product_key,
)

BASE_DIR = Path(__file__).resolve().parent
PRODUCTS_CSV = BASE_DIR / "data" / "source" / "etf_products.csv"
ASK = "확인"
NONE = "없음"

# (분류, 질문 속 상품 표현, 기대 결과: 종목코드 / ASK / NONE)
CASES = [
    ("정확한 이름", "KODEX 200", "069500"),
    ("정확한 이름", "TIGER 미국S&P500", "360750"),
    ("정확한 이름", "ACE KRX금현물", "411060"),
    ("띄어쓰기·대소문자", "kodex200", "069500"),
    ("띄어쓰기·대소문자", "tiger 미국 나스닥 100", "133690"),
    ("띄어쓰기·대소문자", "KODEX 200 ETF", "069500"),
    ("종목코드", "069500", "069500"),
    ("종목코드", "360750", "360750"),
    ("한글 브랜드", "코덱스 200", "069500"),
    ("한글 브랜드", "타이거 미국S&P500", "360750"),
    ("한글 브랜드", "하나로 200", "293180"),
    ("영문 오타", "COXEX200", "069500"),
    ("영문 오타", "KODXE 200", "069500"),
    ("영문 오타", "TIGRE 미국나스닥100", "133690"),
    ("영문 오타", "TIGER 미국SNP500", "360750"),
    ("영문 오타", "HANAR0 200", ASK),
    ("한글 오타", "코덱쓰 200", "069500"),
    ("한글 오타", "솔 미국S&P500", "433330"),
    ("한글 오타", "에이스 미국배당다우존슨", "402970"),
    ("부분 표현", "에이스 금현물", "411060"),
    ("부분 표현", "ACE 미국나스닥", "367380"),
    ("부분 표현", "타이거 나스닥", ASK),
    ("부분 표현", "ACE 빅테크", ASK),
    ("모호한 표현", "200", ASK),
    ("모호한 표현", "나스닥100", ASK),
    ("모호한 표현", "S&P500", ASK),
    ("모호한 표현", "미국S&P500", ASK),
    # 숫자 치환은 실제 미등록 상품일 수 있으므로 다른 상품 후보로 바꾸지 않습니다.
    ("숫자가 다른 표현", "KODEX 300", NONE),
    ("DB에 없는 상품", "KODEX 레버리지", NONE),
    ("DB에 없는 상품", "KODEX 200선물인버스2X", NONE),
    ("DB에 없는 상품", "TIGER 차이나전기차SOLACTIVE", NONE),
    ("DB에 없는 상품", "삼성전자", NONE),
    ("DB에 없는 상품", "069501", NONE),
    ("DB에 없는 상품", "달토끼 우주여행 ETF", NONE),
]


def load_products():
    with open(PRODUCTS_CSV, encoding="utf-8-sig") as file:
        return [
            {key: row[key] for key in ("product_code", "product_name", "asset_manager")}
            for row in csv.DictReader(file)
        ]


# ---------------------------------------------------------------------------
# 각 방식은 (결정, 종목코드) 를 돌려줍니다. 결정: "연결" / "확인" / "없음"
# ---------------------------------------------------------------------------

def legacy_rules(query, products):
    """오타 대응을 넣기 전 product_catalog의 점수 규칙 그대로."""
    normalized_query = normalize_product_key(query)
    scored = []
    for product in products:
        code = product["product_code"].upper()
        name = normalize_product_key(product["product_name"])
        if normalized_query == code:
            scored.append((100, product))
        elif normalized_query == name:
            scored.append((95, product))
        elif name and name in normalized_query:
            scored.append((80, product))
        elif normalized_query and normalized_query in name:
            scored.append((70, product))
    if not scored:
        return NONE, None
    best = max(score for score, _ in scored)
    winners = [product for score, product in scored if score == best]
    if len(winners) > 1:
        return ASK, None
    return "연결", winners[0]["product_code"]


def current_rules(query, products):
    result = match_products(query, products)
    if result["success"]:
        return "연결", result["product"]["product_code"]
    if result.get("error_type") == "ambiguous_product":
        return ASK, None
    return NONE, None


def _bigrams(text):
    key = normalize_product_key(text)
    return [key[i:i + 2] for i in range(len(key) - 1)] or [key]


class Bm25:
    def __init__(self, documents, k1=1.2, b=0.75):
        self.documents = [_bigrams(doc) for doc in documents]
        self.average_length = sum(map(len, self.documents)) / len(self.documents)
        self.document_frequency = Counter(
            term for doc in self.documents for term in set(doc)
        )
        self.k1, self.b = k1, b

    def scores(self, query):
        total = len(self.documents)
        results = []
        for doc in self.documents:
            counts = Counter(doc)
            score = 0.0
            for term in _bigrams(query):
                if term not in counts:
                    continue
                frequency = self.document_frequency[term]
                idf = math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
                tf = counts[term]
                score += idf * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * len(doc) / self.average_length)
                )
            results.append(score)
        return results


def _pick_top(scores, products):
    best = max(range(len(scores)), key=lambda i: scores[i])
    if scores[best] <= 0:
        return NONE, None
    return "연결", products[best]["product_code"]


def _cosine(left, right):
    dot = sum(a * b for a, b in zip(left, right))
    return dot / (math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right)))


def _min_max(values):
    low, high = min(values), max(values)
    return [(value - low) / (high - low) if high > low else 0.0 for value in values]


def evaluate(name, decide):
    correct = 0
    misrecognized = []
    wrong = []
    for category, query, expected in CASES:
        decision, code = decide(query)
        if expected == ASK:
            ok = decision == ASK
        elif expected == NONE:
            ok = decision == NONE
        else:
            ok = decision == "연결" and code == expected
        correct += ok
        if decision == "연결" and code != expected:
            misrecognized.append(f"{query} → {code}")
        elif not ok:
            wrong.append(f"{query} ({decision})")
    return {
        "name": name,
        "correct": correct,
        "misrecognized": misrecognized,
        "wrong": wrong,
    }


def main():
    products = load_products()
    names = [product["product_name"] for product in products]
    bm25 = Bm25(names)

    methods = [
        ("기존 규칙", lambda q: legacy_rules(q, products)),
        ("규칙 + 오타 대응", lambda q: current_rules(q, products)),
        ("BM25", lambda q: _pick_top(bm25.scores(q), products)),
    ]

    if "--vector" in sys.argv[1:]:
        from src.services.embeddings import embed_texts

        queries = [query for _, query, _ in CASES]
        vectors = embed_texts(names + queries)
        name_vectors = vectors[:len(names)]
        query_vectors = dict(zip(queries, vectors[len(names):]))

        def vector_scores(query):
            return [_cosine(query_vectors[query], vector) for vector in name_vectors]

        def hybrid_scores(query):
            lexical = _min_max(bm25.scores(query))
            semantic = _min_max(vector_scores(query))
            return [0.5 * a + 0.5 * b for a, b in zip(lexical, semantic)]

        methods += [
            ("벡터", lambda q: _pick_top(vector_scores(q), products)),
            ("하이브리드(BM25+벡터)", lambda q: _pick_top(hybrid_scores(q), products)),
        ]

    total = len(CASES)
    print(f"평가 질문 {total}개 (상품 {len(products)}개)\n")
    print(f"{'방식':<22}{'정답률':>10}{'오인식':>8}")
    results = [evaluate(name, decide) for name, decide in methods]
    for result in results:
        rate = f"{result['correct']}/{total} ({result['correct'] / total:.0%})"
        print(f"{result['name']:<22}{rate:>10}{len(result['misrecognized']):>8}")

    for result in results:
        print(f"\n[{result['name']}]")
        if result["misrecognized"]:
            print("  오인식:", "; ".join(result["misrecognized"]))
        if result["wrong"]:
            print("  놓침:", "; ".join(result["wrong"]))


if __name__ == "__main__":
    main()
