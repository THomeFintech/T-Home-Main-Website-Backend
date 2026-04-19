"""
app/services/cloudinary_service.py

Single Cloudinary configuration + upload helper for the entire app.
All other files should import from here — do NOT call cloudinary.config() elsewhere.

Required environment variables (.env):
    CLOUDINARY_CLOUD_NAME=your_cloud_name
    CLOUDINARY_API_KEY=your_api_key
    CLOUDINARY_API_SECRET=your_api_secret

Install:
    pip install cloudinary python-dotenv
"""
import os

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

# ── Configure once at import time ─────────────────────────────────────────────
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,   # always use https URLs
)


def upload_file(file, folder: str = "thome_docs") -> dict:
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="auto",
        access_mode="public",
        overwrite=False,
    )

    # 🔥 DEBUG PRINTS
    print("=== CLOUDINARY UPLOAD DEBUG ===")
    print("URL:", result.get("secure_url"))
    print("PUBLIC ID:", result.get("public_id"))
    print("FORMAT:", result.get("format"))
    print("RESOURCE TYPE:", result.get("resource_type"))
    print("================================")

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }

def delete_file(public_id: str, resource_type: str = "image") -> dict:
    """
    Delete an asset from Cloudinary by its public_id.

    Args:
        public_id:     The Cloudinary public_id returned at upload time.
        resource_type: "image", "video", or "raw". Default is "image".
                       For PDFs use "raw".

    Returns:
        Cloudinary API response dict, e.g. {"result": "ok"}.
    """
    return cloudinary.uploader.destroy(public_id, resource_type=resource_type)