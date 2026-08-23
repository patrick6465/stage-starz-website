"""Railway entrypoint that layers launch-readiness routes onto the Stage Starz app."""

import app as app_module
import class_content_editor as class_editor

from app import app, log_activity, permission_required
from admin_editor_fixes import register_admin_editor_fixes
from bundled_assets import install_bundled_assets
from class_content_editor import CLASS_PAGES, register_class_content_editor
from classes_hero_asset import register_classes_hero_asset
from classes_hero_layout import register_classes_hero_layout
from command_center_mobile_polish import register_command_center_mobile_polish
from command_center_time_polish import register_command_center_time_polish
from competition_editor_support import install_competition_editor_support
from competition_site_fixes import register_competition_site_fixes
from config import UPLOAD_FOLDER
from homepage_mobile_gallery_polish import register_homepage_mobile_gallery_polish
from launch_foundation import register_launch_foundation
from order_status_fix import register_order_status_fix
from performance_mobile_polish import register_performance_mobile_polish
from performance_workspace_polish import register_performance_workspace_polish
from persistent_media import (
    delete_persistent_image,
    register_persistent_media,
    save_persistent_image,
)
from persistent_videos import register_persistent_videos
from product_media_caption_support import install_product_media_captions
from product_media_gallery import register_product_media_gallery
from program_hero_finalizer import register_program_hero_finalizer
from program_hero_panels import register_program_hero_panels
from public_logo_polish import register_public_logo_polish
from public_page_text_editor import register_public_page_text_editor
from public_page_text_extras import install_public_page_text_extras
from public_studio_gallery import register_public_studio_gallery
from public_video_routes import register_public_video_routes
from reports_never_500 import register_reports_never_500
from reports_postgres_fix import register_reports_postgres_fix
from routes_inventory import register_inventory_routes
from routes_packing import register_packing_routes
from routes_variants import register_variant_routes
from store_mobile_delete_safety import register_store_mobile_delete_safety
from store_two_shop_experience import register_two_shop_experience
from store_two_shop_injection_fix import register_two_shop_injection_fix
from store_workspace_polish import register_store_workspace_polish
from studio_active_tab_polish import register_studio_active_tab_polish
from studio_detail_title_polish import register_studio_detail_title_polish
from studio_gallery_admin_nav import register_studio_gallery_admin_nav
from studio_gallery_manager import register_studio_gallery_manager
from studio_workspace_polish import register_studio_workspace_polish
from teen_image_asset import register_teen_image_asset
from ticketing_mobile_designer_polish import register_ticketing_mobile_designer_polish
from ticketing_operations_mobile_polish import register_ticketing_operations_mobile_polish
from video_admin_nav import register_video_admin_nav
from video_player_polish import register_video_player_polish
from website_video_manager import register_website_video_manager
from website_workspace_polish import register_website_workspace_polish

# Keep existing bundled assets available for older references.
install_bundled_assets()

# Uploaded photos are stored in the persistent database and mirrored back to the
# Railway filesystem at every restart/deploy. Patch all existing upload/delete
# call sites so Homepage Editor, Media Library and Class/Team Editor share it.
register_persistent_media(app)
app_module.save_uploaded_image = save_persistent_image
app_module.delete_uploaded_image = delete_persistent_image
class_editor._save_uploaded_image = save_persistent_image

# Website videos use the same persistence pattern as uploaded photos: back them
# up to the persistent database and restore them to Railway disk after deploys.
register_persistent_videos(app)

# Website videos live in Railway media storage and can be assigned to the
# homepage performance panel or the Musical Theater Competition spotlight.
register_website_video_manager(app, permission_required, log_activity)

# Store products can use a four-photo gallery plus one optional uploaded video.
# The primary photo remains in products.image_url; extra media is kept in its own
# persistent product_media table and reuses the existing image/video storage.
register_product_media_gallery(
    app,
    permission_required,
    save_persistent_image,
    delete_persistent_image,
    log_activity,
)

# Photos 2–4 are flexible gallery positions. Each one can carry an editable
# customer-facing caption such as Size Chart, Back View, or Sleeve Detail.
install_product_media_captions(app)

# Keep destructive Store Manager actions visually separated on phones and replace
# the generic delete prompt with a product-specific irreversible-action warning.
register_store_mobile_delete_safety(app)

# Split the public store into seasonal Spirit Wear and year-round merchandise.
# Existing products default to Spirit Wear so the current catalog stays intact.
register_two_shop_experience(app, permission_required, log_activity)

# Ensure the Store Availability panel and two public shop-choice cards are added
# even after the shared workspace CSS has already introduced their class names.
register_two_shop_injection_fix(app)

# Render assigned videos directly while the public HTML page is being served.
# This is especially important for competition.html, which otherwise comes from
# send_from_directory as a streaming response that is unreliable to rewrite later.
register_public_video_routes(app)
register_video_player_polish(app)
register_video_admin_nav(app)

