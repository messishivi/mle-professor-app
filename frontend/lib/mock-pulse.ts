import type { Paper } from "./pulse-types";

/**
 * Prototype mock data for the P1 design review only.
 * Replaced by real API data in P2a/P3a. Titles are fictional.
 */
export const MOCK_UPDATED_AT = "2026-09-13 06:00 UTC";

export const MOCK_STACK = [
  "PyTorch",
  "FastAPI",
  "K8s",
  "A10 GPUs",
  "pgvector",
];

export const MOCK_PAPERS: Paper[] = [
  {
    id: "p-2609-08412",
    title:
      "SparseMoE Routing at the Edge: 4-bit Grouped Experts for Sub-Second Inference",
    url: "https://arxiv.org/abs/2609.08412",
    arxivId: "2609.08412",
    source: "arXiv",
    date: "2026-09-12",
    abstract:
      "Groups 4-bit quantized experts by router affinity and serves them on a single A10-class GPU, cutting p95 latency 3.1x vs. the fp16 baseline at <1% quality drop on 12 evaluation suites.",
    concepts: ["MoE", "quantization", "serving"],
    verdict: "adopt",
    fit: "high",
    memo:
      "Directly applicable to our inference stack: same GPU class, router changes are drop-in. Pilot on the support-bot model next sprint.",
    read: false,
  },
  {
    id: "p-2609-07955",
    title:
      "Continual Pretraining on Customer Data: A 12-Day Recipe That Survives Forgetting",
    url: "https://arxiv.org/abs/2609.07955",
    arxivId: "2609.07955",
    source: "arXiv",
    date: "2026-09-11",
    abstract:
      "A data-mixing and replay schedule for 12-day CPT runs on domain corpora, measuring catastrophic forgetting with a 40-task held-out battery and keeping drift under 2%.",
    concepts: ["continual learning", "pretraining"],
    verdict: "adopt",
    fit: "high",
    memo:
      "The replay schedule is the reusable artifact. Our customer-data corpus fits the paper's size band; worth a dry-run cost estimate.",
    read: false,
  },
  {
    id: "hf-48213",
    title: "Speculative Decoding with Self-Drafted Trees",
    url: "https://huggingface.co/papers/48213",
    arxivId: "2609.06210",
    source: "HF",
    date: "2026-09-10",
    abstract:
      "Drafts verification trees using the target model's own early layers, gaining 1.7x throughput without a separate draft model and without changing the serving API.",
    concepts: ["speculative decoding", "latency"],
    verdict: "prototype",
    fit: "watch",
    memo:
      "Needs a prototype pass: integration lives inside our serving layer, and gains depend on our acceptance-rate profile. 2-week spike.",
    read: true,
  },
  {
    id: "p-2609-05518",
    title: "Benchmarking RAG: Where Retrievers Actually Break",
    url: "https://arxiv.org/abs/2609.05518",
    arxivId: "2609.05518",
    source: "arXiv",
    date: "2026-09-09",
    abstract:
      "Systematic failure taxonomy across 9 retrievers on multi-hop and temporal queries: temporal grounding is the weakest axis, failing on 41% of dated questions.",
    concepts: ["RAG", "evaluation"],
    verdict: "watch",
    fit: "low",
    memo:
      "Useful as an evaluation checklist for our consultant grounding; not buildable for us directly. Keep for the eval harness work.",
    read: false,
  },
  {
    id: "hf-47902",
    title: "Yet Another Vision Tokenizer",
    url: "https://huggingface.co/papers/47902",
    arxivId: "2609.04101",
    source: "HF",
    date: "2026-09-08",
    abstract:
      "A 1024-token-per-image vision tokenizer trained with a DINOv3 backbone; competitive on classification, marginal on document understanding.",
    concepts: ["tokenization", "vision"],
    verdict: "skip",
    fit: "low",
    memo: "Outside our current problem space; vision is not on the roadmap. Skip for now.",
    read: false,
  },
  {
    id: "p-2609-03377",
    title: "Cost-Aware Model Routing for Multi-Tenant SaaS",
    url: "https://arxiv.org/abs/2609.03377",
    arxivId: "2609.03377",
    source: "arXiv",
    date: "2026-09-07",
    abstract:
      "A bandit-based router that sends each request to the cheapest model that passes a per-tenant quality gate; 38% cost reduction at fixed quality over 11 weeks of production data.",
    concepts: ["routing", "cost"],
    verdict: "watch",
    fit: "high",
    memo:
      "Strong fit with our token-spend controls (Plan 03). The per-tenant quality gate maps onto our provider layer; revisit when Plan 03 ships.",
    read: false,
  },
  {
    id: "hf-47511",
    title: "Protein Structure Refinement with Flow Matching",
    url: "https://huggingface.co/papers/47511",
    arxivId: "2609.02088",
    source: "HF",
    date: "2026-09-06",
    abstract:
      "Flow-matching denoisers that refine low-confidence protein backbone regions, improving local Cα accuracy by 0.4 Å on the CASP hard set.",
    concepts: ["protein", "flow matching"],
    verdict: "skip",
    fit: "low",
    memo: "Biology-adjacent; no overlap with our stack or roadmap. Skip.",
    read: false,
  },
  {
    id: "p-2609-01843",
    title: "Incremental Indexing for Vector Stores Under Write Load",
    url: "https://arxiv.org/abs/2609.01843",
    arxivId: "2609.01843",
    source: "arXiv",
    date: "2026-09-05",
    abstract:
      "Keeps an HNSW index queryable during continuous ingestion by partitioning builds into background generations; recall stays within 0.5% of a full rebuild.",
    concepts: ["vector db", "indexing"],
    verdict: "prototype",
    fit: "high",
    memo:
      "We run pgvector with periodic rebuilds — this would remove the rebuild window. Prototype: compare against our current rebuild cost first.",
    read: false,
  },
];
