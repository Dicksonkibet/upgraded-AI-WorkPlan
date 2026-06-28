from app import db
from datetime import datetime


class SystemSetting(db.Model):
    """Simple key/value store for settings the admin can change from the UI.

    Values are always stored as strings; SettingsService is responsible
    for casting them to the right type (int, str, etc.) on the way out.
    """
    __tablename__ = 'system_settings'

    id         = db.Column(db.Integer, primary_key=True)
    key        = db.Column(db.String(100), unique=True, nullable=False)
    value      = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SystemSetting {self.key}={self.value!r}>'
