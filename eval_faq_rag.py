"""Compare FAQ embedding models and retrieval parameters without modifying PostgreSQL."""

import argparse
import csv
import json
import math
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.db.postgres import BASE_DIR
from src.services.embeddings import document_text


FAQ_PATH = BASE_DIR / "data" / "source" / "FAQ.csv"
QUESTION_PATH = BASE_DIR / "data" / "evaluation" / "faq_rag_questions.json"
RESULT_DIR = BASE_DIR / "data" / "evaluation" / "results"
MODEL_CONFIGS = (
    ("text-embedding-3-small", 1536),
    ("text-embedding-3-large", 1536),
)
TOP_K_VALUES = (1, 3, 5)
THRESHOLDS = tuple(round(value / 100, 2) for value in range(20, 71, 5))


def cosine(left, right):
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def faq_semantic_text(row):
    return "\n".join((
        f"FAQ 질문: {row.get('question', '')}",
        f"핵심어: {row.get('keywords', '')}",
        f"검증 답변: {row.get('answer', '')}",
    ))


def embed(client, model, dimensions, texts):
    vectors = []
    for offset in range(0, len(texts), 64):
        batch = texts[offset:offset + 64]
        response = client.embeddings.create(
            model=model,
            dimensions=dimensions,
            input=batch,
        )
        items = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in items)
    return vectors


def ranked_results(query_vector, faq_rows, faq_vectors):
    ranked = [
        (row["faq_id"], cosine(query_vector, vector))
        for row, vector in zip(faq_rows, faq_vectors)
    ]
    return sorted(ranked, key=lambda item: (-item[1], item[0]))


def retrieval_metrics(rankings, questions):
    positives = [item for item in questions if item["kind"] == "positive"]
    metrics = {}
    for top_k in TOP_K_VALUES:
        hits = 0
        reciprocal_rank = 0.0
        for question in positives:
            expected = set(question["expected_faq_ids"])
            ranking = rankings[question["id"]][:top_k]
            matched_rank = next(
                (index for index, (faq_id, _) in enumerate(ranking, 1) if faq_id in expected),
                None,
            )
            if matched_rank:
                hits += 1
                reciprocal_rank += 1 / matched_rank
        metrics[top_k] = {
            "hit_rate": hits / len(positives),
            "mrr": reciprocal_rank / len(positives),
        }
    return metrics


def threshold_metrics(rankings, questions):
    positives = [item for item in questions if item["kind"] == "positive"]
    negatives = [item for item in questions if item["kind"] == "negative"]
    rows = []
    for threshold in THRESHOLDS:
        positive_hit_at_1 = 0
        positive_hit_at_3 = 0
        negative_rejected = 0
        for question in positives:
            expected = set(question["expected_faq_ids"])
            accepted = [
                faq_id
                for faq_id, score in rankings[question["id"]]
                if score >= threshold
            ][:3]
            positive_hit_at_1 += bool(accepted and accepted[0] in expected)
            positive_hit_at_3 += bool(expected.intersection(accepted))
        for question in negatives:
            _, score = rankings[question["id"]][0]
            if score < threshold:
                negative_rejected += 1
        positive_accuracy_at_1 = positive_hit_at_1 / len(positives)
        positive_accuracy_at_3 = positive_hit_at_3 / len(positives)
        negative_rejection = negative_rejected / len(negatives)
        rows.append({
            "threshold": threshold,
            "positive_accuracy_at_1": positive_accuracy_at_1,
            "positive_accuracy_at_3": positive_accuracy_at_3,
            "negative_rejection": negative_rejection,
            "balanced_accuracy": (positive_accuracy_at_3 + negative_rejection) / 2,
            "false_accept_rate": 1 - negative_rejection,
        })
    return rows


def best_threshold(rows):
    return max(
        rows,
        key=lambda row: (
            row["balanced_accuracy"],
            row["positive_accuracy_at_3"],
            row["positive_accuracy_at_1"],
            -row["false_accept_rate"],
            row["threshold"],
        ),
    )


