import base64

from app.dcf.about_models import AboutPage
from app.extensions import db


def get_about():
    """Get the (singleton) about-page row, creating it with sensible
    defaults on first access."""
    entry = db.session.get(AboutPage, 1)
    if entry is None:
        entry = AboutPage(
            id=1,
            name="Sheshang Choksi",
            tagline="Financial Analyst & Developer",
            about_me="Passionate about financial markets and technology. Building tools to democratize financial analysis.",
            academics="MBA in Finance | B.Tech in Computer Science",
            experience="Financial Analysis, Startup Valuation, and Software Development.",
        )
        db.session.add(entry)
        db.session.commit()
    return entry


def update_about(fields, photo_bytes=None, resume_bytes=None, resume_filename=None):
    entry = get_about()
    for key in ("name", "tagline", "about_me", "academics", "experience",
                "linkedin_url", "github_url", "twitter_url", "email", "phone", "website_url"):
        if key in fields:
            setattr(entry, key, fields[key])
    if photo_bytes:
        entry.photo_data = photo_bytes
    if resume_bytes:
        entry.resume_data = resume_bytes
        entry.resume_filename = resume_filename
    db.session.commit()
    return entry


def photo_base64(entry):
    if entry and entry.photo_data:
        return base64.b64encode(entry.photo_data).decode()
    return None


def resize_photo(file_storage, size=(500, 500)):
    """Resize an uploaded photo to a square JPEG, same behaviour as the
    Streamlit version (auto-resize, flatten transparency onto white)."""
    from PIL import Image
    import io

    img = Image.open(file_storage)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    img = img.resize(size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
