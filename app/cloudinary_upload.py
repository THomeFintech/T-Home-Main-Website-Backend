"""
app/cloudinary_upload.py

Async helper used directly in FastAPI route handlers.
Delegates all Cloudinary config to app/services/cloudinary_service.py —
do NOT call cloudinary.config() here.

Usage in a route:
    from app.cloudinary_upload import upload_to_cloudinary

    file_url, public_id = await upload_to_cloudinary(file, folder="thome_docs/kyc")
"""
import io

from fastapi import HTTPException, UploadFile

from app.services.cloudinary_service import upload_file


async def upload_to_cloudinary(
    file: UploadFile,
    folder: str = "thome_docs",
) -> tuple[str, str]:
    """
    Read a FastAPI UploadFile and upload it to Cloudinary.

    Args:
        file:   The UploadFile object from the request.
        folder: Cloudinary folder to organise uploads.

    Returns:
        (secure_url, public_id) — both strings.

    Raises:
        HTTPException 500: If the Cloudinary upload fails for any reason.
    """
    try:
        file_bytes = await file.read()
        result = upload_file(io.BytesIO(file_bytes), folder=folder)
        return result["url"], result["public_id"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cloudinary upload failed for '{file.filename}': {str(e)}",
        )