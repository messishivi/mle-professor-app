"""Curated ML / MLE interview bank. Works fully offline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BankQuestion:
    id: str
    topic: str
    difficulty: str
    question: str
    answer: str
    hints: list[str] = field(default_factory=list)


TOPICS = [
    "Foundations",
    "Supervised Learning",
    "Deep Learning",
    "Transformers & NLP",
    "Computer Vision",
    "Optimization",
    "ML System Design",
    "MLOps",
    "Statistics & Experiments",
]


QUESTIONS: list[BankQuestion] = [
    BankQuestion(
        id="f-01",
        topic="Foundations",
        difficulty="easy",
        question="Explain the bias–variance tradeoff and how model complexity moves each term.",
        answer=(
            "Expected test error decomposes into bias² + variance + irreducible noise. "
            "Underfitting (high bias) comes from a hypothesis class too simple to capture the signal. "
            "Overfitting (high variance) comes from fitting noise; small data changes swing predictions. "
            "Regularization, more data, and ensembles reduce variance; a richer model or better features reduce bias."
        ),
        hints=["Write the error decomposition.", "What happens as you go from linear to a deep net?"],
    ),
    BankQuestion(
        id="f-02",
        topic="Foundations",
        difficulty="medium",
        question="When is MLE equivalent to MAP, and what prior recovers L2 regularization for a Gaussian likelihood?",
        answer=(
            "MAP = MLE when the prior is uniform (or as N → ∞ if the prior is proper). "
            "A Gaussian likelihood with a zero-mean isotropic Gaussian prior on weights is equivalent to L2 / ridge. "
            "A Laplace prior yields L1 / lasso. Always state the likelihood: squared loss ↔ Gaussian noise."
        ),
        hints=["MAP = argmax p(θ|x) ∝ p(x|θ)p(θ).", "Which prior has log-density −λ‖θ‖²?"],
    ),
    BankQuestion(
        id="f-03",
        topic="Foundations",
        difficulty="medium",
        question="What is data leakage? Give two subtle examples that show up in production ML."
        ,
        answer=(
            "Leakage is using information at training time that will not be available, or not legitimately available, at prediction time. "
            "Examples: (1) standardizing with test-set statistics or doing CV after feature selection on the full set; "
            "(2) using a post-treatment feature (clicked, charged-off) as an input; "
            "(3) random splits on time-series or on grouped users so the same entity appears in train and test; "
            "(4) target encoding without nested CV. Leakage inflates offline metrics and fails in production."
        ),
        hints=["Think time, groups, and features derived from the label."],
    ),
    BankQuestion(
        id="f-04",
        topic="Foundations",
        difficulty="hard",
        question="Why can a calibrated model with worse AUC still be preferable for a ranking-vs-decision product?",
        answer=(
            "AUC measures ranking quality over thresholds; calibration measures that predicted p matches empirical frequency. "
            "If the product uses a probability in an expected-value decision (pricing, bidding, medical threshold), "
            "miscalibration causes systematic over/under action even if rank order is good. "
            "You can often fix calibration post-hoc (Platt, isotonic) without changing AUC. "
            "If the product only sorts items, AUC/NDCG matter more than calibration."
        ),
        hints=["Separate ranking metrics from probability quality."],
    ),
    BankQuestion(
        id="s-01",
        topic="Supervised Learning",
        difficulty="easy",
        question="Precision, recall, F1, ROC-AUC, PR-AUC: which do you pick for a 1% fraud class?",
        answer=(
            "Accuracy is misleading. Precision/recall and PR-AUC focus on the positive class and are preferred under imbalance. "
            "ROC-AUC can look optimistic because many true negatives make FPR tiny. "
            "Choose the operating threshold from a cost matrix (false-positive review cost vs missed-fraud cost), not from F1 by default."
        ),
        hints=["What does FPR do when negatives dominate?"],
    ),
    BankQuestion(
        id="s-02",
        topic="Supervised Learning",
        difficulty="medium",
        question="Compare bagging and boosting. Why does a random forest reduce variance while GBM reduces bias?",
        answer=(
            "Bagging trains base learners independently on bootstrap samples and averages; RF also randomizes features, so trees de-correlate and variance drops. "
            "Boosting trains sequentially on residuals / reweighted errors, so the ensemble can fit complex functions (lower bias) but overfits if you boost too long. "
            "Use shallow trees + shrinkage + subsampling in GBM; use deep unpruned trees in RF."
        ),
        hints=["Independent vs sequential errors."],
    ),
    BankQuestion(
        id="s-03",
        topic="Supervised Learning",
        difficulty="medium",
        question="How does k-fold cross-validation change for time-series or grouped user data?",
        answer=(
            "i.i.d. k-fold leaks the future and leaks users. For time, use walk-forward / purged CV with an embargo around the cut. "
            "For grouped data (users, queries, patients), split by group so no entity is in both sides. "
            "Nested CV is required if you tune hyperparameters, otherwise the selection itself overfits the outer test."
        ),
        hints=["Independence of folds is the real assumption."],
    ),
    BankQuestion(
        id="s-04",
        topic="Supervised Learning",
        difficulty="hard",
        question="You have a high-cardinality categorical feature. Compare one-hot, hashing, target encoding, and embeddings. Failure modes?",
        answer=(
            "One-hot: simple, explodes dimensionality, fails on unseen levels. "
            "Hashing: fixed dim, collisions, no semantics. "
            "Target encoding: strong signal, severe leakage unless out-of-fold; smoothing for rare levels. "
            "Learned embeddings: share statistics across levels, need enough data per id, cold-start needs a default vector. "
            "In production, freeze the encoding map and handle unknowns explicitly."
        ),
        hints=["Think cardinality, leakage, and cold start."],
    ),
    BankQuestion(
        id="d-01",
        topic="Deep Learning",
        difficulty="easy",
        question="What problem do residual connections solve, and why do they help optimization more than representation?",
        answer=(
            "They give a gradient highway so deep nets can learn identity mappings instead of being forced to fit F(x) from scratch. "
            "This eases vanishing gradients and makes the loss landscape better conditioned; empirically the main win is optimization, "
            "not a magical new inductive bias. BatchNorm / LayerNorm and careful init play a similar role."
        ),
        hints=["What is easy to implement if you can add x back?"],
    ),
    BankQuestion(
        id="d-02",
        topic="Deep Learning",
        difficulty="medium",
        question="Dropout vs BatchNorm vs LayerNorm: when does each help, and why is dropout rarely used with BatchNorm today?",
        answer=(
            "Dropout is a regularizer that samples subnetworks; at train/test you must scale (or use inverted dropout). "
            "BatchNorm reduces internal covariate shift / smooths the landscape, uses minibatch stats, so it couples examples and is awkward for small batches, RNNs, and variable-length NLP. "
            "LayerNorm is batch-independent, standard in transformers. Dropout + BatchNorm interact badly because BN already noise-regularizes via batch stats, and dropout changes those stats between train and eval."
        ),
        hints=["Which normalizer depends on the batch?"],
    ),
    BankQuestion(
        id="d-03",
        topic="Deep Learning",
        difficulty="medium",
        question="Walk through backprop for a linear layer y = Wx + b with loss L. What is ∂L/∂W?",
        answer=(
            "Let δ = ∂L/∂y. Then ∂L/∂W = δ xᵀ (outer product), ∂L/∂b = δ, ∂L/∂x = Wᵀ δ. "
            "Shapes: if x is [n], y [m], W [m, n], then δ is [m] and ∂L/∂W is [m, n]. "
            "In minibatches you average or sum over the batch. Mention autograd implements this via the chain rule on the computational graph."
        ),
        hints=["Name the three gradients: W, b, x."],
    ),
    BankQuestion(
        id="d-04",
        topic="Deep Learning",
        difficulty="hard",
        question="Why do transformers prefer LayerNorm and AdamW, while a ResNet-50 on ImageNet still trains well with SGD + momentum?",
        answer=(
            "Vision CNNs are well-conditioned with strong spatial inductive bias and BatchNorm; SGD+momentum with a stepwise/cosine schedule generalizes well and is the historical recipe. "
            "Transformers are less locally smooth, have attention layers with scale issues, and are trained with Adam/AdamW whose per-parameter adaptive rates plus decoupled weight decay stabilize large embedding/LN parameter groups. "
            "Adam often generalizes slightly worse on CNNs; that's why many CV papers still quote SGD. Always mention learning-rate warmup for transformers."
        ),
        hints=["Inductive bias + optimizer generalization gap."],
    ),
    BankQuestion(
        id="t-01",
        topic="Transformers & NLP",
        difficulty="easy",
        question="Explain self-attention in one pass: Q, K, V, and the complexity vs an RNN.",
        answer=(
            "Each token makes a query, key, and value. Attention weights are softmax(QKᵀ / √d) and the output is weights · V. "
            "Every token can mix with every other token in O(n² d) time (n = sequence length), vs O(n d²) sequential steps for an RNN. "
            "The quadratic cost is the reason for sparse/linear attention, chunking, and long-context tricks. Multi-head attention lets heads specialize."
        ),
        hints=["Write the softmax(QKᵀ)V formula."],
    ),
    BankQuestion(
        id="t-02",
        topic="Transformers & NLP",
        difficulty="medium",
        question="BERT vs GPT: architecture, training objective, and what each is a bad idea for.",
        answer=(
            "BERT is a bidirectional encoder trained with masked LM (+ NSP in the original). Great for classification, span labeling, dense retrieval encoders. Bad as a left-to-right generator. "
            "GPT is a decoder-only causal LM. Great at generation, in-context learning, and instruction following. Weaker as a bidirectional encoder unless you pool carefully. "
            "T5-style encoder-decoder sits in between for seq2seq. Today most assistants are decoder-only."
        ),
        hints=["Masking vs next-token. Bidirectional vs causal mask."],
    ),
    BankQuestion(
        id="t-03",
        topic="Transformers & NLP",
        difficulty="medium",
        question="How does LoRA adapt a frozen LLM? Why is rank r ≪ d enough?",
        answer=(
            "LoRA freezes W₀ and learns ΔW = BA with B ∈ R^{d×r}, A ∈ R^{r×k}, r ≪ min(d, k). "
            "The update lives in a low-rank subspace; empirically task adaptation has low intrinsic rank. "
            "Benefits: few trainable params, can swap adapters, merge at inference (W₀+BA) with no extra latency. "
            "QLoRA combines 4-bit base weights with LoRA. Watch rank, which layers (attn q/v vs MLP), and learning rate."
        ),
        hints=["ΔW = BA. Merge vs extra latency."],
    ),
    BankQuestion(
        id="t-04",
        topic="Transformers & NLP",
        difficulty="hard",
        question="Design a RAG system for internal docs. Where do you chunk, embed, retrieve, and fail?",
        answer=(
            "Ingest: parse, chunk with overlap by semantic sections not raw tokens only, store metadata (title, ACL). "
            "Embed with a retrieval model (not the chat model). Hybrid search: dense + BM25, then rerank. "
            "At query time: rewrite the question, retrieve top-k, pack into the context window with citations. "
            "Failures: bad chunking, embedding domain shift, stale index, lost tables/figures, prompt stuffing, hallucination when retrieval is empty. "
            "Evaluate with retrieval recall@k and grounded-answer scores, not just chat quality. Mention access control on chunks."
        ),
        hints=["Hybrid retrieval + evaluation of the retriever separately."],
    ),
    BankQuestion(
        id="c-01",
        topic="Computer Vision",
        difficulty="easy",
        question="What inductive bias does a convolution encode that a transformer does not?",
        answer=(
            "Locality, translation equivariance, and weight sharing: a conv kernel looks at a neighborhood and the same filter is reused across space. "
            "That is a strong prior for natural images and is data-efficient. ViTs replace this with patches + global attention and need more data/regularization (or conv stems) to match CNNs on small datasets."
        ),
        hints=["Locality and parameter sharing."],
    ),
    BankQuestion(
        id="c-02",
        topic="Computer Vision",
        difficulty="medium",
        question="How does a detection head differ from classification? Sketch Faster R-CNN vs YOLO at a high level.",
        answer=(
            "Classification predicts one label per image. Detection predicts a variable set of boxes + classes, so you need localization, matching (IoU / Hungarian), and a no-object class. "
            "Two-stage (Faster R-CNN): RPN proposes regions, then a head classifies/regresses each RoI. Accurate, slower. "
            "One-stage (YOLO/RetinaNet): dense predictions on a grid/anchors or queries, with focal loss to handle easy negatives. Faster, historically less precise on small objects."
        ),
        hints=["Set prediction + matching, not a single softmax."],
    ),
    BankQuestion(
        id="c-03",
        topic="Computer Vision",
        difficulty="medium",
        question="Why does data augmentation act like regularization in vision, and when can it hurt?",
        answer=(
            "Augmentations expand the empirical distribution toward invariances you want (crop, flip, color jitter, MixUp). That reduces overfitting to spurious cues. "
            "They hurt when they destroy the label: horizontal flip on text/digits, aggressive color jitter for medical stains, MixUp on detection boxes without box-aware mixing. "
            "Match augmentations to the deployment distribution (no random crop if the product always sees full frames)."
        ),
        hints=["Invariance vs label-destroying transforms."],
    ),
    BankQuestion(
        id="c-04",
        topic="Computer Vision",
        difficulty="hard",
        question="Contrast GANs and diffusion models for image generation. Training stability and sampling cost?",
        answer=(
            "GANs learn a generator vs discriminator min-max. Fast sampling (one forward pass) but unstable (mode collapse, oscillatory training, metric hacking of FID). "
            "Diffusion / score models learn to denoise over many steps; training is supervised and stable, likelihood-related objectives, high-quality samples, but sampling is slow (many NFE) unless distilled (consistency models, rectified flow). "
            "Latent diffusion (Stable Diffusion) runs the process in a VAE latent space to cut cost."
        ),
        hints=["Adversarial vs denoising. One-step vs many-step sampling."],
    ),
    BankQuestion(
        id="o-01",
        topic="Optimization",
        difficulty="easy",
        question="SGD, momentum, Adam: write the update idea and one reason to pick each.",
        answer=(
            "SGD: θ ← θ − η ∇L. Simple, best generalization on many convex/CNN problems, needs a tuned schedule. "
            "Momentum / Nesterov: velocity accumulates gradients, dampens noise, accelerates along consistent directions. "
            "Adam: per-parameter first and second moment estimates; robust to scale, default for transformers/NLP. "
            "AdamW decouples weight decay from the adaptive update — use that, not L2-in-grad for Adam."
        ),
        hints=["Adaptive vs non-adaptive. AdamW vs Adam+L2."],
    ),
    BankQuestion(
        id="o-02",
        topic="Optimization",
        difficulty="medium",
        question="What does the learning-rate warmup + cosine decay schedule buy you in large-batch training?",
        answer=(
            "Large batches make early gradients noisy/large in scale; warmup avoids exploding updates while BatchNorm/Adam stats settle. "
            "Cosine (or linear) decay anneals to a small LR so you settle into a flatter minimum. "
            "Linear scaling rule: multiply LR by batch-size ratio, with warmup. If you cannot keep the effective batch, use gradient accumulation."
        ),
        hints=["Why is step 1 of Adam + huge LR dangerous?"],
    ),
    BankQuestion(
        id="o-03",
        topic="Optimization",
        difficulty="medium",
        question="Vanishing vs exploding gradients. Two concrete fixes besides 'use ResNets'.",
        answer=(
            "Vanishing: saturating sigmoids, deep unnormalized stacks. Fixes: ReLU/GELU, residual/highway, normalization, LSTM gates, better init (He/Xavier). "
            "Exploding: clip gradients by global norm, use smaller LR, skip connections, careful RNN init (orthogonal). "
            "Watch the gradient norm histogram in training; exploding often shows as NaNs, vanishing as layers that stop moving."
        ),
        hints=["Activation, init, clip, skip."],
    ),
    BankQuestion(
        id="o-04",
        topic="Optimization",
        difficulty="hard",
        question="You must train on one 16GB laptop. How do you fit a 7B-class model for LoRA fine-tuning?",
        answer=(
            "Don't load a full-precision 7B + Adam states (that is many tens of GB). Use 4-bit / 8-bit base weights (QLoRA), LoRA on attention projections, gradient checkpointing, small batch + accumulation, and freeze embeddings if needed. "
            "Prefer MLX/GGUF/llama.cpp style runtimes on Apple silicon rather than naive PyTorch fp32. "
            "If even that OOMs, distill, use a 1–3B model, or do all reasoning via an API and keep only embeddings local — which is the architecture of this app."
        ),
        hints=["Memory = weights + optimizer + activations. Quantize and adapter-tune."],
    ),
    BankQuestion(
        id="m-01",
        topic="ML System Design",
        difficulty="medium",
        question="Design a news-feed ranking system. Walk through candidate generation, ranking, and re-ranking.",
        answer=(
            "Three stages: (1) candidate generation / retrieval — two-tower or ANN over embeddings + heuristics, 10k → few hundred; "
            "(2) heavy ranker — GBDT or a small net on interaction features, predicts p(engage); "
            "(3) re-rank — diversity, freshness, exploration, business rules, calibration. "
            "Mention position bias (IPS / randomized drop), delayed labels, and an online A/B layer. Offline NDCG is not the product metric."
        ),
        hints=["Funnel: millions → hundreds → tens."],
    ),
    BankQuestion(
        id="m-02",
        topic="ML System Design",
        difficulty="medium",
        question="How would you detect and handle training-serving skew?",
        answer=(
            "Skew is any difference between train-time features/labels and serve-time ones: different code paths, clocks, default values, batch vs online aggregates, leaked future data. "
            "Mitigations: one feature definition (feature store with point-in-time joins), log serving features and train on the log, schema/distribution monitors, shadow traffic. "
            "Never recompute a training feature with a different SQL snippet in the serving graph."
        ),
        hints=["Log the served features and train on that."],
    ),
    BankQuestion(
        id="m-03",
        topic="ML System Design",
        difficulty="hard",
        question="Design real-time fraud detection with a 50ms p99 budget. What is online vs nearline vs offline?",
        answer=(
            "Online: feature lookup + model score in <50ms, so precompute embeddings/aggregates, no big joins, maybe a tiny tree or distilled net. "
            "Nearline: stream aggregates (last 1h spend) in Flink/Spark, write to Redis/feature store. "
            "Offline: train, backfill, heavy graph features. "
            "Use a cascade: rules → fast model → optional async review. Track precision@alert-budget, not just AUC. Have a kill switch and a fallback rule set."
        ),
        hints=["Precompute features. Cascade. Fallback."],
    ),
    BankQuestion(
        id="m-04",
        topic="ML System Design",
        difficulty="hard",
        question="Cold start in recommendations: new user, new item. Give a practical strategy for each.",
        answer=(
            "New user: onboarding questions, popularity/explore bandits, content-based from the first few clicks, don't wait for CF. "
            "New item: content embeddings (text/image) into the same space as item towers, editorial priors, explore traffic quota. "
            "Hybrid two-tower + content tower. Measure separately: recall for new items, not just overall NDCG which is dominated by head items."
        ),
        hints=["Content vs collaborative. Exploration budget."],
    ),
    BankQuestion(
        id="ops-01",
        topic="MLOps",
        difficulty="easy",
        question="What do you monitor after deploying a classifier besides accuracy?",
        answer=(
            "Input drift (PSI / KS on features), prediction drift, label delay, calibration, slice metrics (by country/device), latency/error rate, and data completeness. "
            "Accuracy needs labels; you often won't have them for days, so proxy with traffic quality and shadow models. Alert on sudden volume or null-rate changes first — they catch broken pipelines."
        ),
        hints=["You may not have labels tomorrow."],
    ),
    BankQuestion(
        id="ops-02",
        topic="MLOps",
        difficulty="medium",
        question="Feature store: what problem does it actually solve, and what is a point-in-time join?",
        answer=(
            "It is a consistent feature definition + serving/training materialization so training and serving don't diverge. "
            "A point-in-time join reconstructs, for each training event at time t, the feature values that would have been known then — no future aggregates. "
            "Without it, you leak. A store is overkill for one notebook model; it pays off with many models sharing entities."
        ),
        hints=["Consistency and time-travel, not just a Redis cache."],
    ),
    BankQuestion(
        id="ops-03",
        topic="MLOps",
        difficulty="medium",
        question="How do you roll out a new ranker safely?",
        answer=(
            "Offline eval on a frozen set + counterfactual/IPS if logging policy ≠ new policy. "
            "Shadow / dark launch comparing scores. Then A/B with a small traffic slice, guardrail metrics (latency, revenue, complaints), and a ramp plan. "
            "Keep an instant rollback. For ranking, watch position-aware metrics and long-term retention, not just CTR which can be gamed by clickbait."
        ),
        hints=["Offline → shadow → A/B → ramp. Guardrails."],
    ),
    BankQuestion(
        id="ops-04",
        topic="MLOps",
        difficulty="hard",
        question="Your production F1 dropped 8% overnight. Walk the debug tree.",
        answer=(
            "Check serving health first: error rate, null features, schema change, model artifact mismatch, clock/timezone, bad deploy. "
            "Then data: upstream pipeline, delayed labels, traffic mix shift (a new country). Compare feature distributions vs yesterday. "
            "Then model: was there a retraining job? leakage in the new data? "
            "Reproduce on logged serving features. If only one slice broke, it's data; if all slices, it's often a broken feature or swapped weights. Have a rollback ready before you 'just retrain'."
        ),
        hints=["Infra → data → model. Logged features beat recompute."],
    ),
    BankQuestion(
        id="st-01",
        topic="Statistics & Experiments",
        difficulty="easy",
        question="What does a p-value actually mean, and why is p < 0.05 not a product decision?",
        answer=(
            "P(data or more extreme | H₀ true), not P(H₀ | data). A small p says the data would be rare under the null, not that the effect is large or good for users. "
            "Look at effect size, confidence intervals, practical significance, multiple comparisons, and peeking. Pre-register the metric and stopping rule. Power the experiment for the MDE you care about."
        ),
        hints=["Conditional on H₀, not the other way around."],
    ),
    BankQuestion(
        id="st-02",
        topic="Statistics & Experiments",
        difficulty="medium",
        question="A/B test with a two-sided 5% test. You peek every day and stop at the first significant day. What's wrong, and how do you fix it?",
        answer=(
            "Optional stopping inflates Type I error; the p-value assumes a fixed sample size. "
            "Fixes: sequential tests (always-valid CIs, SPRT, alpha spending), CUPED for variance reduction, and a pre-declared horizon. "
            "Also cluster by user not event, or you understate variance. Novelty effects need a holdout over time."
        ),
        hints=["Peeking. User-level clustering."],
    ),
    BankQuestion(
        id="st-03",
        topic="Statistics & Experiments",
        difficulty="medium",
        question="Correlation is not causation. Give a concrete ML example where a causal question changes the model you train.",
        answer=(
            "Predicting who will churn (observational, using 'last 7 day activity') vs estimating the effect of a retention coupon. "
            "If you train on post-treatment activity you block the causal path. For treatment effect you want uplift / ITE models, randomized assignment or identification assumptions (unconfoundedness, IV). "
            "Another example: using hospital because it is a collider. Interviewers want you to separate prediction from intervention."
        ),
        hints=["Prediction vs intervention. Post-treatment features."],
    ),
    BankQuestion(
        id="st-04",
        topic="Statistics & Experiments",
        difficulty="hard",
        question="You need to measure a ranking change when historical logs were collected under a different policy. Outline an off-policy estimator and its failure mode.",
        answer=(
            "Inverse propensity scoring: for each logged item, weight by π_new(a|x)/π_old(a|x). Unbiased if propensities are correct and support overlaps. "
            "Failure: large weights on rare actions → huge variance. Fixes: clip weights, self-normalized IPS, doubly robust (IPS + reward model). "
            "If the new policy proposes actions the old policy never showed, you cannot evaluate them from logs — you need exploration data."
        ),
        hints=["IPS variance. Overlap."],
    ),
]


def questions_for(
    topic: str | None = None,
    *,
    difficulty: str | None = None,
) -> list[BankQuestion]:
    out = QUESTIONS
    if topic and topic != "All":
        out = [q for q in out if q.topic == topic]
    if difficulty and difficulty != "All":
        out = [q for q in out if q.difficulty == difficulty]
    return list(out)


def question_by_id(qid: str) -> BankQuestion | None:
    for q in QUESTIONS:
        if q.id == qid:
            return q
    return None
