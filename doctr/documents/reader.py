# Copyright (C) 2021, Mindee.
# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

import os
import fitz
import numpy as np
import pathlib
import cv2
import math
import warnings
from typing import Union, List, Tuple, Optional

__all__ = ['read_documents']

DEFAULT_RES_MIN = int(0.8e6)
DEFAULT_RES_MAX = int(3e6)


def read_documents(
    filepaths: List[str],
    num_pixels: Optional[int] = None
) -> Tuple[List[List[np.ndarray]], List[List[str]], List[List[Tuple[int, int]]]]:
    """
    Always return tuple of:
        - list of documents, each doc is a numpy image pages list (valid RGB image with 3 channels)
        - list of document names, each page inside a doc has a different name
        - list of document shapes
    optional : list of sizes
    :param filepaths: list of pdf filepaths to prepare, or a filepath (str)
    :param num_pixels: output num_pixels of images
    """

    documents_imgs = []
    documents_names = []

    for f_document in filepaths:

        pages_imgs, pages_names = prepare_pdf_from_filepath(
            f_document, num_pixels=num_pixels
        )

        documents_imgs.append(pages_imgs)
        documents_names.append(pages_names)

    documents_shapes = [[page.shape[:2] for page in doc] for doc in documents_imgs]

    return documents_imgs, documents_names, documents_shapes


def prepare_pdf_from_filepath(
    filepath: str,
    num_pixels: Optional[int] = None
) -> Tuple[List[np.ndarray], List[str]]:
    """
    Read a pdf from a filepath with fitz
    :param filepath: filepath of the .pdf file
    :param num_pixels: output num_pixels
    """

    filename = pathlib.PurePosixPath(filepath).stem
    pdf = fitz.open(filepath)
    imgs, names = convert_pdf_pages_to_imgs(
        pdf=pdf, filename=filename, page_idxs=None, num_pixels=num_pixels)
    return imgs, names


def convert_pdf_pages_to_imgs(
    pdf: fitz.fitz.Document,
    filename: str,
    page_idxs: Optional[List[int]],
    num_pixels: Optional[int] = None,
    img_type: str = "np"
) -> Tuple[List[np.ndarray], List[str]]:
    """
    Convert pdf pages to numpy arrays.
    :param pdf: pdf doc opened with fitz
    :param filename: pdf name to rename pages
    :param img_type: The format of the output pages, can be "np" or "png"
    :param page_idxs: Int or list of int to specify which pages to take. If None, takes all pages.
    :param num_pixels: Output num_pixels in pixels. If None, use the default page size (DPI@96).
    Can be used as a tuple to force a minimum/maximum num_pixels dynamically.
    :param with_names: Output list of names in return statement.
    :return: List of numpy arrays of dtype uint8.
    """

    imgs = []
    names = []

    page_idxs = page_idxs or [x + 1 for x in range(len(pdf))]

    # Iterate over pages
    for i in page_idxs:

        page = pdf[i - 1]

        out_res = max(min(num_pixels, DEFAULT_RES_MAX), DEFAULT_RES_MIN) if isinstance(num_pixels, int) else None

        # Make numpy array
        pixmap = page_to_pixmap(page, out_res)

        if img_type == "np":
            imgs.append(pixmap_to_numpy(pixmap))
        else:
            if img_type != "png":
                warnings.warn(f"could not convert to {img_type}, returning png")
            imgs.append(pixmap.getImageData(output="png"))

    names = [f"{filename}-p{str(idx).zfill(3)}" for idx in page_idxs]

    return imgs, names


def page_to_pixmap(
    page: fitz.fitz.Page,
    num_pixels: Optional[int] = None
) -> fitz.fitz.Pixmap:
    """
    Convert a fitz page to a fitz bitmap
    """
    out_res = num_pixels
    box = page.MediaBox
    in_res = int(box[2]) * int(box[3])

    if not out_res:
        out_res = max(min(in_res, DEFAULT_RES_MAX), DEFAULT_RES_MIN)

    scale = min(20, np.sqrt(out_res / in_res))

    return page.getPixmap(matrix=fitz.Matrix(scale, scale))


def pixmap_to_numpy(
    pixmap: fitz.fitz.Pixmap,
    channel_order: str = "RGB"
) -> np.ndarray:
    """
    convert a fitz pixmap to a numpy image
    """
    stream = pixmap.getImageData()
    stream = np.frombuffer(stream, dtype=np.uint8)
    img = cv2.imdecode(stream, cv2.IMREAD_UNCHANGED)
    if channel_order == "RGB":
        return img[:, :, ::-1]
    elif channel_order == "BGR":
        return img
    else:
        raise Exception("Invalid channel parameter! Must be RGB or BGR")
