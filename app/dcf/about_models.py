from datetime import datetime, timezone

from app.extensions import db


class AboutPage(db.Model):
    """Single-row table for the editable About/profile page. Any logged-in
    user can edit it (this is a small trusted-team app with one real user;
    see auth/models.py — there's no separate admin-role column to check)."""

    __tablename__ = "about_page"

    id = db.Column(db.Integer, primary_key=True)  # always 1
    name = db.Column(db.String(255), nullable=False, default="Sheshang Choksi")
    tagline = db.Column(db.String(255), nullable=False, default="Financial Analyst & Developer")
    about_me = db.Column(db.Text, nullable=False, default="")
    academics = db.Column(db.Text, nullable=False, default="")
    experience = db.Column(db.Text, nullable=False, default="")
    photo_data = db.Column(db.LargeBinary, nullable=True)
    resume_data = db.Column(db.LargeBinary, nullable=True)
    resume_filename = db.Column(db.String(255), nullable=True)
    linkedin_url = db.Column(db.String(500), nullable=False, default="")
    github_url = db.Column(db.String(500), nullable=False, default="")
    twitter_url = db.Column(db.String(500), nullable=False, default="")
    email = db.Column(db.String(255), nullable=False, default="")
    phone = db.Column(db.String(50), nullable=False, default="")
    website_url = db.Column(db.String(500), nullable=False, default="")
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )
