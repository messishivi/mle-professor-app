"""Canonical papers so the knowledge base is useful on first launch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedPaper:
    external_id: str
    title: str
    authors: str
    year: int
    topics: tuple[str, ...]
    abstract: str


SEED_PAPERS: tuple[SeedPaper, ...] = (
    SeedPaper(
        external_id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin",
        year=2017,
        topics=("Transformers & NLP", "Deep Learning"),
        abstract=(
            "We propose the Transformer, a model architecture based solely on attention mechanisms, "
            "dispensing with recurrence and convolutions entirely. Experiments on machine translation "
            "tasks show these models to be superior in quality while being more parallelizable and "
            "requiring significantly less time to train. The Transformer uses stacked self-attention "
            "and point-wise fully connected layers for both encoder and decoder, with multi-head "
            "attention and positional encodings to retain order information."
        ),
    ),
    SeedPaper(
        external_id="1810.04805",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        authors="Devlin, Chang, Lee, Toutanova",
        year=2018,
        topics=("Transformers & NLP",),
        abstract=(
            "BERT is designed to pre-train deep bidirectional representations from unlabeled text by "
            "jointly conditioning on both left and right context in all layers. The pre-trained BERT "
            "model can be fine-tuned with just one additional output layer to create state-of-the-art "
            "models for a wide range of tasks, such as question answering and language inference, "
            "without substantial task-specific architecture modifications. BERT uses a masked language "
            "model objective and next-sentence prediction."
        ),
    ),
    SeedPaper(
        external_id="1512.03385",
        title="Deep Residual Learning for Image Recognition",
        authors="He, Zhang, Ren, Sun",
        year=2015,
        topics=("Computer Vision", "Deep Learning"),
        abstract=(
            "Deeper neural networks are more difficult to train. We present a residual learning "
            "framework to ease the training of networks that are substantially deeper than those used "
            "previously. We explicitly reformulate the layers as learning residual functions with "
            "reference to the layer inputs, instead of learning unreferenced functions. We provide "
            "comprehensive empirical evidence showing that these residual networks are easier to "
            "optimize and can gain accuracy from considerably increased depth."
        ),
    ),
    SeedPaper(
        external_id="1412.6980",
        title="Adam: A Method for Stochastic Optimization",
        authors="Kingma, Ba",
        year=2015,
        topics=("Optimization",),
        abstract=(
            "We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic "
            "objective functions, based on adaptive estimates of lower-order moments. The method is "
            "straightforward to implement, is computationally efficient, has little memory requirement, "
            "is invariant to diagonal rescaling of the gradients, and is well suited for problems that "
            "are large in terms of data and/or parameters. The hyper-parameters have intuitive "
            "interpretations and typically require little tuning."
        ),
    ),
    SeedPaper(
        external_id="1502.03167",
        title="Batch Normalization: Accelerating Deep Network Training by Reducing Internal Covariate Shift",
        authors="Ioffe, Szegedy",
        year=2015,
        topics=("Deep Learning", "Optimization"),
        abstract=(
            "Training deep neural networks is complicated by the fact that the distribution of each "
            "layer's inputs changes during training, as the parameters of the previous layers change. "
            "We refer to this as internal covariate shift, and address the problem by normalizing layer "
            "inputs. Batch Normalization allows us to use much higher learning rates and be less careful "
            "about initialization, and in some cases eliminates the need for Dropout."
        ),
    ),
    SeedPaper(
        external_id="2005.11401",
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        authors="Lewis, Perez, Piktus, Petroni, Karpukhin, Goyal, Küttler, Lewis, Yih, Rocktäschel, Riedel, Kiela",
        year=2020,
        topics=("Transformers & NLP", "ML System Design"),
        abstract=(
            "Large pre-trained language models store factual knowledge in their parameters and still "
            "have difficulty accessing and precisely manipulating knowledge. Retrieval-Augmented "
            "Generation (RAG) combines pre-trained parametric memory with a non-parametric memory of "
            "a dense vector index of Wikipedia. We show that RAG models generate more specific, diverse "
            "and factual language than a purely parametric seq2seq baseline."
        ),
    ),
    SeedPaper(
        external_id="2106.09685",
        title="LoRA: Low-Rank Adaptation of Large Language Models",
        authors="Hu, Shen, Wallis, Allen-Zhu, Li, Wang, Wang, Chen",
        year=2021,
        topics=("Transformers & NLP", "Optimization"),
        abstract=(
            "We propose Low-Rank Adaptation (LoRA), which freezes the pre-trained model weights and "
            "injects trainable rank decomposition matrices into each layer of the Transformer "
            "architecture, greatly reducing the number of trainable parameters for downstream tasks. "
            "On GPT-3 175B, LoRA reduces trainable parameters by 10,000 times and GPU memory by 3 times "
            "compared to full fine-tuning, with no additional inference latency when the adapters are merged."
        ),
    ),
    SeedPaper(
        external_id="2006.11239",
        title="Denoising Diffusion Probabilistic Models",
        authors="Ho, Jain, Abbeel",
        year=2020,
        topics=("Computer Vision", "Deep Learning"),
        abstract=(
            "We present high quality image synthesis results using diffusion probabilistic models, a "
            "class of latent variable models inspired by considerations from nonequilibrium "
            "thermodynamics. Our best results are obtained by training on a weighted variational bound "
            "designed according to a novel connection between diffusion probabilistic models and "
            "denoising score matching with Langevin dynamics."
        ),
    ),
    SeedPaper(
        external_id="1707.06347",
        title="Proximal Policy Optimization Algorithms",
        authors="Schulman, Wolski, Dhariwal, Radford, Klimov",
        year=2017,
        topics=("Optimization", "Deep Learning"),
        abstract=(
            "We propose Proximal Policy Optimization (PPO), a family of policy gradient methods for "
            "reinforcement learning which alternate between sampling data through interaction with the "
            "environment and optimizing a surrogate objective using stochastic gradient ascent. PPO "
            "uses a novel objective that enables multiple epochs of minibatch updates while clipping "
            "the probability ratio to keep the new policy close to the old one."
        ),
    ),
    SeedPaper(
        external_id="1312.6114",
        title="Auto-Encoding Variational Bayes",
        authors="Kingma, Welling",
        year=2014,
        topics=("Deep Learning", "Foundations"),
        abstract=(
            "We show how a reparameterization of the variational lower bound yields a simple "
            "differentiable unbiased estimator of the lower bound that can be optimized using standard "
            "stochastic gradient methods. The resulting Auto-Encoding Variational Bayes (AEVB) "
            "algorithm learns a recognition model (inference network) jointly with a generative model, "
            "enabling efficient approximate posterior inference and ancestral sampling."
        ),
    ),
    SeedPaper(
        external_id="1301.3781",
        title="Efficient Estimation of Word Representations in Vector Space",
        authors="Mikolov, Chen, Corrado, Dean",
        year=2013,
        topics=("Transformers & NLP", "Foundations"),
        abstract=(
            "We propose two novel model architectures for computing continuous vector representations "
            "of words from very large data sets: the Continuous Bag-of-Words model and the Skip-gram "
            "model. The quality of the vectors is measured in a word similarity task and in analogical "
            "reasoning; the skip-gram architecture achieves large improvements in accuracy at much "
            "lower computational cost than previous neural language models."
        ),
    ),
    SeedPaper(
        external_id="1409.1556",
        title="Very Deep Convolutional Networks for Large-Scale Image Recognition",
        authors="Simonyan, Zisserman",
        year=2015,
        topics=("Computer Vision", "Deep Learning"),
        abstract=(
            "We investigate the effect of the convolutional network depth on its accuracy in the "
            "large-scale image recognition setting. The main contribution is a thorough evaluation of "
            "networks of increasing depth using an architecture with very small (3×3) convolution "
            "filters, which shows that a significant improvement on the prior-art can be achieved by "
            "pushing the depth to 16–19 weight layers (VGG)."
        ),
    ),
)
