"""Recover legacy PDF crop coordinates and render them at a higher DPI."""

from __future__ import annotations

import zlib
from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass

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
