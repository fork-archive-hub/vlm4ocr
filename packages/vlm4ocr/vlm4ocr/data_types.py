import os
from typing import List, Dict, Literal
from PIL import Image
from dataclasses import dataclass, field
from vlm4ocr.utils import get_default_page_delimiter, ImageProcessor

OutputMode = Literal["markdown", "HTML", "text", "JSON"]

@dataclass
class OCRResult:
    """
    This class represents the result of an OCR process.

    Parameters:
    ----------
    input_dir : str
        The directory where the input files (e.g., image, PDF, tiff) are located.
    output_mode : str
        The output format. Must be 'markdown', 'HTML', or 'text'.
    pages : List[str]
        A list of strings, each representing a page of the OCR result.
    """
    input_dir: str
    output_mode: OutputMode
    pages: List[dict] = field(default_factory=list)
    filename: str = field(init=False)
    status: str = field(init=False, default="processing")
    messages_log: List[List[Dict[str,str]]] = field(default_factory=list)

    def __post_init__(self):
        """
        Called after the dataclass-generated __init__ method.
        Used for validation and initializing derived fields.
        """
        self.filename = os.path.basename(self.input_dir)

        # output_mode validation
        if self.output_mode not in ["markdown", "HTML", "text", "JSON"]:
            raise ValueError("output_mode must be 'markdown', 'HTML', 'text', or 'JSON'")

        # pages validation 
        if not isinstance(self.pages, list):
            raise ValueError("pages must be a list of dict")
        for i, page_content in enumerate(self.pages):
            if not isinstance(page_content, dict):
                raise ValueError(f"Each page must be a dict. Page at index {i} is not a dict.")


    def add_page(self, text:str, image_processing_status: dict):
        """
        This method adds a new page to the OCRResult object.

        Parameters:
        ----------
        text : str
            The OCR result text of the page.
        image_processing_status : dict
            A dictionary containing the image processing status for the page.
            It can include keys like 'rotate_correction', 'max_dimension_pixels', etc.
        """
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        if not isinstance(image_processing_status, dict):
            raise ValueError("image_processing_status must be a dict")
        
        page = {
            "text": text,
            "image_processing_status": image_processing_status
        }
        self.pages.append(page)

    def get_page(self, idx):
        if not isinstance(idx, int):
            raise ValueError("Index must be an integer")
        if idx < 0 or idx >= len(self.pages):
            raise IndexError(f"Index out of range. The OCRResult has {len(self.pages)} pages, but index {idx} was requested.")
        
        return self.pages[idx]

    def clear_messages_log(self):
        self.messages_log = []

    def add_messages_to_log(self, messages: List[Dict[str,str]]):
        if not isinstance(messages, list):
            raise ValueError("messages must be a list of dict")
        
        self.messages_log.extend(messages)

    def get_messages_log(self) -> List[List[Dict[str,str]]]:
        return self.messages_log.copy()

    def __len__(self):
        return len(self.pages)
    
    def __iter__(self):
        return iter(self.pages)
    
    def __repr__(self):
        return f"OCRResult(filename={self.filename}, output_mode={self.output_mode}, pages_count={len(self.pages)}, status={self.status})"
    
    def to_string(self, page_delimiter:str="auto") -> str:
        """
        Convert the OCRResult object to a string representation.

        Parameters:
        ----------
        page_delimiter : str, Optional
            Only applies if separate_pages = True. The delimiter to use between PDF pages. 
            if 'auto', it will be set to the default page delimiter for the output mode: 
            'markdown' -> '\n\n---\n\n'
            'HTML' -> '<br><br>'
            'text' -> '\n\n---\n\n'
        """
        if not isinstance(page_delimiter, str):
            raise ValueError("page_delimiter must be a string")
        
        if page_delimiter == "auto":
            self.page_delimiter = get_default_page_delimiter(self.output_mode)
        else:
            self.page_delimiter = page_delimiter

        return self.page_delimiter.join([page.get("text", "") for page in self.pages])
    
@dataclass    
class FewShotExample:
    """
    This class represents a few-shot example for OCR tasks.

    Parameters:
    ----------
    image : PIL.Image.Image
        The image associated with the example.
    text : str
        The expected OCR result text for the image.
    rotate_correction : bool, Optional
        If True, applies rotate correction to the images using pytesseract.
    max_dimension_pixels : int, Optional
        The maximum dimension of the image in pixels. Original dimensions will be resized to fit in. If None, no resizing is applied.
    """
    image: Image.Image
    text: str
    rotate_correction: bool = False
    max_dimension_pixels: int = None
    def __post_init__(self):
        if not isinstance(self.image, Image.Image):
            raise ValueError("image must be a PIL.Image.Image object")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        
        if self.rotate_correction or self.max_dimension_pixels is not None:
            self.image_processor = ImageProcessor()

        # Rotate correction if specified
        if self.rotate_correction:
            self.image, _ = self.image_processor.rotate_correction(self.image)

        # Resize image if max_dimension_pixels is specified
        if self.max_dimension_pixels is not None:
            self.image, _ = self.image_processor.resize(image=self.image, max_dimension_pixels=self.max_dimension_pixels)