def evaluate_live_database(questions):
    from src.services.vector_search import search_faq_vectors

    positives = [item for item in questions if item["kind"] == "positive"]
    negatives = [item for item in questions if item["kind"] == "negative"]
    hit_at_1 = 0
    hit_at_3 = 0
    negative_rejections = 0
    failures = []

    for question in questions:
        rows = search_faq_vectors(question["query"])
        retrieved = [row["faq_id"] for row in rows]
        if question["kind"] == "positive":
            expected = set(question["expected_faq_ids"])
            hit_at_1 += bool(retrieved and retrieved[0] in expected)
            hit_at_3 += bool(expected.intersection(retrieved[:3]))
            if not expected.intersection(retrieved[:3]):
                failures.append((question["id"], question["query"], retrieved))
        else:
            negative_rejections += not retrieved
            if retrieved:
                failures.append((question["id"], question["query"], retrieved))

    print(f"live hit@1={hit_at_1 / len(positives):.1%}")
    print(f"live hit@3={hit_at_3 / len(positives):.1%}")
    print(f"live negative rejection={negative_rejections / len(negatives):.1%}")
    for item_id, query, retrieved in failures:
        print(f"FAIL {item_id}: {query} -> {retrieved}")
    return not failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--live-db", action="store_true")
    parser.add_argument(
        "--document-profile",
        choices=("full", "semantic"),
        default="full",
    )
    args = parser.parse_args()

    with FAQ_PATH.open(encoding="utf-8-sig", newline="") as source:
        faq_rows = list(csv.DictReader(source))
    questions = json.loads(QUESTION_PATH.read_text(encoding="utf-8"))
    faq_texts = [
        faq_semantic_text(row) if args.document_profile == "semantic"
        else document_text(row)
        for row in faq_rows
    ]

    if args.live_db:
        return 0 if evaluate_live_database(questions) else 1

    if max(map(len, faq_texts)) > 1000:
        raise ValueError("FAQ document exceeds the current 1000-character chunk size")

    selected = [
        config for config in MODEL_CONFIGS
        if not args.models or config[0] in args.models
    ]
    if not selected:
        raise ValueError("No supported model selected")

    load_dotenv(BASE_DIR / ".env")
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_path = RESULT_DIR / f"faq_rag_details_{timestamp}.csv"
    summary_path = RESULT_DIR / f"faq_rag_summary_{timestamp}.json"
    details = []
    summaries = []

    with OpenAI(timeout=60, max_retries=2) as client:
        for model, dimensions in selected:
            model_started = time.perf_counter()
            faq_vectors = embed(client, model, dimensions, faq_texts)
            query_vectors = embed(
                client,
                model,
                dimensions,
                [item["query"] for item in questions],
            )
            rankings = {
                question["id"]: ranked_results(vector, faq_rows, faq_vectors)
                for question, vector in zip(questions, query_vectors)
            }
            retrieval = retrieval_metrics(rankings, questions)
            thresholds = threshold_metrics(rankings, questions)
            selected_threshold = best_threshold(thresholds)

            for question in questions:
                ranking = rankings[question["id"]]
                details.append({
                    "model": model,
                    "dimensions": dimensions,
                    "id": question["id"],
                    "kind": question["kind"],
                    "query": question["query"],
                    "expected_faq_ids": "|".join(question["expected_faq_ids"]),
                    "top1_faq_id": ranking[0][0],
                    "top1_score": round(ranking[0][1], 6),
                    "top3_faq_ids": "|".join(item[0] for item in ranking[:3]),
                })

            summary = {
                "model": model,
                "dimensions": dimensions,
                "document_profile": args.document_profile,
                "faq_count": len(faq_rows),
                "evaluation_questions": len(questions),
                "positive_questions": sum(item["kind"] == "positive" for item in questions),
                "negative_questions": sum(item["kind"] == "negative" for item in questions),
                "max_document_characters": max(map(len, faq_texts)),
                "chunk_size": 1000,
                "chunk_overlap": 100,
                "chunks_per_faq": 1,
                "evaluation_seconds": round(time.perf_counter() - model_started, 4),
                "retrieval": {str(key): value for key, value in retrieval.items()},
                "threshold_sweep": thresholds,
                "selected_threshold": selected_threshold,
            }
            summaries.append(summary)
            print(
                f"{model}: hit@1={retrieval[1]['hit_rate']:.1%}, "
                f"hit@3={retrieval[3]['hit_rate']:.1%}, "
                f"best_threshold={selected_threshold['threshold']:.2f}, "
                f"balanced_accuracy={selected_threshold['balanced_accuracy']:.1%}, "
                f"seconds={summary['evaluation_seconds']:.2f}"
            )

    with detail_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=details[0].keys())
        writer.writeheader()
        writer.writerows(details)
    summary_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"details={detail_path}")
    print(f"summary={summary_path}")


if __name__ == "__main__":
    raise SystemExit(main())
