# Copyright (C) 2021-2022, Mindee.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://opensource.org/licenses/Apache-2.0> for full license details.

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import cv2
import numpy as np
from tqdm import tqdm

from .datasets import AbstractDataset
from .utils import convert_target_to_relative, crop_bboxes_from_image

__all__ = ["IMGUR5K"]


class IMGUR5K(AbstractDataset):
    """IMGUR5K dataset from `"TextStyleBrush: Transfer of Text Aesthetics from a Single Example"
    <https://arxiv.org/abs/2106.08385>`_ |
    `repository <https://github.com/facebookresearch/IMGUR5K-Handwriting-Dataset>`_.

    .. image:: https://github.com/mindee/doctr/releases/download/v0.5.0/imgur5k-grid.png
        :align: center
        :width: 630
        :height: 400

    >>> # NOTE: You need to download/generate the dataset from the repository.
    >>> from doctr.datasets import IMGUR5K
    >>> train_set = IMGUR5K(train=True, img_folder="/path/to/IMGUR5K-Handwriting-Dataset/images",
    >>>                     label_path="/path/to/IMGUR5K-Handwriting-Dataset/dataset_info/imgur5k_annotations.json")
    >>> img, target = train_set[0]
    >>> test_set = IMGUR5K(train=False, img_folder="/path/to/IMGUR5K-Handwriting-Dataset/images",
    >>>                    label_path="/path/to/IMGUR5K-Handwriting-Dataset/dataset_info/imgur5k_annotations.json")
    >>> img, target = test_set[0]

    Args:
        img_folder: folder with all the images of the dataset
        label_path: path to the annotations file of the dataset
        train: whether the subset should be the training one
        use_polygons: whether polygons should be considered as rotated bounding box (instead of straight ones)
        recognition_task: whether the dataset should be used for recognition task
        **kwargs: keyword arguments from `AbstractDataset`.
    """

    def __init__(
        self,
        img_folder: str,
        label_path: str,
        train: bool = True,
        use_polygons: bool = False,
        recognition_task: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            img_folder, pre_transforms=convert_target_to_relative if not recognition_task else None, **kwargs
        )

        # File existence check
        if not os.path.exists(label_path) or not os.path.exists(img_folder):
            raise FileNotFoundError(f"unable to locate {label_path if not os.path.exists(label_path) else img_folder}")

        self.data: List[Tuple[Union[Path, np.ndarray], Dict[str, Any]]] = []
        self.train = train
        np_dtype = np.float32

        img_names = os.listdir(img_folder)
        train_samples = int(len(img_names) * 0.9)
        set_slice = slice(train_samples) if self.train else slice(train_samples, None)

        with open(label_path) as f:
            annotation_file = json.load(f)

        for img_name in tqdm(iterable=img_names[set_slice], desc="Unpacking IMGUR5K", total=len(img_names[set_slice])):
            img_path = Path(img_folder, img_name)
            img_id = img_name.split(".")[0]

            # File existence check
            if not os.path.exists(os.path.join(self.root, img_name)):
                raise FileNotFoundError(f"unable to locate {os.path.join(self.root, img_name)}")

            # some files have no annotations which are marked with only a dot in the 'word' key
            # ref: https://github.com/facebookresearch/IMGUR5K-Handwriting-Dataset/blob/main/README.md
            if img_id not in annotation_file["index_to_ann_map"].keys():
                continue
            ann_ids = annotation_file["index_to_ann_map"][img_id]
            annotations = [annotation_file["ann_id"][a_id] for a_id in ann_ids]

            labels = [ann["word"] for ann in annotations if ann["word"] != "."]
            # x_center, y_center, width, height, angle
            _boxes = [
                list(map(float, ann["bounding_box"].strip("[ ]").split(", ")))
                for ann in annotations
                if ann["word"] != "."
            ]
            # (x, y) coordinates of top left, top right, bottom right, bottom left corners
            box_targets = [cv2.boxPoints(((box[0], box[1]), (box[2], box[3]), box[4])) for box in _boxes]

            if not use_polygons:
                # xmin, ymin, xmax, ymax
                box_targets = [np.concatenate((points.min(0), points.max(0)), axis=-1) for points in box_targets]

            # filter images without boxes
            if len(box_targets) > 0:
                if recognition_task:
                    crops = crop_bboxes_from_image(
                        img_path=os.path.join(self.root, img_name), geoms=np.asarray(box_targets, dtype=np_dtype)
                    )
                    for crop, label in zip(crops, labels):
                        self.data.append((crop, dict(labels=[label])))
                else:
                    self.data.append((img_path, dict(boxes=np.asarray(box_targets, dtype=np_dtype), labels=labels)))

    def extra_repr(self) -> str:
        return f"train={self.train}"
