"""Recover legacy PDF crop coordinates and render them at a higher DPI."""

from __future__ import annotations

import zlib
import math
from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass, replace

import pymupdf


_DARK_PIXEL_TABLE = bytes(1 if value < 220 else 0 for value in range(256))


@dataclass(frozen=True)
class CropLocation:
    page_index: int | None
    x0: float | None
    y0: float | None
    x1: float | None
    y1: float | None
    confidence: float
    ambiguous: bool = False
    is_blank: bool = False


def _row_hash(rgb_row: bytes) -> int:
    # PDF pages in this bank are monochrome. Thresholding the red channel keeps
    # the locator stable across small anti-aliasing differences.
    return zlib.crc32(rgb_row[0::3].translate(_DARK_PIXEL_TABLE))


def _row_hashes(pixmap: pymupdf.Pixmap, typecode: str = 'I') -> array:
    samples = bytes(pixmap.samples)
    stride = pixmap.width * pixmap.n
    return array(
        typecode,
        (
            _row_hash(samples[y * stride:(y + 1) * stride])
            for y in range(pixmap.height)
        ),
    )


def _dark_pixel_count(pixmap: pymupdf.Pixmap) -> int:
    red = bytes(pixmap.samples)[0::pixmap.n]
    return sum(red.translate(_DARK_PIXEL_TABLE))


class LegacyCropLocator:
    """Locate 108-DPI, full-width PNG crops inside their exact source PDF."""

    def __init__(self, document: pymupdf.Document, source_dpi: int = 108):
        self.document = document
        self.source_dpi = source_dpi
        self.scale = source_dpi / 72.0
        self.page_heights: list[int] = []
        # A packed 32-bit value uses the upper 16 bits for the page and lower
        # 16 for the row. This is far smaller than millions of Python tuples on
        # the production 2 GiB VPS.
        self.index = defaultdict(lambda: array('I'))
        for page_index, page in enumerate(document):
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(self.scale, self.scale),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            hashes = _row_hashes(pixmap)
            self.page_heights.append(pixmap.height)
            for row, value in enumerate(hashes):
                self.index[(pixmap.width, value)].append((page_index << 16) | row)

    def locate(
        self,
        image_data: bytes,
        previous_end: tuple[int, int] | None = None,
    ) -> tuple[CropLocation, tuple[int, int] | None]:
        pixmap = pymupdf.Pixmap(image_data)
        if pixmap.n != 3:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
        if _dark_pixel_count(pixmap) <= 10:
            return CropLocation(
                None, None, None, None, None, 1.0, is_blank=True,
            ), previous_end

        hashes = _row_hashes(pixmap)
        votes = Counter()
        informative_rows = 0
        for asset_row, value in enumerate(hashes):
            positions = self.index.get((pixmap.width, value), ())
            # Pure-white rows can occur thousands of times and provide no
            # location information. Headers still remain below this threshold.
            if not positions or len(positions) > 300:
                continue
            informative_rows += 1
            for packed_position in positions:
                page_index = packed_position >> 16
                page_row = packed_position & 0xFFFF
                start_row = page_row - asset_row
                if (
                    start_row >= 0
                    and start_row + pixmap.height <= self.page_heights[page_index]
                ):
                    votes[(page_index, start_row)] += 1

        if not votes or votes.most_common(1)[0][1] < 5:
            raise ValueError(
                f'Could not safely locate a {pixmap.width}x{pixmap.height} legacy crop.'
            )
        best_score = votes.most_common(1)[0][1]
        candidates = sorted(position for position, score in votes.items() if score == best_score)
        chosen = candidates[0]
        if previous_end is not None and len(candidates) > 1:
            previous_page, previous_row = previous_end
            forward = [
                candidate
                for candidate in candidates
                if candidate[0] > previous_page
                or (candidate[0] == previous_page and candidate[1] >= previous_row - 3)
            ]
            if forward:
                chosen = forward[0]

        page_index, start_row = chosen
        scale = self.scale
        page_width = self.document[page_index].rect.width
        location = CropLocation(
            page_index=page_index,
            x0=0.0,
            y0=start_row / scale,
            x1=page_width,
            y1=(start_row + pixmap.height) / scale,
            confidence=best_score / max(1, informative_rows),
            ambiguous=len(candidates) > 1,
        )
        return location, (page_index, start_row + pixmap.height)


class FormulaAwareCropAdjuster:
    """Move text-link anchors above tall inline formula bounds.

    Some source PDFs place the question label at the vertical centre of a
    matrix. Their internal link anchor therefore cuts through the matrix. PDF
    text blocks retain the complete formula bounds and let us move that edge to
    a small margin above the formula without guessing from raster pixels.
    """

    def __init__(
        self,
        document: pymupdf.Document,
        margin: float = 3.0,
        tolerance: float = 1.5,
        max_up: float = 90.0,
    ):
        self.document = document
        self.margin = margin
        self.tolerance = tolerance
        self.max_up = max_up
        self.page_blocks = []
        for page in document:
            blocks = [
                pymupdf.Rect(block[:4])
                for block in page.get_text('blocks')
                if block[3] > block[1]
            ]
            # Determinant bars and some matrix brackets are PDF vector paths,
            # not text. Their full-height bounds connect otherwise separate
            # formula rows and reveal the true top of the expression.
            blocks.extend(
                pymupdf.Rect(drawing['rect'])
                for drawing in page.get_drawings()
                if drawing['rect'].y1 > drawing['rect'].y0
            )
            self.page_blocks.append(blocks)

    def boundary(self, page_index: int, anchor: float) -> float:
        page_height = self.document[page_index].rect.height
        if anchor <= self.tolerance:
            return 0.0
        if anchor >= page_height - self.tolerance:
            return page_height
        overlapping_tops = [
            block.y0
            for block in self.page_blocks[page_index]
            if block.y0 <= anchor + self.tolerance
            and block.y1 >= anchor - self.tolerance
            and anchor - block.y0 <= self.max_up
        ]
        if not overlapping_tops:
            return anchor
        return max(0.0, min(anchor, min(overlapping_tops) - self.margin))

    def adjust(self, location: CropLocation) -> CropLocation:
        if location.page_index is None or location.is_blank:
            return location
        y0 = self.boundary(location.page_index, location.y0)
        y1 = self.boundary(location.page_index, location.y1)
        if y1 <= y0 + 1.0:
            raise ValueError(
                f'Formula-aware bounds collapsed on page {location.page_index + 1}: '
                f'{y0:.2f}–{y1:.2f}.'
            )
        return replace(location, y0=y0, y1=y1)


