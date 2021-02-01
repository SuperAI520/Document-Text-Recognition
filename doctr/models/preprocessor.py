# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

import os
import math
import json
import tensorflow as tf
import numpy as np
from typing import Union, List, Tuple, Optional, Any, Dict


__all__ = ['PreProcessor']


class PreProcessor:
    """Implements an abstract preprocessor object

    Args:
        output_size: expected size of each page in format (H, W)
        batch_size: the size of page batches
        mean: mean value of the training distribution by channel
        std: standard deviation of the training distribution by channel
        interpolation: one of 'bilinear', 'nearest', 'bicubic', 'area', 'lanczos3', 'lanczos5'

    """

    def __init__(
        self,
        output_size: Tuple[int, int],
        batch_size: int,
        mean: Tuple[float, float, float] = (.5, .5, .5),
        std: Tuple[float, float, float] = (1., 1., 1.),
        interpolation: str = 'bilinear'
    ) -> None:

        self.output_size = output_size
        self.mean = tf.cast(mean, dtype=tf.float32)
        self.std = tf.cast(std, dtype=tf.float32)
        self.batch_size = batch_size
        self.interpolation = interpolation

    def resize(
        self,
        x: tf.Tensor
    ) -> tf.Tensor:
        raise NotImplementedError

    def normalize(
        self,
        x: tf.Tensor
    ) -> tf.Tensor:
        """Takes a tensor and moves it to [-1, 1] range

        Args:
            x: tensor ro normalize
        Returns:
            normalized tensor encoded in float32
        """
        # Re-center and scale the distribution to [-1, 1]
        return tf.cast(x, tf.float32) * (self.std / 255) - (self.mean / self.std)

    def batch_inputs(
        self,
        x: List[tf.Tensor]
    ) -> List[tf.Tensor]:
        """Gather samples into batches for inference purposes

        Args:
            x: list of samples (tf.Tensor)

        Returns:
            list of batched samples
        """

        num_batches = len(x) / self.batch_size

        # Deal with fixed-size batches
        b_images = [np.stack(x[idx * self.batch_size: (idx + 1) * self.batch_size])
                    for idx in range(int(num_batches))]
        # Deal with the last batch
        if num_batches > int(num_batches):
            b_images.append(np.asarray(x[int(num_batches) * self.batch_size:]))

        return b_images

    def __call__(
        self,
        x: List[np.ndarray]
    ) -> List[tf.Tensor]:
        """Prepare document data for model forwarding

        Args:
            x: list of images (np.array)
        Returns:
            list of page batches
        """
        # convert images to tf
        tensors = [tf.cast(sample, dtype=tf.float32) for sample in x]
        # Resize (and eventually pad) the inputs
        images = [self.resize(sample) for sample in tensors]
        # Batch them
        processed_batches = self.batch_inputs(images)
        # Normalize
        processed_batches = [self.normalize(b) for b in processed_batches]

        return processed_batches
