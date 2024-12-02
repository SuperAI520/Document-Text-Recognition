# Optical Character Recognition made seamless & accessible to anyone, powered by TensorFlow 2 & PyTorch**

What you can expect from this repository:

- efficient ways to parse textual information (localize and identify each word) from your documents
- guidance on how to integrate this in your current architecture

## Quick Tour

### Getting your pretrained model

```python
from doctr.models import ocr_predictor

model = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True)
```

### Reading files

Documents can be interpreted from PDF or images:

```python
from doctr.io import DocumentFile
# PDF
pdf_doc = DocumentFile.from_pdf("path/to/your/doc.pdf")
# Image
single_img_doc = DocumentFile.from_images("path/to/your/img.jpg")
# Webpage (requires `weasyprint` to be installed)
webpage_doc = DocumentFile.from_url("https://www.yoursite.com")
# Multiple page images
multi_img_doc = DocumentFile.from_images(["path/to/page1.jpg", "path/to/page2.jpg"])
```

### Putting it together

Let's use the default pretrained model for an example:

```python
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

model = ocr_predictor(pretrained=True)
# PDF
doc = DocumentFile.from_pdf("path/to/your/doc.pdf")
# Analyze
result = model(doc)
```

## Installation

### Prerequisites

Python 3.10 (or higher) and [pip](https://pip.pypa.io/en/stable/) are required to install docTR.

### Latest release

You can then install the latest release of the package using [pypi](https://pypi.org/project/python-doctr/) as follows:

```shell
pip install python-doctr
```

> :warning: Please note that the basic installation is not standalone, as it does not provide a deep learning framework, which is required for the package to run.

We try to keep framework-specific dependencies to a minimum. You can install framework-specific builds as follows:

```shell
# for TensorFlow
pip install "python-doctr[tf]"
# for PyTorch
pip install "python-doctr[torch]"
# optional dependencies for visualization, html, and contrib modules can be installed as follows:
pip install "python-doctr[torch,viz,html,contib]"
```

For MacBooks with M1 chip, you will need some additional packages or specific versions:

- TensorFlow 2: [metal plugin](https://developer.apple.com/metal/tensorflow-plugin/)
- PyTorch: [version >= 2.0.0](https://pytorch.org/get-started/locally/#start-locally)

## Models architectures

Credits where it's due: this repository is implementing, among others, architectures from published research papers.

### Text Detection

- DBNet: [Real-time Scene Text Detection with Differentiable Binarization](https://arxiv.org/pdf/1911.08947.pdf).
- LinkNet: [LinkNet: Exploiting Encoder Representations for Efficient Semantic Segmentation](https://arxiv.org/pdf/1707.03718.pdf)
- FAST: [FAST: Faster Arbitrarily-Shaped Text Detector with Minimalist Kernel Representation](https://arxiv.org/pdf/2111.02394.pdf)

### Text Recognition

- CRNN: [An End-to-End Trainable Neural Network for Image-based Sequence Recognition and Its Application to Scene Text Recognition](https://arxiv.org/pdf/1507.05717.pdf).
- SAR: [Show, Attend and Read:A Simple and Strong Baseline for Irregular Text Recognition](https://arxiv.org/pdf/1811.00751.pdf).
- MASTER: [MASTER: Multi-Aspect Non-local Network for Scene Text Recognition](https://arxiv.org/pdf/1910.02562.pdf).
- ViTSTR: [Vision Transformer for Fast and Efficient Scene Text Recognition](https://arxiv.org/pdf/2105.08582.pdf).
- PARSeq: [Scene Text Recognition with Permuted Autoregressive Sequence Models](https://arxiv.org/pdf/2207.06966).