# Parent Hub, Dancer Portal and the public Recital page keep their editable copy
# in the database so wording changes survive Railway deployments. Include their
# page-specific buttons and link labels while leaving destination URLs protected.
install_public_page_text_extras()
register_public_page_text_editor(app, permission_required, log_activity)

# Studio Gallery photos use the same persistent image store as the other website
# editors. Only valid DB-backed files are rendered on the public pages, preventing
# broken static binary assets from leaving blank cards after a deployment.
register_studio_gallery_manager(app, permission_required, log_activity)
register_public_studio_gallery(app)

# On phones, temporarily slide the homepage quick-action bar away while the
# Studio Gallery is in view so captions and photos are never covered.
register_homepage_mobile_gallery_polish(app)

# Replace any legacy generic star badge in public-page headers with the actual
# Stage Starz logo so older static pages stay consistent with the homepage.
register_public_logo_polish(app)

# Serve the sharp built-in image assets from cache-busting routes.
register_teen_image_asset(app)
register_classes_hero_asset(app)

# Competition program pages use the same yearly text/photo editor as class pages.
CLASS_PAGES["teen_competition"] = {
    "label": "Teen Competition Team",
    "filename": "teen-competition-team.html",
    "audience": "Ages 14+ • Int2–Advanced",
    "built_in_hero_image": "/assets/images/teen-competition-team-sharp.webp",
}
install_competition_editor_support(app)

register_launch_foundation(app, permission_required, log_activity)
register_class_content_editor(app, permission_required, log_activity)
register_competition_site_fixes(app)
register_classes_hero_layout(app)

# Register the finalizer before the panel renderer. Flask runs after_request
# handlers in reverse registration order, so the renderer builds the photo card
# first and the finalizer then removes legacy backgrounds and applies saved photos.
register_program_hero_finalizer(app)
register_program_hero_panels(app)

register_admin_editor_fixes(app, UPLOAD_FOLDER, save_persistent_image, log_activity)

# Replace the legacy order-status handler so a successful status commit is never
# turned into a 500 page by optional CRM/family synchronization or audit logging.
register_order_status_fix(app)

# Register Store & Orders routes that live in modular route files. The shared
# workspace links to these pages, so they must be attached to the Railway app
# before the workspace shell is applied.
register_inventory_routes(app)
register_variant_routes(app)
register_packing_routes(app)

# Replace the legacy Reports endpoint with a PostgreSQL-safe implementation that
# normalizes database dates and numeric values before rendering the dashboard.
register_reports_postgres_fix(app, permission_required)

# Final containment for Reports: an unexpected live-schema edge case must never
# take down the page with the global 500 handler. It will render a controlled
# safe-mode Reports page and preserve the full exception in Railway logs.
register_reports_never_500(app)

# Keep mobile Command Center work areas compact without changing backend routes.
register_command_center_mobile_polish(app)

# Show greetings and activity history in the studio's Eastern time zone rather
# than Railway server UTC, and hide raw database microseconds from the dashboard.
register_command_center_time_polish(app)

# Add Studio Gallery to the shared Website Management navigation. Register this
# before the workspace shell because Flask runs after_request handlers in reverse;
# the shell is built first and this hook can then append the Gallery tab.
register_studio_gallery_admin_nav(app)

# Give all Website Management tools one shared desktop/mobile workspace shell.
register_website_workspace_polish(app)

# Register the active-tab and detail-title polish before the shell. Flask executes
# after_request handlers in reverse order, so the shell is injected first; these
# refinements then see the finished Studio Operations workspace markup.
register_studio_active_tab_polish(app)
register_studio_detail_title_polish(app)

# Keep family, student, class, attendance, billing and costume screens inside one
# consistent Studio Operations workspace, including their detail/edit pages.
register_studio_workspace_polish(app)

# Make door check-in, ticket-order and seat-hold detail screens practical on
# phones while preserving the existing ticketing workflows and database logic.
register_ticketing_operations_mobile_polish(app)

# Add touch-friendly panning and mobile instructions to the large reserved-
# ticketing venue canvas without changing the desktop coordinate designer.
register_ticketing_mobile_designer_polish(app)

# Register the Recital & Competition mobile finisher before the shared shell.
# Flask executes after_request handlers in reverse order, so the shell is injected
# first and this pass can then refine its dock and older page layouts safely.
register_performance_mobile_polish(app)

# Keep competition, recital, production and reserved-ticketing screens in one
# shared performance workspace, including event/show/routine/order detail pages.
register_performance_workspace_polish(app)

# Keep product, order, inventory, fulfillment and store-report screens inside one
# shared Store & Orders workspace while leaving the public storefront untouched.
register_store_workspace_polish(app)

__all__ = ["app"]