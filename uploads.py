import os
import uuid

from werkzeug.utils import secure_filename

ALLOWED_ATTACHMENT_EXT = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "doc", "docx"}

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def save_local_attachment(file_storage):
    """
    Зберігає PDF/картинку на диск Render (static/uploads/).
    Повертає (url, error). url є None при помилці.
    """

    if not file_storage or not file_storage.filename:
        return None, None

    ext = _ext(file_storage.filename)

    if ext not in ALLOWED_ATTACHMENT_EXT:
        return None, "Непідтримуваний формат файлу. Дозволено: PDF, зображення, DOC/DOCX."

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    safe_name = secure_filename(file_storage.filename) or "file"
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"

    file_storage.save(os.path.join(UPLOAD_DIR, stored_name))

    return f"/static/uploads/{stored_name}", None


def upload_video(file_storage):
    """
    Завантажує відео у Cloudinary.
    Повертає (url, error). url є None при помилці або якщо Cloudinary не налаштований.
    """

    if not file_storage or not file_storage.filename:
        return None, None

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if not (cloud_name and api_key and api_secret):
        return None, "Завантаження відео не налаштоване (немає ключів Cloudinary)."

    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

    try:
        result = cloudinary.uploader.upload(
            file_storage,
            resource_type="video",
            folder="sayboi_lessons",
        )
    except Exception as e:
        return None, f"Не вдалося завантажити відео: {e}"

    return result.get("secure_url"), None
