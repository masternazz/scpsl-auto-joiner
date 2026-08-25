"""Windows OCR helpers for locating visible SCP:SL controls."""
import asyncio
import io

from PIL import ImageGrab
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

import winput


def _capture_window(hwnd):
    rect = winput.get_window_rect(hwnd)
    if not rect:
        return None, None
    image = ImageGrab.grab(bbox=rect, include_layered_windows=True)
    return rect, image


async def _recognize(image):
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(encoded.getvalue())
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return []
    result = await engine.recognize_async(bitmap)
    matches = []
    for line in result.lines:
        for word in line.words:
            matches.append({"text": word.text, "x": word.bounding_rect.x, "y": word.bounding_rect.y, "width": word.bounding_rect.width, "height": word.bounding_rect.height})
    return matches


def read_window(hwnd):
    """Return OCR words in window-relative coordinates."""
    rect, image = _capture_window(hwnd)
    if image is None:
        return []
    try:
        return asyncio.run(_recognize(image))
    except Exception:
        return []


def find_center(words, phrases):
    """Find a case-insensitive word/phrase and return its relative center."""
    wanted = [phrase.lower() for phrase in phrases]
    for word in words:
        text = word["text"].strip().lower()
        if any(text == phrase or phrase in text for phrase in wanted):
            return int(word["x"] + word["width"] / 2), int(word["y"] + word["height"] / 2)
    return None
