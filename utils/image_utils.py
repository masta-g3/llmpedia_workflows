# Utilities for managing image paths and retrieval

import os
import logging
from typing import Optional
import utils.paper_utils as pu # Assuming paper_utils handles S3 downloads

logger = logging.getLogger(__name__) # Use standard logger setup

class ImageManager:
    """Centralized image management for tweet generation."""

    def __init__(self, data_path: str):
        self.data_path = data_path
        self.bucket_map = {
            "art": "arxiv-art",
            "first_page": "arxiv-first-page",
        }
        self.local_dirs = {
            "art": os.path.join(data_path, "arxiv_art"),
            "first_page": os.path.join(data_path, "arxiv_first_page"),
            "figure": os.path.join(data_path, "arxiv_md"),
        }

    def get_image_path(
        self, arxiv_code: str, image_type: str, figure_filename: Optional[str] = None
    ) -> Optional[str]:
        """Get path to an image, downloading from S3 if needed."""
        if image_type == "figure":
            if figure_filename is None:
                raise ValueError("figure_filename is required for figure images")
            image_path = os.path.join(
                self.local_dirs["figure"], arxiv_code, figure_filename
            )
            if not os.path.exists(image_path):
                logger.warning(f"Figure image not found: {image_path}")
                return None
        else:
            image_path = os.path.join(self.local_dirs[image_type], f"{arxiv_code}.png")
            if not os.path.exists(image_path):
                bucket_name = self.bucket_map.get(image_type)
                if bucket_name:
                    logger.info(f"Downloading {image_type} image from {bucket_name}")
                    pu.download_s3_file(
                        arxiv_code, bucket_name=bucket_name, prefix="data", format="png"
                    )
            if not os.path.exists(image_path):
                logger.warning(
                    f"{image_type.capitalize()} image not found: {image_path}"
                )
                return None
        return image_path 