import tensorflow as tf
import pytest
import json
from doctr.datasets import DataGenerator


@pytest.fixture(scope="function")
def mock_detection_label(tmpdir_factory):
    folder = tmpdir_factory.mktemp("labels")
    label = {
        "boxes_1": [[[1, 2], [1, 3], [2, 1], [2, 3]], [[10, 20], [10, 30], [20, 10], [20, 30]]],
        "boxes_2": [[[3, 2], [3, 3], [4, 1], [4, 3]], [[30, 20], [30, 30], [40, 10], [40, 30]]],
        "boxes_3": [[[1, 5], [1, 8], [2, 5], [2, 8]]],
    }
    for i in range(5):
        fn = folder.join("mock_image_file_" + str(i) + ".jpeg.json")
        with open(fn, 'w') as f:
            json.dump(label, f)
    return str(folder)


def test_detection_core_generator(mock_image_folder, mock_detection_label):
    core_loader = DataGenerator(
        input_size=(1024, 1024),
        images_path=mock_image_folder,
        labels_path=mock_detection_label,
        batch_size=2,
    )
    assert core_loader.__len__() == 3
    for _, batch in enumerate(core_loader):
        batch_images, batch_polys, batch_masks = batch
        assert isinstance(batch_images, tf.Tensor)
        assert batch_images.shape[1] == batch_images.shape[2] == 1024
        assert isinstance(batch_polys, list)
        assert isinstance(batch_masks, list)
        for poly, mask in zip(batch_polys, batch_masks):
            assert len(poly) == len(mask)
            for box in poly:
                assert all(x <= 1 and y <= 1 for [x, y] in box)
