# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

from fastapi import APIRouter, UploadFile, File

import tensorflow as tf

gpu_devices = tf.config.experimental.list_physical_devices('GPU')
if any(gpu_devices):
    tf.config.experimental.set_memory_growth(gpu_devices[0], True)

from doctr.models import recognition_predictor

from app.schemas import RecognitionOut


reco_predictor = recognition_predictor(pretrained=True)

router = APIRouter()


@router.post("/", response_model=RecognitionOut, status_code=200, summary="Perform text recognition")
async def text_recognition(file: UploadFile = File(...)):
    """Runs DocTR text recognition model to analyze the input"""
    img = tf.io.decode_image(file.file.read())
    out = reco_predictor(img[None, ...], training=False)
    return RecognitionOut(value=out[0])
