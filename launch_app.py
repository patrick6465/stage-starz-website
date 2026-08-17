"""Railway entrypoint that layers launch-readiness routes onto the Stage Starz app."""

from app import app, log_activity, permission_required
from class_content_editor import register_class_content_editor
from launch_foundation import register_launch_foundation

register_launch_foundation(app, permission_required, log_activity)
register_class_content_editor(app, permission_required, log_activity)

__all__ = ["app"]