def render_pdf_crop(
    document: pymupdf.Document,
    location: CropLocation,
    dpi: int,
) -> tuple[bytes, int, int]:
    if location.page_index is None:
        raise ValueError('A blank crop has no PDF coordinates.')
    pixmap = document[location.page_index].get_pixmap(
        matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0),
        clip=pymupdf.Rect(location.x0, location.y0, location.x1, location.y1),
        colorspace=pymupdf.csRGB,
        alpha=False,
    )
    pixmap.set_dpi(dpi, dpi)
    return pixmap.tobytes('png'), pixmap.width, pixmap.height


def render_blank_crop(width: int, height: int, dpi: int) -> tuple[bytes, int, int]:
    pixmap = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, max(1, width), max(1, height)),
        False,
    )
    pixmap.clear_with(255)
    pixmap.set_dpi(dpi, dpi)
    return pixmap.tobytes('png'), pixmap.width, pixmap.height


def trailing_edge_fragment_start(
    image_data: bytes,
    dpi: int,
    *,
    max_points: float = 18.0,
    separator_points: float = 3.0,
    edge_points: float = 1.5,
) -> int | None:
    """Locate ink cut by the lower edge after a safe blank-row separator.

    Legacy question crops meet at PDF link anchors. Tall integrals, matrices and
    limits can start above that anchor, leaving their upper fragment at the end
    of the preceding crop. We only recover a fragment when ink reaches the crop
    edge and a real whitespace run separates it from the preceding question.
    """
    pixmap = pymupdf.Pixmap(image_data)
    if pixmap.n not in {3, 4}:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    max_rows = max(1, math.ceil(max_points * dpi / 72.0))
    separator_rows = max(3, math.ceil(separator_points * dpi / 72.0))
    edge_rows = max(2, math.ceil(edge_points * dpi / 72.0))
    start = max(0, pixmap.height - max_rows)
    samples = bytes(pixmap.samples)
    dark_rows = []
    for y in range(start, pixmap.height):
        row = samples[y * pixmap.stride:(y + 1) * pixmap.stride]
        dark_pixels = row[0::pixmap.n].translate(_DARK_PIXEL_TABLE).count(1)
        dark_rows.append(dark_pixels > 2)
    if not any(dark_rows[-edge_rows:]):
        return None

    last_separator_end = None
    run_start = None
    for index, is_dark in enumerate(dark_rows):
        if not is_dark and run_start is None:
            run_start = index
        elif is_dark and run_start is not None:
            if index - run_start >= separator_rows:
                last_separator_end = index
            run_start = None
    if last_separator_end is None or not any(dark_rows[last_separator_end:]):
        return None
    return start + last_separator_end


def crop_pixmap_rows(image_data: bytes, y0: int, y1: int, dpi: int) -> bytes:
    source = pymupdf.Pixmap(image_data)
    y0 = max(0, min(source.height, y0))
    y1 = max(y0, min(source.height, y1))
    output = pymupdf.Pixmap(
        pymupdf.csRGB, pymupdf.IRect(0, 0, source.width, max(1, y1 - y0)), False,
    )
    output.clear_with(255)
    source.set_origin(0, -y0)
    output.copy(source, pymupdf.IRect(0, 0, source.width, max(1, y1 - y0)))
    output.set_dpi(dpi, dpi)
    return output.tobytes('png')


def reframe_crop_image(
    image_data: bytes,
    dpi: int,
    *,
    leading_fragment: bytes | None = None,
    trim_bottom_rows: int = 0,
) -> tuple[bytes, int, int, int]:
    """Prepend a recovered edge fragment and optionally remove it from source."""
    current = pymupdf.Pixmap(image_data)
    leading = pymupdf.Pixmap(leading_fragment) if leading_fragment else None
    body_height = max(1, current.height - max(0, trim_bottom_rows))
    leading_height = leading.height if leading else 0
    width = current.width
    output = pymupdf.Pixmap(
        pymupdf.csRGB, pymupdf.IRect(0, 0, width, leading_height + body_height), False,
    )
    output.clear_with(255)
    if leading is not None:
        leading.set_origin(0, 0)
        output.copy(leading, pymupdf.IRect(0, 0, min(width, leading.width), leading_height))
    current.set_origin(0, leading_height)
    output.copy(current, pymupdf.IRect(0, leading_height, width, leading_height + body_height))
    output.set_dpi(dpi, dpi)
    return output.tobytes('png'), width, output.height, leading_height
