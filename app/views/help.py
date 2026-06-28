from flask import Blueprint, render_template
from flask_login import login_required
from app.services.settings_service import settings_service
from app.utils.decorators import get_visible_menus

help_bp = Blueprint('help', __name__)

@help_bp.route('/')
@login_required
def index():
    whatsapp = settings_service.get('whatsapp_support') or ''
    # Strip non-digits
    whatsapp = ''.join(c for c in whatsapp if c.isdigit())
    return render_template('help/index.html',
        whatsapp_number=whatsapp,
        menus=get_visible_menus(current_user))

# Fix: import current_user
from flask_login import current_user
