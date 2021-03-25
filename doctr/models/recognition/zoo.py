# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

from typing import Dict, Any
from .core import RecognitionPredictor, RecognitionPreProcessor
from .. import recognition


__all__ = ["recognition_predictor"]

default_cfgs: Dict[str, Dict[str, Any]] = {
    'crnn_vgg16_bn': {'model': 'crnn_vgg16_bn', 'post_processor': 'CTCPostProcessor'},
    'crnn_resnet31': {'model': 'crnn_resnet31', 'post_processor': 'CTCPostProcessor'},
    'sar_vgg16_bn': {'model': 'sar_vgg16_bn', 'post_processor': 'SARPostProcessor'},
    'sar_resnet31': {'model': 'sar_resnet31', 'post_processor': 'SARPostProcessor'},
}


def _predictor(arch: str, pretrained: bool, **kwargs: Any) -> RecognitionPredictor:

    if default_cfgs.get(arch) is None:
        raise ValueError(f"unknown architecture '{arch}'")

    _model = recognition.__dict__[default_cfgs[arch]['model']](pretrained=pretrained)
    kwargs['mean'] = kwargs.get('mean', _model.cfg['mean'])
    kwargs['std'] = kwargs.get('std', _model.cfg['std'])
    predictor = RecognitionPredictor(
        RecognitionPreProcessor(output_size=_model.cfg['input_shape'][:2], **kwargs),
        _model,
        recognition.__dict__[default_cfgs[arch]['post_processor']](_model.cfg['vocab'])
    )

    return predictor


def recognition_predictor(arch: str = 'crnn_vgg16_bn', pretrained: bool = False, **kwargs: Any) -> RecognitionPredictor:
    """Text recognition architecture.

    Example::
        >>> import numpy as np
        >>> from doctr.models import recognition_predictor
        >>> model = recognition_predictor(pretrained=True)
        >>> input_page = (255 * np.random.rand(32, 128, 3)).astype(np.uint8)
        >>> out = model([input_page])

    Args:
        arch: name of the architecture to use ('crnn_vgg16_bn', 'crnn_resnet31', 'sar_vgg16_bn', 'sar_resnet31')
        pretrained: If True, returns a model pre-trained on our text recognition dataset

    Returns:
        Recognition predictor
    """

    return _predictor(arch, pretrained, **kwargs)
