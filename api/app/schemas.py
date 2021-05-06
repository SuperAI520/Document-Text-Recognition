# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

from pydantic import BaseModel, Field
from typing import Tuple


# Recognition output
class RecognitionOut(BaseModel):
    value: str = Field(..., example="Hello")


class DetectionOut(BaseModel):
    box: Tuple[float, float, float, float]
