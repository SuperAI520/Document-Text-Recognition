import pytest
import requests
from io import BytesIO

from doctr import models

import sys
from tensorflow.keras import layers
from tensorflow.keras.models import Sequential

from doctr.models.preprocessor import Preprocessor
from doctr import documents
from test_documents import mock_pdf


@pytest.fixture(scope="module")
def mock_model():
    _layers = [
        layers.Conv2D(8, 3, activation='relu', padding='same', input_shape=(224, 224, 3)),
        layers.GlobalAveragePooling2D(),
        layers.Flatten(),
        layers.Dense(10),
    ]
    return Sequential(_layers)


@pytest.fixture(scope="module")
def test_convert_to_tflite(mock_model):
    serialized_model = models.utils.convert_to_tflite(mock_model)
    assert isinstance(serialized_model, bytes)
    return serialized_model


@pytest.fixture(scope="module")
def test_convert_to_fp16(mock_model):
    serialized_model = models.utils.convert_to_fp16(mock_model)
    assert isinstance(serialized_model, bytes)
    return serialized_model


@pytest.fixture(scope="module")
def test_quantize_model(mock_model):
    serialized_model = models.utils.quantize_model(mock_model, (224, 224, 3))
    assert isinstance(serialized_model, bytes)
    return serialized_model


def test_export_sizes(test_convert_to_tflite, test_convert_to_fp16, test_quantize_model):
    assert sys.getsizeof(test_convert_to_tflite) > sys.getsizeof(test_convert_to_fp16)
    assert sys.getsizeof(test_convert_to_fp16) > sys.getsizeof(test_quantize_model)


def test_preprocess_documents(mock_pdf, num_docs=10, batch_size=3):  # noqa: F811
    docs = documents.reader.read_documents(
        filepaths=[mock_pdf for _ in range(num_docs)])
    preprocessor = Preprocessor(out_size=(600, 600), normalization=True, mode='symmetric', batch_size=batch_size)
    batched_docs, docs_indexes, pages_indexes = preprocessor(docs)
    assert len(docs_indexes) == len(pages_indexes)
    assert docs_indexes[-1] + 1 == num_docs
    if num_docs > batch_size:
        assert all(len(batch) == batch_size for batches in batched_docs[:-1] for batch in batches)
