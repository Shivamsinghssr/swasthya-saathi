"""
eval/evaluate.py

Evaluation harness for Swasthya Saathi.

Tests agent quality against golden Q&A pairs — questions where we know
what a good answer should contain.

Usage:
    cd backend
    python eval/evaluate.py                    # run all evals
    python eval/evaluate.py --tool symptom     # run only symptom tests
    python eval/evaluate.py --verbose          # show full responses

Output:
    eval/results/eval_YYYY-MM-DD_HH-MM.json   # saved results

Metrics:
    - Pass rate: % of tests where expected keywords appear in response
    - Tool accuracy: % of tests where correct tool was called
    - Latency: average response time per query
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage


# ── Golden Test Cases ──────────────────────────────────────────────────────────
# Format:
#   query:         User's input (Hindi or English)
#   expected_tool: Which tool the agent should call
#   must_contain:  Keywords that MUST appear in the response (case-insensitive)
#   must_not_contain: Keywords that should NOT appear (hallucination check)

GOLDEN_CASES = [

    # ── Symptom Checker ───────────────────────────────────────────────────────
    {
        "id": "S01",
        "category": "symptom",
        "query": "mujhe 3 din se bukhar hai",
        "expected_tool": "symptom_checker",
        "must_contain": ["paracetamol", "paani", "doctor"],
        "must_not_contain": ["I don't know", "mujhe nahi pata"],
        "description": "Basic fever query"
    },
    {
        "id": "S02",
        "category": "symptom",
        "query": "मुझे दस्त हो रहे हैं और पेट में दर्द है",
        "expected_tool": "symptom_checker",
        "must_contain": ["ors", "paani", "namak"],
        "must_not_contain": [],
        "description": "Diarrhea query in Devanagari"
    },
    {
        "id": "S03",
        "category": "symptom",
        "query": "mujhe khansi aa rahi hai 1 hafte se",
        "expected_tool": "symptom_checker",
        "must_contain": ["khansi", "doctor"],
        "must_not_contain": [],
        "description": "Persistent cough"
    },
    {
        "id": "S04",
        "category": "symptom",
        "query": "meri aankhein aur twacha peeli ho gayi hai",
        "expected_tool": "symptom_checker",
        "must_contain": ["peeli", "liver", "doctor"],
        "must_not_contain": [],
        "description": "Jaundice symptoms"
    },
    {
        "id": "S05",
        "category": "symptom",
        "query": "mujhe tez bukhar hai aur kaanpna ho raha hai",
        "expected_tool": "symptom_checker",
        "must_contain": ["malaria", "doctor"],
        "must_not_contain": [],
        "description": "Malaria symptoms — fever with chills"
    },

    # ── Medicine Explainer ────────────────────────────────────────────────────
    {
        "id": "M01",
        "category": "medicine",
        "query": "Paracetamol kaise leni chahiye?",
        "expected_tool": "medicine_explainer",
        "must_contain": ["500", "din", "baar"],
        "must_not_contain": [],
        "description": "Paracetamol dosage"
    },
    {
        "id": "M02",
        "category": "medicine",
        "query": "ORS ka ghol kaise banate hain?",
        "expected_tool": "medicine_explainer",
        "must_contain": ["paani", "namak", "cheeni"],
        "must_not_contain": [],
        "description": "ORS preparation"
    },
    {
        "id": "M03",
        "category": "medicine",
        "query": "iron tablet kab leni chahiye?",
        "expected_tool": "medicine_explainer",
        "must_contain": ["iron", "khane"],
        "must_not_contain": [],
        "description": "Iron tablet timing"
    },
    {
        "id": "M04",
        "category": "medicine",
        "query": "Metformin ke side effects kya hain?",
        "expected_tool": "medicine_explainer",
        "must_contain": ["metformin", "diabetes"],
        "must_not_contain": [],
        "description": "Metformin side effects"
    },

    # ── Scheme Checker ────────────────────────────────────────────────────────
    {
        "id": "SC01",
        "category": "scheme",
        "query": "Ayushman Bharat kya hai aur mujhe kaise milega?",
        "expected_tool": "scheme_checker",
        "must_contain": ["ayushman", "5 lakh", "card"],
        "must_not_contain": [],
        "description": "Ayushman Bharat eligibility"
    },
    {
        "id": "SC02",
        "category": "scheme",
        "query": "pregnant mahila ko kya government schemes milti hain?",
        "expected_tool": "scheme_checker",
        "must_contain": ["jsy", "prasav"],
        "must_not_contain": [],
        "description": "Maternity schemes"
    },
    {
        "id": "SC03",
        "category": "scheme",
        "query": "sarkari aspatal mein kya free milta hai?",
        "expected_tool": "scheme_checker",
        "must_contain": ["muft", "free", "nhm"],
        "must_not_contain": [],
        "description": "NHM free services"
    },

    # ── Health Center Locator ─────────────────────────────────────────────────
    {
        "id": "H01",
        "category": "health_center",
        "query": "Varanasi mein sarkari aspatal kahan hai?",
        "expected_tool": "health_center_locator",
        "must_contain": ["varanasi", "phc"],
        "must_not_contain": [],
        "description": "PHC in Varanasi"
    },
    {
        "id": "H02",
        "category": "health_center",
        "query": "Patna mein doctor kahan milega?",
        "expected_tool": "health_center_locator",
        "must_contain": ["patna"],
        "must_not_contain": [],
        "description": "Health center in Patna"
    },

    # ── Multi-tool (complex queries) ──────────────────────────────────────────
    {
        "id": "MT01",
        "category": "multi",
        "query": "mujhe bukhar hai aur doctor ne Paracetamol di hai, kya sarkari aspatal mein free milegi?",
        "expected_tool": None,  # Multiple tools expected
        "must_contain": ["paracetamol", "free"],
        "must_not_contain": [],
        "description": "Multi-tool: symptom + medicine + scheme"
    },
]


# ── Evaluator ─────────────────────────────────────────────────────────────────

class Evaluator:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._setup()

    def _setup(self):
        """Initialize tools and agent — same as production startup."""
        print("⚙️  Initializing agent...")
        from rag.indexer import load_or_build_indexes
        from agent.tools import init_tools
        from agent.graph import get_graph

        retrievers, health_centers = load_or_build_indexes()
        init_tools(
            symptom_retriever  = retrievers["symptoms"],
            medicine_retriever = retrievers["medicines"],
            scheme_retriever   = retrievers["schemes"],
            health_centers     = health_centers,
        )
        self.graph = get_graph()
        print("✅ Agent ready.\n")

    def run_case(self, case: dict) -> dict:
        """Run a single test case. Returns result dict."""
        start = time.time()

        try:
            result = self.graph.invoke({
                "messages": [HumanMessage(content=case["query"])]
            })
            latency = time.time() - start

            # Extract response text
            response = result["messages"][-1].content

            # Extract tools called
            tools_called = []
            for msg in result["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        name = tc.get("name", "") if isinstance(tc, dict) else tc.name
                        if name:
                            tools_called.append(name)

            # Evaluate: must_contain check
            response_lower = response.lower()
            missing_keywords = [
                kw for kw in case["must_contain"]
                if kw.lower() not in response_lower
            ]
            hallucinated = [
                kw for kw in case.get("must_not_contain", [])
                if kw.lower() in response_lower
            ]

            # Tool accuracy check
            tool_correct = True
            if case["expected_tool"]:
                tool_correct = case["expected_tool"] in tools_called

            passed = len(missing_keywords) == 0 and len(hallucinated) == 0

            result_dict = {
                "id":               case["id"],
                "category":         case["category"],
                "description":      case["description"],
                "query":            case["query"],
                "passed":           passed,
                "tool_correct":     tool_correct,
                "tools_called":     tools_called,
                "expected_tool":    case["expected_tool"],
                "missing_keywords": missing_keywords,
                "hallucinated":     hallucinated,
                "latency_s":        round(latency, 2),
                "response_preview": response[:200] + "..." if len(response) > 200 else response,
            }

            if self.verbose:
                result_dict["full_response"] = response

            return result_dict

        except Exception as e:
            return {
                "id":       case["id"],
                "category": case["category"],
                "passed":   False,
                "error":    str(e),
                "latency_s": time.time() - start,
            }

    def run_all(self, category_filter: Optional[str] = None) -> dict:
        """Run all test cases and return summary."""
        cases = GOLDEN_CASES
        if category_filter:
            cases = [c for c in cases if c["category"] == category_filter]

        print(f"🧪 Running {len(cases)} test cases...\n")
        results = []

        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case['id']}: {case['description']}...")
            r = self.run_case(case)
            results.append(r)

            status = "✅ PASS" if r.get("passed") else "❌ FAIL"
            latency = r.get("latency_s", 0)
            tools = r.get("tools_called", [])
            print(f"         {status} | {latency}s | tools: {tools}")

            if not r.get("passed") and r.get("missing_keywords"):
                print(f"         Missing: {r['missing_keywords']}")
            time.sleep(3)  # small delay for readability

        # Summary
        passed      = sum(1 for r in results if r.get("passed"))
        tool_correct = sum(1 for r in results if r.get("tool_correct", True))
        avg_latency = sum(r.get("latency_s", 0) for r in results) / len(results)

        summary = {
            "timestamp":        datetime.now().isoformat(),
            "total":            len(results),
            "passed":           passed,
            "failed":           len(results) - passed,
            "pass_rate":        f"{passed/len(results)*100:.1f}%",
            "tool_accuracy":    f"{tool_correct/len(results)*100:.1f}%",
            "avg_latency_s":    round(avg_latency, 2),
            "results":          results,
        }

        return summary

    def save_results(self, summary: dict):
        """Save results to eval/results/ directory."""
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        path = results_dir / f"eval_{ts}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Results saved to {path}")
        return path

    def print_summary(self, summary: dict):
        print("\n" + "="*60)
        print("📊 EVALUATION SUMMARY")
        print("="*60)
        print(f"  Total tests:    {summary['total']}")
        print(f"  Passed:         {summary['passed']} ({summary['pass_rate']})")
        print(f"  Failed:         {summary['failed']}")
        print(f"  Tool accuracy:  {summary['tool_accuracy']}")
        print(f"  Avg latency:    {summary['avg_latency_s']}s")
        print("="*60)

        # Per-category breakdown
        categories = {}
        for r in summary["results"]:
            cat = r.get("category", "unknown")
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0}
            categories[cat]["total"] += 1
            if r.get("passed"):
                categories[cat]["passed"] += 1

        print("\nPer-category:")
        for cat, stats in categories.items():
            rate = stats["passed"] / stats["total"] * 100
            print(f"  {cat:20s} {stats['passed']}/{stats['total']} ({rate:.0f}%)")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swasthya Saathi Evaluation Harness")
    parser.add_argument("--tool", choices=["symptom", "medicine", "scheme", "health_center", "multi"],
                        help="Run only tests for a specific category")
    parser.add_argument("--verbose", action="store_true", help="Show full responses")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to file")
    args = parser.parse_args()

    evaluator = Evaluator(verbose=args.verbose)
    summary = evaluator.run_all(category_filter=args.tool)
    evaluator.print_summary(summary)

    if not args.no_save:
        evaluator.save_results(summary)
