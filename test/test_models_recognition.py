import pytest
import numpy as np
import math
import tensorflow as tf

from doctr.models import recognition
from doctr.documents import read_pdf
from doctr.models import extract_crops


def test_recopreprocessor(mock_pdf):  # noqa: F811
    num_docs = 3
    batch_size = 4
    docs = [read_pdf(mock_pdf) for _ in range(num_docs)]
    processor = recognition.RecognitionPreProcessor(output_size=(256, 128), batch_size=batch_size)
    batched_docs = processor([page for doc in docs for page in doc])

    # Number of batches
    assert len(batched_docs) == math.ceil(8 * num_docs / batch_size)
    # Total number of samples
    assert sum(batch.shape[0] for batch in batched_docs) == 8 * num_docs
    # Batch size
    assert all(batch.shape[0] == batch_size for batch in batched_docs[:-1])
    assert batched_docs[-1].shape[0] == batch_size if (8 * num_docs) % batch_size == 0 else (8 * num_docs) % batch_size
    # Data type
    assert all(batch.dtype == tf.float32 for batch in batched_docs)
    # Image size
    assert all(batch.shape[1:] == (256, 128, 3) for batch in batched_docs)
    # Test with non-full last batch
    batch_size = 16
    processor = recognition.RecognitionPreProcessor(output_size=(256, 128), batch_size=batch_size)
    batched_docs = processor([page for doc in docs for page in doc])
    assert batched_docs[-1].shape[0] == (8 * num_docs) % batch_size


@pytest.mark.parametrize(
    "arch_name, input_shape, output_size",
    [
        ["crnn_vgg16_bn", (32, 128, 3), (32, 119)],
        ["sar_vgg16_bn", (64, 256, 3), (41, 119)],
    ],
)
def test_recognition_models(arch_name, input_shape, output_size):
    batch_size = 8
    reco_model = recognition.__dict__[arch_name](pretrained=True, input_shape=input_shape)
    input_tensor = tf.random.uniform(shape=[batch_size, *input_shape], minval=0, maxval=1)
    out = reco_model(input_tensor)
    assert isinstance(out, tf.Tensor)
    assert isinstance(reco_model, tf.keras.Model)
    assert out.numpy().shape == (batch_size, *output_size)


@pytest.mark.parametrize(
    "post_processor, input_shape",
    [
        ["SARPostProcessor", [2, 30, 119]],
        ["CTCPostProcessor", [2, 30, 119]],
    ],
)
def test_reco_postprocessors(post_processor, input_shape, mock_vocab):
    processor = recognition.__dict__[post_processor](mock_vocab)
    decoded = processor(tf.random.uniform(shape=input_shape, minval=0, maxval=1, dtype=tf.float32))
    assert isinstance(decoded, list) and all(isinstance(word, str) for word in decoded)
    assert len(decoded) == input_shape[0]
    assert all(char in mock_vocab for word in decoded for char in word)


@pytest.fixture(scope="session")
def test_recognitionpredictor(mock_pdf, mock_vocab):  # noqa: F811

    batch_size = 4
    predictor = recognition.RecognitionPredictor(
        recognition.RecognitionPreProcessor(output_size=(32, 128), batch_size=batch_size),
        recognition.crnn_vgg16_bn(vocab_size=len(mock_vocab), input_shape=(32, 128, 3)),
        recognition.CTCPostProcessor(mock_vocab)
    )

    pages = read_pdf(mock_pdf)
    # Create bounding boxes
    boxes = np.array([[0, 0, 0.25, 0.25], [0.5, 0.5, 1., 1.]], dtype=np.float32)
    crops = extract_crops(pages[0], boxes)

    out = predictor(crops)

    # One prediction per crop
    assert len(out) == boxes.shape[0]
    assert all(isinstance(charseq, str) for charseq in out)

    return predictor


@pytest.mark.parametrize(
    "arch_name",
    [
        "crnn_vgg16_bn_predictor",
        "sar_vgg16_bn_predictor",
    ],
)
def test_recognition_zoo(arch_name):
    batch_size = 2
    # Model
    predictor = recognition.zoo.__dict__[arch_name](pretrained=False)
    # object check
    assert isinstance(predictor, recognition.RecognitionPredictor)
    input_tensor = tf.random.uniform(shape=[batch_size, 1024, 1024, 3], minval=0, maxval=1)
    out = predictor(input_tensor)
    assert isinstance(out, list) and len(out) == batch_size
    assert all(isinstance(word, str) for word in out)
