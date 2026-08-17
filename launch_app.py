"""Railway entrypoint that layers launch-readiness routes onto the Stage Starz app."""

from app import app, log_activity, permission_required, save_uploaded_image
from admin_editor_fixes import register_admin_editor_fixes
from bundled_assets import install_bundled_assets
from class_content_editor import CLASS_PAGES, register_class_content_editor
from competition_site_fixes import register_competition_site_fixes
from config import UPLOAD_FOLDER
from launch_foundation import register_launch_foundation

# Materialize the high-quality bundled Teen team image before any page can request it.
install_bundled_assets()

# Competition program pages use the same yearly text/photo editor as class pages.
CLASS_PAGES["teen_competition"] = {
    "label": "Teen Competition Team",
    "filename": "teen-competition-team.html",
    "audience": "Ages 14+ • Int2–Advanced",
    "built_in_hero_image": "/assets/images/teen-competition-team.webp",
}

register_launch_foundation(app, permission_required, log_activity)
register_class_content_editor(app, permission_required, log_activity)
register_competition_site_fixes(app)
register_admin_editor_fixes(app, UPLOAD_FOLDER, save_uploaded_image, log_activity)

__all__ = ["app"]
