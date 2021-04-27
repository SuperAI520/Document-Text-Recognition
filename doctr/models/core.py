# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.


import numpy as np
from typing import List, Any, Tuple
from .detection import DetectionPredictor
from .recognition import RecognitionPredictor
from ._utils import extract_crops
from doctr.documents.elements import Word, Line, Block, Page, Document
from doctr.utils.repr import NestedObject

__all__ = ['OCRPredictor', 'DocumentBuilder']


class OCRPredictor(NestedObject):
    """Implements an object able to localize and identify text elements in a set of documents

    Args:
        det_predictor: detection module
        reco_predictor: recognition module
    """

    _children_names: List[str] = ['det_predictor', 'reco_predictor', 'doc_builder']

    def __init__(
        self,
        det_predictor: DetectionPredictor,
        reco_predictor: RecognitionPredictor,
    ) -> None:

        self.det_predictor = det_predictor
        self.reco_predictor = reco_predictor
        self.doc_builder = DocumentBuilder()

    def __call__(
        self,
        pages: List[np.ndarray],
        **kwargs: Any,
    ) -> Document:

        # Dimension check
        if any(page.ndim != 3 for page in pages):
            raise ValueError("incorrect input shape: all pages are expected to be multi-channel 2D images.")

        # Localize text elements
        boxes = self.det_predictor(pages, **kwargs)
        # Crop images
        crops = [crop for page, _boxes in zip(pages, boxes) for crop in extract_crops(page, _boxes[:, :4])]
        # Identify character sequences
        char_sequences = self.reco_predictor(crops, **kwargs)

        # Reorganize
        out = self.doc_builder(boxes, char_sequences, [page.shape[:2] for page in pages])

        return out


class DocumentBuilder(NestedObject):
    """Implements a document builder

    Args:
        resolve_lines: whether words should be automatically grouped into lines
        resolve_blocks: whether lines should be automatically grouped into blocks
        paragraph_break: relative length of the minimum space separating paragraphs
    """

    def __init__(
        self,
        resolve_lines: bool = False,
        resolve_blocks: bool = False,
        paragraph_break: float = 0.035
    ) -> None:

        self.resolve_lines = resolve_lines

        if resolve_blocks:
            raise NotImplementedError

        self.paragraph_break = paragraph_break

    @staticmethod
    def _sort_boxes(boxes: np.ndarray) -> np.ndarray:
        """Sort bounding boxes from top to bottom, left to right

        Args:
            boxes: bounding boxes of shape (N, 4)

        Returns:
            indices of ordered boxes of shape (N,)
        """
        return (boxes[:, 0] + 2 * boxes[:, 3] / np.median(boxes[:, 3] - boxes[:, 1])).argsort()

    def _resolve_sub_lines(self, boxes: np.ndarray, words: List[int]) -> List[List[int]]:
        """Split a line in sub_lines

        Args:
            boxes: bounding boxes of shape (N, 4)
            words: list of indexes for the words of the line

        Returns:
            A list of (sub-)lines computed from the original line (words)
        """
        lines = []
        # Sort words horizontally
        words = [words[j] for j in np.argsort([boxes[i, 0] for i in words]).tolist()]
        # Eventually split line horizontally
        if len(words) < 2:
            lines.append(words)
        else:
            sub_line = [words[0]]
            for i in words[1:]:
                horiz_break = True

                prev_box = boxes[sub_line[-1]]
                # If distance between boxes is lower than paragraph break, same sub-line
                if (boxes[i, 0] - prev_box[2]) < self.paragraph_break:
                    horiz_break = False

                if horiz_break:
                    lines.append(sub_line)
                    sub_line = []

                sub_line.append(i)
            lines.append(sub_line)

        return lines

    def _resolve_lines(self, boxes: np.ndarray) -> List[List[int]]:
        """Order boxes to group them in lines

        Args:
            boxes: bounding boxes of shape (N, 4)

        Returns:
            nested list of box indices
        """
        # Compute median for boxes heights
        y_med = np.median(boxes[:, 3] - boxes[:, 1])
        # Sort boxes
        idxs = (boxes[:, 0] + 2 * boxes[:, 3] / y_med).argsort()

        lines = []
        words = [idxs[0]]  # Assign the top-left word to the first line
        # Define a mean y-center for the line
        y_center_sum = boxes[idxs[0]][[1, 3]].mean()

        for idx in idxs[1:]:
            vert_break = True

            # If y-center of the box is close enough to mean y-center of the line, same line
            if abs(boxes[idx][[1, 3]].mean() - y_center_sum / len(words)) < y_med / 2:
                vert_break = False

            if vert_break:
                # Compute sub-lines (horizontal split)
                lines.extend(self._resolve_sub_lines(boxes, words))
                words = []
                y_center_sum = 0

            words.append(idx)
            y_center_sum += boxes[idx][[1, 3]].mean()

        # Use the remaining words to form the last(s) line(s)
        if len(words) > 0:
            # Compute sub-lines (horizontal split)
            lines.extend(self._resolve_sub_lines(boxes, words))

        return lines

    def _build_blocks(self, boxes: np.ndarray, char_sequences: List[str]) -> List[Block]:
        """Gather independent words in structured blocks

        Args:
            boxes: bounding boxes of all detected words of the page, of shape (N, 4)
            char_sequences: list of all detected words of the page, of shape N

        Returns:
            list of block elements
        """

        if boxes.shape[0] != len(char_sequences):
            raise ValueError(f"Incompatible argument lengths: {boxes.shape[0]}, {len(char_sequences)}")

        if boxes.shape[0] == 0:
            return []

        # Decide whether we try to form lines
        if self.resolve_lines:
            lines = self._resolve_lines(boxes[:, :4])
        else:
            # Sort bounding boxes, one line for all boxes
            lines = [self._sort_boxes(boxes[:, :4])]

        # No automatic line grouping yet --> 1 block for all lines
        blocks = [
            Block(
                [Line(
                    [Word(
                        char_sequences[idx],
                        boxes[idx, 4],
                        ((boxes[idx, 0], boxes[idx, 1]), (boxes[idx, 2], boxes[idx, 3]))
                    ) for idx in line]
                ) for line in lines]
            )
        ]

        return blocks

    def extra_repr(self) -> str:
        return f"resolve_lines={self.resolve_lines}, paragraph_break={self.paragraph_break}"

    def __call__(
        self,
        boxes: List[np.ndarray],
        char_sequences: List[str],
        page_shapes: List[Tuple[int, int]]
    ) -> Document:
        """Re-arrange detected words into structured blocks

        Args:
            boxes: list of localization predictions for all words, of shape (N, 5)
            char_sequences: list of all word values, of size N
            page_shape: shape of each page

        Returns:
            list of documents
        """

        # Check the number of crops for each page
        page_idx, crop_idx = 0, 0
        _pages = []
        for page_boxes in boxes:
            # Assemble all detected words into structured blocks
            _pages.append(
                Page(
                    self._build_blocks(
                        page_boxes,
                        char_sequences[crop_idx: crop_idx + page_boxes.shape[0]]
                    ),
                    page_idx,
                    page_shapes[page_idx],
                )
            )
            crop_idx += page_boxes.shape[0]
            page_idx += 1

        return Document(_pages)
