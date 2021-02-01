# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras.models import Sequential
from typing import Tuple, Dict, Any, Optional

from .. import vgg
from ..utils import load_pretrained_params
from .core import RecognitionModel

__all__ = ['CRNN', 'crnn_vgg16_bn']

default_cfgs: Dict[str, Dict[str, Any]] = {
    'crnn_vgg16_bn': {'backbone': 'vgg16_bn', 'num_classes': 30, 'rnn_units': 128,
                      'input_size': (32, 128, 3),
                      'url': None},
}


class CRNN(RecognitionModel):
    """Implements a CRNN architecture as described in `"Convolutional RNN: an Enhanced Model for Extracting Features
    from Sequential Data" <https://arxiv.org/pdf/1602.05875.pdf>`_.

    Args:
        feature_extractor: the backbone serving as feature extractor
        num_classes: number of output classes
        rnn_units: number of units in the LSTM layers
    """
    def __init__(
        self,
        feature_extractor: tf.keras.Model,
        num_classes: int = 30,
        rnn_units: int = 128
    ) -> None:
        super().__init__()
        self.feat_extractor = feature_extractor
        self.decoder = Sequential(
            [
                layers.Bidirectional(layers.LSTM(units=rnn_units, return_sequences=True)),
                layers.Bidirectional(layers.LSTM(units=rnn_units, return_sequences=True)),
                layers.Dense(units=num_classes + 1)
            ]
        )

    def call(
        self,
        inputs: tf.Tensor,
    ) -> tf.Tensor:

        features = self.feat_extractor(inputs)
        # B x H x W x C --> B x W x H x C
        transposed_feat = tf.transpose(features, perm=[0, 2, 1, 3])
        w, h, c = transposed_feat.get_shape().as_list()[1:]
        # B x W x H x C --> B x W x H * C
        features_seq = tf.reshape(transposed_feat, shape=(-1, w, h * c))
        decoded_features = self.decoder(features_seq)

        return decoded_features


def _crnn_vgg(arch: str, pretrained: bool, input_size: Optional[Tuple[int, int, int]] = None, **kwargs: Any) -> CRNN:

    # Feature extractor
    feat_extractor = vgg.__dict__[default_cfgs[arch]['backbone']](
        input_size=input_size or default_cfgs[arch]['input_size'],
        include_top=False,
    )

    kwargs['num_classes'] = kwargs.get('num_classes', default_cfgs[arch]['num_classes'])
    kwargs['rnn_units'] = kwargs.get('rnn_units', default_cfgs[arch]['rnn_units'])

    # Build the model
    model = CRNN(feat_extractor, **kwargs)
    # Load pretrained parameters
    if pretrained:
        load_pretrained_params(model, default_cfgs[arch]['url'])

    return model


def crnn_vgg16_bn(pretrained: bool = False, **kwargs: Any) -> CRNN:
    """CRNN with a VGG-16 backbone as described in `"Convolutional RNN: an Enhanced Model for Extracting Features
    from Sequential Data" <https://arxiv.org/pdf/1602.05875.pdf>`_.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet

    Returns:
        text recognition architecture
    """

    return _crnn_vgg('crnn_vgg16_bn', pretrained, **kwargs)
