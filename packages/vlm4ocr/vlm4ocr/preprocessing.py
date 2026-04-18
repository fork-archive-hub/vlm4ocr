import re
import asyncio
import importlib.util
import importlib.resources
import warnings
from typing import Tuple, Literal, Optional, TYPE_CHECKING
from PIL import Image

if TYPE_CHECKING:
    from vlm4ocr.vlm_engines import VLMEngine


RotateCorrectionMethod = Literal["tesseract", "vlm"]


class ImageProcessor:
    def __init__(self, vlm_engine: Optional["VLMEngine"] = None):
        """
        Image preprocessing utilities for OCR: rotation correction and resizing.

        Parameters:
        ----------
        vlm_engine : VLMEngine, Optional
            Required only when rotation correction is performed via method="vlm".
        """
        self.has_tesseract = importlib.util.find_spec("pytesseract") is not None
        self.vlm_engine = vlm_engine
        self._orientation_system_prompt: Optional[str] = None

    def _load_orientation_prompt(self) -> str:
        if self._orientation_system_prompt is None:
            prompt_path = importlib.resources.files('vlm4ocr.assets.default_prompt_templates').joinpath('orientation_system_prompt.txt')
            with prompt_path.open('r', encoding='utf-8') as f:
                self._orientation_system_prompt = f.read()
        return self._orientation_system_prompt

    @staticmethod
    def _parse_angle(response_text: str) -> Optional[int]:
        """
        Extract the first integer found in the VLM response and normalize to [0, 360).
        Returns None if no integer is present.
        """
        match = re.search(r"\d+", response_text)
        if match is None:
            return None
        angle = int(match.group(0)) % 360
        return angle

    def rotate_correction(self, image: Image.Image, method: RotateCorrectionMethod = "tesseract") -> Tuple[Image.Image, int]:
        """
        Correct the rotation of an image.

        Parameters:
        ----------
        image : Image.Image
            The image to be corrected.
        method : {"tesseract", "vlm"}
            "tesseract" uses pytesseract OSD. "vlm" prompts the configured VLM engine.

        Returns:
        -------
        Tuple[Image.Image, int]
            The corrected image and the rotation angle applied (degrees).
        """
        if method == "tesseract":
            return self._rotate_correction_tesseract_osd(image)
        if method == "vlm":
            return self._rotate_correction_vlm(image)
        raise ValueError(f"Unknown rotate_correction method: {method!r}. Must be 'tesseract' or 'vlm'.")

    async def rotate_correction_async(self, image: Image.Image, method: RotateCorrectionMethod = "tesseract") -> Tuple[Image.Image, int]:
        """
        Asynchronous version of rotate_correction.
        """
        if method == "tesseract":
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._rotate_correction_tesseract_osd, image)
        if method == "vlm":
            return await self._rotate_correction_vlm_async(image)
        raise ValueError(f"Unknown rotate_correction method: {method!r}. Must be 'tesseract' or 'vlm'.")

    def _rotate_correction_tesseract_osd(self, image: Image.Image) -> Tuple[Image.Image, int]:
        """
        Use Tesseract OSD to detect and correct the rotation.
        """
        if importlib.util.find_spec("pytesseract") is None:
            raise ImportError("pytesseract is not installed. Please install it to use this feature.")

        import pytesseract

        try:
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            rotation_angle = osd['rotate']
            if rotation_angle != 0:
                return image.rotate(rotation_angle, expand=True), rotation_angle
            return image, 0
        except Exception as e:
            print(f"Error correcting image rotation: {e}")
            raise ValueError(f"Failed to correct image rotation: {e}") from e

    def _rotate_correction_vlm(self, image: Image.Image) -> Tuple[Image.Image, int]:
        """
        Prompt the configured VLM engine to detect orientation and rotate accordingly.
        """
        if self.vlm_engine is None:
            raise ValueError("vlm_engine is required for rotate_correction method='vlm'.")

        system_prompt = self._load_orientation_prompt()
        messages = self.vlm_engine.get_ocr_messages(
            system_prompt=system_prompt,
            user_prompt=None,
            image=image,
        )
        response = self.vlm_engine.chat(messages)
        return self._apply_vlm_response(image, response.get("response", ""))

    async def _rotate_correction_vlm_async(self, image: Image.Image) -> Tuple[Image.Image, int]:
        if self.vlm_engine is None:
            raise ValueError("vlm_engine is required for rotate_correction method='vlm'.")

        system_prompt = self._load_orientation_prompt()
        messages = self.vlm_engine.get_ocr_messages(
            system_prompt=system_prompt,
            user_prompt=None,
            image=image,
        )
        response = await self.vlm_engine.chat_async(messages)
        return self._apply_vlm_response(image, response.get("response", ""))

    def _apply_vlm_response(self, image: Image.Image, response_text: str) -> Tuple[Image.Image, int]:
        angle = self._parse_angle(response_text)
        if angle is None:
            warnings.warn(
                f"VLM orientation response contained no integer angle; skipping rotation. Response: {response_text!r}"
            )
            return image, 0
        if angle == 0:
            return image, 0
        return image.rotate(angle, expand=True), angle

    def resize(self, image: Image.Image, max_dimension_pixels: int = 4000) -> Tuple[Image.Image, bool]:
        """
        Resize the image to fit within the specified maximum dimension while maintaining aspect ratio.
        """
        width, height = image.size
        if width > max_dimension_pixels or height > max_dimension_pixels:
            if width > height:
                new_width = max_dimension_pixels
                new_height = int((max_dimension_pixels / width) * height)
            else:
                new_height = max_dimension_pixels
                new_width = int((max_dimension_pixels / height) * width)
            return image.resize((new_width, new_height), resample=Image.Resampling.LANCZOS), True

        return image, False

    async def resize_async(self, image: Image.Image, max_dimension_pixels: int = 4000) -> Tuple[Image.Image, bool]:
        """
        Asynchronous version of resize.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.resize, image, max_dimension_pixels)
