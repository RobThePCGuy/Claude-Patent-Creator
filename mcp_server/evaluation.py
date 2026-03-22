#!/usr/bin/env python3
"""
RAGAS Evaluation Framework for MPEP RAG System
Measures retrieval quality, faithfulness, and answer relevance
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from datasets import Dataset  # type: ignore[import-untyped]
    from ragas import evaluate  # type: ignore[import-untyped]
    from ragas.metrics import (  # type: ignore[import-untyped]
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    RAGAS_AVAILABLE = True
except ImportError:
    Dataset = None  # type: ignore[assignment,misc]
    evaluate = None  # type: ignore[assignment]
    answer_relevancy = None  # type: ignore[assignment]
    context_precision = None  # type: ignore[assignment]
    context_recall = None  # type: ignore[assignment]
    faithfulness = None  # type: ignore[assignment]
    print(
        "Warning: RAGAS not available. Install with: pip install ragas datasets",
        file=sys.stderr,
    )
    RAGAS_AVAILABLE = False


class MPEPEvaluator:
    """Evaluates MPEP RAG system using RAGAS metrics"""

    def __init__(self):
        self.results_dir = Path(__file__).parent / "evaluation_results"
        self.results_dir.mkdir(exist_ok=True)
        self.test_dataset_file = Path(__file__).parent / "test_dataset.json"

    def create_test_dataset(self) -> List[Dict[str, Any]]:
        """Create golden dataset of MPEP questions for evaluation"""
        test_cases = [
            {
                "question": "What are the claim definiteness requirements under 35 USC 112(b)?",
                "ground_truth": "Under 35 USC 112(b), the specification shall conclude with one or more claims particularly pointing out and distinctly claiming the subject matter which the inventor regards as the invention. Claims must be definite and clear.",
            },
            {
                "question": "What is required for written description under 35 USC 112(a)?",
                "ground_truth": "35 USC 112(a) requires that the specification contain a written description of the invention in such full, clear, concise, and exact terms as to enable any person skilled in the art to make and use the same.",
            },
            {
                "question": "What are the requirements for claim antecedent basis?",
                "ground_truth": "Claim antecedent basis requires that when a claim refers to 'the' or 'said' element, that element must have been previously introduced in the claim using 'a' or 'an'. This ensures clarity and definiteness.",
            },
            {
                "question": "What is the enablement requirement in patent law?",
                "ground_truth": "The enablement requirement under 35 USC 112(a) mandates that the specification must teach those skilled in the art how to make and use the full scope of the claimed invention without undue experimentation.",
            },
            {
                "question": "What are the requirements for patent claim format?",
                "ground_truth": "Patent claims must be in the form of a single sentence, begin with a capital letter, end with a period, use consistent terminology, and include a preamble, transitional phrase, and body that clearly defines the invention.",
            },
            {
                "question": "What is best mode requirement?",
                "ground_truth": "The best mode requirement under 35 USC 112(a) required inventors to disclose the best way they knew to practice their invention at the time of filing. This requirement still exists but failure to disclose is no longer a basis for invalidity under AIA.",
            },
            {
                "question": "What are the requirements for dependent claims?",
                "ground_truth": "A dependent claim must refer back to and further limit a previous claim (independent or dependent). It incorporates all limitations of the claim to which it refers and must be construed to include all limitations of the referenced claim.",
            },
            {
                "question": "What is the doctrine of claim differentiation?",
                "ground_truth": "The doctrine of claim differentiation presumes that each claim in a patent has a different scope. If a limitation appears in a dependent claim, that limitation is presumed to be absent from the independent claim.",
            },
            {
                "question": "What are functional claim limitations?",
                "ground_truth": "Functional claim limitations define an element by what it does rather than what it is. Under 35 USC 112(f), means-plus-function claims are interpreted to cover the corresponding structure described in the specification and equivalents thereof.",
            },
            {
                "question": "What is required for a proper abstract?",
                "ground_truth": "The abstract must be a concise statement of the technical disclosure, preferably 150 words or less. It should enable the reader to quickly determine the nature and gist of the technical disclosure without being a substitute for claims.",
            },
        ]

        with open(self.test_dataset_file, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, indent=2)

        print(f"Created test dataset with {len(test_cases)} questions", file=sys.stderr)
        return test_cases

    def load_test_dataset(self) -> List[Dict[str, Any]]:
        """Load existing test dataset or create new one"""
        if self.test_dataset_file.exists():
            with open(self.test_dataset_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return self.create_test_dataset()

    def evaluate_rag_pipeline(
        self, mpep_index, test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Evaluate RAG pipeline using RAGAS metrics"""
        if not RAGAS_AVAILABLE:
            return {"error": "RAGAS not installed. Install with: pip install ragas datasets"}

        if test_cases is None:
            test_cases = self.load_test_dataset()

        # Prepare evaluation data
        questions = []
        ground_truths = []
        contexts_list = []
        answers = []

        print(f"Evaluating {len(test_cases)} test cases...", file=sys.stderr)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\rProcessing {i}/{len(test_cases)}", end="", file=sys.stderr)

            question = test_case["question"]
            ground_truth = test_case["ground_truth"]

            # Retrieve contexts using RAG
            results = mpep_index.search(question, top_k=5)
            contexts = [r["text"] for r in results]

            # For now, use concatenated contexts as answer
            # In real scenario, this would be LLM-generated answer
            answer = " ".join(contexts[:2])

            questions.append(question)
            ground_truths.append(ground_truth)
            contexts_list.append(contexts)
            answers.append(answer)

        print("\n", file=sys.stderr)

        # Create dataset for RAGAS
        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
            "ground_truth": ground_truths,
        }

        dataset = Dataset.from_dict(data)  # type: ignore[union-attr]

        # Evaluate with RAGAS metrics
        print("Running RAGAS evaluation...", file=sys.stderr)
        result = evaluate(  # type: ignore[misc]
            dataset,
            metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
        )

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"evaluation_{timestamp}.json"

        evaluation_results = {
            "timestamp": timestamp,
            "num_test_cases": len(test_cases),
            "metrics": {
                "context_precision": float(result["context_precision"]),
                "context_recall": float(result["context_recall"]),
                "faithfulness": float(result["faithfulness"]),
                "answer_relevancy": float(result["answer_relevancy"]),
            },
            "test_cases": test_cases,
        }

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(evaluation_results, f, indent=2)

        print("\nEvaluation Results:", file=sys.stderr)
        print(f"Context Precision: {result['context_precision']:.3f}", file=sys.stderr)
        print(f"Context Recall: {result['context_recall']:.3f}", file=sys.stderr)
        print(f"Faithfulness: {result['faithfulness']:.3f}", file=sys.stderr)
        print(f"Answer Relevancy: {result['answer_relevancy']:.3f}", file=sys.stderr)
        print(f"\nResults saved to: {results_file}", file=sys.stderr)

        return evaluation_results

    def compare_evaluations(self, baseline_file: str, current_file: str) -> Dict[str, Any]:
        """Compare two evaluation runs to measure improvement"""
        with open(baseline_file, "r") as f:
            baseline = json.load(f)
        with open(current_file, "r") as f:
            current = json.load(f)

        comparison = {
            "baseline_timestamp": baseline["timestamp"],
            "current_timestamp": current["timestamp"],
            "improvements": {},
        }

        for metric in [
            "context_precision",
            "context_recall",
            "faithfulness",
            "answer_relevancy",
        ]:
            baseline_val = baseline["metrics"][metric]
            current_val = current["metrics"][metric]
            if baseline_val == 0:
                improvement = float('inf') if current_val > 0 else 0.0
            else:
                improvement = ((current_val - baseline_val) / baseline_val) * 100

            comparison["improvements"][metric] = {
                "baseline": baseline_val,
                "current": current_val,
                "improvement_pct": round(improvement, 2),
            }

        return comparison


def main():
    """Run evaluation from command line"""
    import argparse

    from server import mpep_index  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="Evaluate MPEP RAG System")
    parser.add_argument("--create-dataset", action="store_true", help="Create test dataset")
    parser.add_argument("--run-eval", action="store_true", help="Run evaluation")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BASELINE", "CURRENT"),
        help="Compare two evaluations",
    )
    args = parser.parse_args()

    evaluator = MPEPEvaluator()

    if args.create_dataset:
        evaluator.create_test_dataset()
        print("Test dataset created")

    elif args.run_eval:
        if not RAGAS_AVAILABLE:
            print(
                "Error: RAGAS not installed. Install with: pip install ragas datasets",
                file=sys.stderr,
            )
            sys.exit(1)

        print("Loading MPEP index...", file=sys.stderr)
        mpep_index.build_index()  # type: ignore[union-attr]
        evaluator.evaluate_rag_pipeline(mpep_index)

    elif args.compare:
        comparison = evaluator.compare_evaluations(args.compare[0], args.compare[1])
        print(json.dumps(comparison, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
