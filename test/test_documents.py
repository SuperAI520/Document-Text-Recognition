import requests
import pytest
import fitz
import numpy as np
from io import BytesIO

from doctr import documents


def _mock_words(size=(1., 1.), offset=(0, 0), confidence=0.9):
    return [
        documents.Word("hello", confidence, [
            (offset[0], offset[1]),
            (size[0] / 2 + offset[0], size[1] / 2 + offset[1])
        ]),
        documents.Word("world", confidence, [
            (size[0] / 2 + offset[0], size[1] / 2 + offset[1]),
            (size[0] + offset[0], size[1] + offset[1])
        ])
    ]


def _mock_lines(size=(1, 1), offset=(0, 0)):
    sub_size = (size[0] / 2, size[1] / 2)
    return [
        documents.Line(_mock_words(size=sub_size, offset=offset)),
        documents.Line(_mock_words(size=sub_size, offset=(offset[0] + sub_size[0], offset[1] + sub_size[1]))),
    ]


def _mock_blocks(size=(1, 1), offset=(0, 0)):
    sub_size = (size[0] / 2, size[1] / 2)
    return [
        documents.Block(_mock_lines(size=sub_size, offset=offset)),
        documents.Block(_mock_lines(size=sub_size, offset=(offset[0] + sub_size[0], offset[1] + sub_size[1]))),
    ]


def _mock_pages(block_size=(1, 1), block_offset=(0, 0)):
    return [
        documents.Page(_mock_blocks(block_size, block_offset), 0, (300, 200),
                       {"value": 0., "confidence": 1.}, {"value": "EN", "confidence": 0.8}),
        documents.Page(_mock_blocks(block_size, block_offset), 1, (500, 1000),
                       {"value": 0.15, "confidence": 0.8}, {"value": "FR", "confidence": 0.7}),
    ]


def test_word():
    word_str = "hello"
    conf = 0.8
    geom = ((0, 0), (1, 1))
    word = documents.Word(word_str, conf, geom)

    # Attribute checks
    assert word.value == word_str
    assert word.confidence == conf
    assert word.geometry == geom

    # Render
    assert word.render() == word_str

    # Export
    assert word.export() == {"value": word_str, "confidence": conf, "geometry": geom}


def test_line():
    geom = ((0, 0), (0.5, 0.5))
    words = _mock_words(size=geom[1], offset=geom[0])
    line = documents.Line(words)

    # Attribute checks
    assert len(line.children) == len(words)
    assert all(isinstance(w, documents.Word) for w in line.children)
    assert line.geometry == geom

    # Render
    assert line.render() == "hello world"

    # Export
    assert line.export() == {"words": [w.export() for w in words], "geometry": geom}


def test_block():
    geom = ((0, 0), (1, 1))
    lines = _mock_lines(size=geom[1], offset=geom[0])
    block = documents.Block(lines)

    # Attribute checks
    assert len(block.children) == len(lines)
    assert all(isinstance(w, documents.Line) for w in block.children)
    assert block.geometry == geom

    # Render
    assert block.render() == "hello world\nhello world"

    # Export
    assert block.export() == {"lines": [line.export() for line in lines], "geometry": geom}


def test_page():
    page_idx = 0
    page_size = (300, 200)
    orientation = {"value": 0., "confidence": 0.}
    language = {"value": "EN", "confidence": 0.8}
    blocks = _mock_blocks()
    page = documents.Page(blocks, page_idx, page_size, orientation, language)

    # Attribute checks
    assert len(page.children) == len(blocks)
    assert all(isinstance(b, documents.Block) for b in page.children)
    assert page.page_idx == page_idx
    assert page.dimensions == page_size
    assert page.orientation == orientation
    assert page.language == language

    # Render
    assert page.render() == "hello world\nhello world\n\nhello world\nhello world"

    # Export
    assert page.export() == {"blocks": [b.export() for b in blocks], "page_idx": page_idx, "dimensions": page_size,
                             "orientation": orientation, "language": language}


def test_document():
    pages = _mock_pages()
    doc = documents.Document(pages)

    # Attribute checks
    assert len(doc.children) == len(pages)
    assert all(isinstance(p, documents.Page) for p in doc.children)

    # Render
    page_export = "hello world\nhello world\n\nhello world\nhello world"
    assert doc.render() == f"{page_export}\n\n\n\n{page_export}"

    # Export
    assert doc.export() == {"pages": [p.export() for p in pages]}


@pytest.fixture(scope="session")
def mock_pdf(tmpdir_factory):
    url = 'https://arxiv.org/pdf/1911.08947.pdf'
    file = BytesIO(requests.get(url).content)
    fn = tmpdir_factory.mktemp("data").join("mock_pdf_file.pdf")
    with open(fn, 'wb') as f:
        f.write(file.getbuffer())
    return fn


def test_pdf_reader_with_pix(mock_pdf, num_pixels=2000000):
    documents_imgs, documents_names, documents_shapes = documents.reader.read_documents(
        filepaths=[mock_pdf],
        num_pixels=num_pixels)
    for doc_shapes, doc_images, doc_names in zip(documents_shapes, documents_imgs, documents_names):
        for shape, image, document_name in zip(doc_shapes, doc_images, doc_names):
            assert isinstance(shape, tuple)
            assert isinstance(document_name, str)
            assert isinstance(image, np.ndarray)
            assert shape[0] * shape[1] <= 1.005 * num_pixels
            assert shape[0] * shape[1] >= 0.995 * num_pixels


def test_pdf_reader(mock_pdf):
    documents_imgs, documents_names, documents_shapes = documents.reader.read_documents(
        filepaths=[mock_pdf],
        num_pixels=None)
    for doc_shapes, doc_images, doc_names in zip(documents_shapes, documents_imgs, documents_names):
        for shape, image, document_name in zip(doc_shapes, doc_images, doc_names):
            assert isinstance(shape, tuple)
            assert isinstance(document_name, str)
            assert isinstance(image, np.ndarray)
            assert shape[0] * shape[1] <= 3000000
            assert shape[0] * shape[1] >= 800000


def test_exceptions_channels(mock_pdf):
    pdf = fitz.open(mock_pdf)
    pixmap = documents.reader.page_to_pixmap(pdf[0])
    with pytest.raises(Exception):
        nparray = documents.reader.pixmap_to_numpy(pixmap=pixmap, channel_order='false')
    nparray = documents.reader.pixmap_to_numpy(pixmap=pixmap, channel_order='BGR')
    assert isinstance(nparray, np.ndarray)
