# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

import tensorflow as tf
import tensorflow_addons as tfa
import numpy as np
from typing import Tuple, Dict
from doctr.utils.geometry import rotate_boxes

__all__ = ["invert_colors", "rotate"]


def invert_colors(img: tf.Tensor, min_val: float = 0.6) -> tf.Tensor:
    out = tf.image.rgb_to_grayscale(img)  # Convert to gray
    # Random RGB shift
    shift_shape = [img.shape[0], 1, 1, 3] if img.ndim == 4 else [1, 1, 3]
    rgb_shift = tf.random.uniform(shape=shift_shape, minval=min_val, maxval=1)
    # Inverse the color
    if out.dtype == tf.uint8:
        out = tf.cast(tf.cast(out, dtype=tf.float32) * rgb_shift, dtype=tf.uint8)
    else:
        out *= rgb_shift
    # Inverse the color
    out = 255 - out if out.dtype == tf.uint8 else 1 - out
    return out


def rotate(
    img: tf.Tensor,
    target: Dict[str, np.ndarray],
    angle: float
) -> Tuple[tf.Tensor, Dict[str, np.ndarray]]:
    """Rotate image around the center, interpolation=NEAREST, pad with 0 (black)

    Args:
        img: image to rotate
        target: dict with array of boxes to rotate as well, and array of flags
        angle: angle in degrees. +: counter-clockwise, -: clockwise

    Returns:
        A tuple of rotated img (tensor), rotated target (dict)
    """
    rotated_img = tfa.image.rotate(img, angles=angle, fill_value=0.0)  # Interpolation NEAREST by default
    boxes = target["boxes"]
    if target["boxes"].dtype == int:
        # Compute relative boxes
        boxes = boxes.astype(float)
        boxes[:, [0, 2]] = boxes[:, [0, 2]] / img.shape[1]
        boxes[:, [1, 3]] = boxes[:, [1, 3]] / img.shape[0]
    # Compute rotated bboxes: xmin, ymin, xmax, ymax --> x, y, w, h, alpha
    r_boxes = rotate_boxes(boxes, angle=angle, min_angle=1)
    if target["boxes"].dtype == int:
        # Back to absolute boxes
        r_boxes[:, [0, 2]] *= img.shape[1]
        r_boxes[:, [1, 3]] *= img.shape[0]
    target["boxes"] = r_boxes
    return rotated_img, target
