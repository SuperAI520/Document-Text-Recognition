from doctr.utils import geometry
import numpy as np


def test_bbox_to_polygon():
    assert geometry.bbox_to_polygon(((0, 0), (1, 1))) == ((0, 0), (1, 0), (0, 1), (1, 1))


def test_polygon_to_bbox():
    assert geometry.polygon_to_bbox(((0, 0), (1, 0), (0, 1), (1, 1))) == ((0, 0), (1, 1))


def test_resolve_enclosing_bbox():
    assert geometry.resolve_enclosing_bbox([((0, 0.5), (1, 0)), ((0.5, 0), (1, 0.25))]) == ((0, 0), (1, 0.5))


def test_rbbox_to_polygon():
    assert (
        geometry.rbbox_to_polygon((.1, .1, .2, .2, 0)) == np.array([[0, .2], [0, 0], [.2, 0], [.2, .2]], np.float32)
    ).all()


def test_polygon_to_rbbox():
    pred = geometry.polygon_to_rbbox([[.2, 0], [0, 0], [0, .2], [.2, .2]])[:4]
    target = (.1, .1, .2, .2)
    assert all(abs(i - j) <= 1e-7 for (i, j) in zip(pred, target))


def test_resolve_enclosing_rbbox():
    pred = geometry.resolve_enclosing_rbbox([(.2, .2, .05, .05, 0), (.2, .2, .2, .2, 0)])[:4]
    target = (.2, .2, .2, .2)
    assert all(abs(i - j) <= 1e-7 for (i, j) in zip(pred, target))
