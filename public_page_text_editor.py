from __future__ import annotations

import json

from flask import flash, redirect, render_template, request

from database import get_db


PAGE_DEFINITIONS = {
    "parent_hub": {
        "label": "Parent Hub",
        "filename": "parent-hub.html",
        "public_url": "/parent-hub.html",
        "description": "Edit the public Parent Hub wording without changing its layout or links.",
        "groups": [
            {
                "label": "Hero",
                "fields": [
                    ("hero_eyebrow", "Eyebrow", ".hero-copy .eyebrow", "For Stage Starz Families", False),
                    ("hero_title", "Main heading", ".hero-copy h1", "Everything parents need, all in one place.", False),
                    ("hero_lead", "Intro paragraph", ".hero-copy .lead", "Use the Parent Hub for recital information, important dates, class registration, competition resources, studio links, and quick access to your Jackrabbit account.", True),
                    ("panel_eyebrow", "Coming-up eyebrow", ".hero-panel .eyebrow", "Coming Up", False),
                    ("panel_title", "Coming-up heading", ".hero-panel h2", "Recital 2027", False),
                    ("panel_dress_label", "Dress rehearsal label", ".hero-panel strong:nth-of-type(1)", "Dress Rehearsal", False),
                    ("panel_dress_time", "Dress rehearsal date/time", ".hero-panel strong:nth-of-type(1) + p", "Friday, June 18, 2027 • 3:00 PM–9:00 PM", False),
                    ("panel_recital_label", "Recital label", ".hero-panel strong:nth-of-type(2)", "Annual Recital", False),
                    ("panel_recital_time", "Recital date/time", ".hero-panel strong:nth-of-type(2) + p", "Saturday, June 19, 2027 • 2:00 PM", False),
                ],
            },
            {
                "label": "Family Resources",
                "fields": [
                    ("resources_eyebrow", "Section eyebrow", "#resources .section-head .eyebrow", "Quick Access", False),
                    ("resources_title", "Section heading", "#resources .section-head h2", "Family Resources", False),
                    ("resources_intro", "Section intro", "#resources .section-head p:last-child", "The most-used Stage Starz links are organized here so families can get where they need to go quickly.", True),
                    ("resource_1_title", "Jackrabbit card title", "#resources .resource-card:nth-child(1) h3", "Jackrabbit Parent Portal", False),
                    ("resource_1_copy", "Jackrabbit card text", "#resources .resource-card:nth-child(1) p", "Access your Stage Starz family account through the official Jackrabbit Parent Portal.", True),
                    ("resource_2_title", "Recital card title", "#resources .resource-card:nth-child(2) h3", "2027 Recital Information", False),
                    ("resource_2_copy", "Recital card text", "#resources .resource-card:nth-child(2) p", "Rehearsal times, recital details, Meyer Theater information, tickets, and directions.", True),
                    ("resource_3_title", "Events card title", "#resources .resource-card:nth-child(3) h3", "Events & Important Dates", False),
                    ("resource_3_copy", "Events card text", "#resources .resource-card:nth-child(3) p", "Keep up with Stage Starz events, performances, auditions, and other important dates.", True),
                    ("resource_4_title", "Dancer Portal card title", "#resources .resource-card:nth-child(4) h3", "Dancer Portal", False),
                    ("resource_4_copy", "Dancer Portal card text", "#resources .resource-card:nth-child(4) p", "Open the Stage Starz dancer resource area for dancer-specific information and tools.", True),
                    ("resource_5_title", "Classes card title", "#resources .resource-card:nth-child(5) h3", "Class Registration", False),
                    ("resource_5_copy", "Classes card text", "#resources .resource-card:nth-child(5) p", "Browse programs and open the registration pages for your dancer's age and level.", True),
                    ("resource_6_title", "Competition card title", "#resources .resource-card:nth-child(6) h3", "Competition Resources", False),
                    ("resource_6_copy", "Competition card text", "#resources .resource-card:nth-child(6) p", "Competition team information, auditions, team pages, and related registration resources.", True),
                    ("resource_7_title", "Store card title", "#resources .resource-card:nth-child(7) h3", "Stage Starz Store", False),
                    ("resource_7_copy", "Store card text", "#resources .resource-card:nth-child(7) p", "Shop Stage Starz apparel, accessories, spirit wear, and studio merchandise.", True),
                    ("resource_8_title", "Contact card title", "#resources .resource-card:nth-child(8) h3", "Contact the Studio", False),
                    ("resource_8_copy", "Contact card text", "#resources .resource-card:nth-child(8) p", "Questions about classes, costumes, recital, policies, billing, or your dancer? Reach us here.", True),
                ],
            },
            {
                "label": "Recital Spotlight",
                "fields": [
                    ("spotlight_eyebrow", "Eyebrow", ".spotlight .eyebrow", "2027 Recital Spotlight", False),
                    ("spotlight_title", "Heading", ".spotlight h2", "Meyer Theater • Monroe, Michigan", False),
                    ("spotlight_copy", "Paragraph", ".spotlight > div:first-child > p:not(.eyebrow)", "Our 2027 annual recital will be held at Meyer Theater in the La-Z-Boy Center at Monroe County Community College. Families can use the buttons below for the full recital page, ticket sales, and directions.", True),
                    ("fact_1_label", "Fact 1 label", ".recital-facts .fact:nth-child(1) span", "Dress Rehearsal", False),
                    ("fact_1_value", "Fact 1 value", ".recital-facts .fact:nth-child(1) strong", "Friday, June 18 • 3:00 PM–9:00 PM", False),
                    ("fact_2_label", "Fact 2 label", ".recital-facts .fact:nth-child(2) span", "Recital", False),
                    ("fact_2_value", "Fact 2 value", ".recital-facts .fact:nth-child(2) strong", "Saturday, June 19 • 2:00 PM", False),
                    ("fact_3_label", "Fact 3 label", ".recital-facts .fact:nth-child(3) span", "Venue", False),
                    ("fact_3_value", "Fact 3 value", ".recital-facts .fact:nth-child(3) strong", "Meyer Theater, Monroe County Community College", False),
                ],
            },
            {
                "label": "Registration & Help",
                "fields": [
                    ("registration_eyebrow", "Registration eyebrow", "#registration .eyebrow", "Registration", False),
                    ("registration_title", "Registration heading", "#registration h2", "Go directly to your dancer's program.", False),
                    ("registration_copy", "Registration paragraph", "#registration .lead", "Choose a registration area below to view current class openings and registration options.", True),
                    ("help_eyebrow", "Help eyebrow", ".help-card .eyebrow", "Parent Help", False),
                    ("help_title", "Help heading", ".help-card h2", "Need an answer from the studio?", False),
                    ("help_copy", "Help paragraph", ".help-card > p:not(.eyebrow)", "For questions that are specific to your dancer or account, contact Stage Starz directly. We can help with the topics families ask about most often.", True),
                    ("topic_1", "Help topic 1", ".topic-list .topic:nth-child(1)", "Dress code", False),
                    ("topic_2", "Help topic 2", ".topic-list .topic:nth-child(2)", "Costumes", False),
                    ("topic_3", "Help topic 3", ".topic-list .topic:nth-child(3)", "Tuition & billing", False),
                    ("topic_4", "Help topic 4", ".topic-list .topic:nth-child(4)", "Studio policies", False),
                    ("topic_5", "Help topic 5", ".topic-list .topic:nth-child(5)", "Recital questions", False),
                    ("topic_6", "Help topic 6", ".topic-list .topic:nth-child(6)", "Class placement", False),
                    ("contact_eyebrow", "Office eyebrow", ".contact-box .eyebrow", "Stage Starz Office", False),
                    ("contact_title", "Office heading", ".contact-box h3", "We're here to help.", False),
                ],
            },
        ],
    },
    "dancer_portal": {
        "label": "Dancer Portal",
        "filename": "portal.html",
        "public_url": "/portal.html",
        "description": "Edit the public dancer resource page wording without changing its layout or destination links.",
        "groups": [
            {
                "label": "Hero",
                "fields": [
                    ("hero_eyebrow", "Eyebrow", ".hero-copy .eyebrow", "Stage Starz Dancers", False),
                    ("hero_title", "Main heading", ".hero-copy h1", "Your dance season, all in one place.", False),
                    ("hero_lead", "Intro paragraph", ".hero-copy .lead", "Quick access to recital information, class registration, competition resources, the Stage Starz store, and the official Jackrabbit account portal.", True),
                    ("panel_eyebrow", "Panel eyebrow", ".hero-panel .eyebrow", "Next Big Stage", False),
                    ("panel_title", "Panel heading", ".hero-panel h2", "Recital 2027", False),
                    ("panel_1_label", "Panel item 1 label", ".hero-panel strong:nth-of-type(1)", "Dress Rehearsal", False),
                    ("panel_1_value", "Panel item 1 value", ".hero-panel strong:nth-of-type(1) + p", "Friday, June 18, 2027 • 3:00 PM–9:00 PM", False),
                    ("panel_2_label", "Panel item 2 label", ".hero-panel strong:nth-of-type(2)", "Annual Recital", False),
                    ("panel_2_value", "Panel item 2 value", ".hero-panel strong:nth-of-type(2) + p", "Saturday, June 19, 2027 • 2:00 PM", False),
                    ("panel_3_label", "Panel item 3 label", ".hero-panel strong:nth-of-type(3)", "Meyer Theater", False),
                    ("panel_3_value", "Panel item 3 value", ".hero-panel strong:nth-of-type(3) + p", "Monroe County Community College • Monroe, Michigan", False),
                ],
            },
            {
                "label": "Dancer Essentials",
                "fields": [
                    ("resources_eyebrow", "Section eyebrow", "#resources .section-head .eyebrow", "Dancer Essentials", False),
                    ("resources_title", "Section heading", "#resources .section-head h2", "Everything you need to stay connected.", False),
                    ("resources_intro", "Section intro", "#resources .section-head p:last-child", "Use these shortcuts for the most important Stage Starz dancer and family resources throughout the season.", True),
                    ("resource_1_title", "Recital card title", "#resources .resource-card:nth-child(1) h3", "2027 Recital", False),
                    ("resource_1_copy", "Recital card text", "#resources .resource-card:nth-child(1) p", "See rehearsal times, recital details, Meyer Theater information, tickets, and directions.", True),
                    ("resource_2_title", "Classes card title", "#resources .resource-card:nth-child(2) h3", "Classes & Registration", False),
                    ("resource_2_copy", "Classes card text", "#resources .resource-card:nth-child(2) p", "Browse Stage Starz programs and open the correct registration page for your dancer's level.", True),
                    ("resource_3_title", "Competition card title", "#resources .resource-card:nth-child(3) h3", "Competition Teams", False),
                    ("resource_3_copy", "Competition card text", "#resources .resource-card:nth-child(3) p", "Access team information, auditions, competition program details, and team resources.", True),
                    ("resource_4_title", "Team-only card title", "#resources .resource-card:nth-child(4) h3", "Team-Only Area", False),
                    ("resource_4_copy", "Team-only card text", "#resources .resource-card:nth-child(4) p", "Open the dedicated Stage Starz competition team resource area.", True),
                    ("resource_5_title", "Store card title", "#resources .resource-card:nth-child(5) h3", "Stardust Ship-it-Shop", False),
                    ("resource_5_copy", "Store card text", "#resources .resource-card:nth-child(5) p", "Shop Stage Starz apparel, accessories, team gear, and studio spirit wear.", True),
                    ("resource_6_title", "Jackrabbit card title", "#resources .resource-card:nth-child(6) h3", "Jackrabbit Parent Portal", False),
                    ("resource_6_copy", "Jackrabbit card text", "#resources .resource-card:nth-child(6) p", "Use the official Jackrabbit portal for account-specific family and dancer information.", True),
                ],
            },
            {
                "label": "Recital Readiness",
                "fields": [
                    ("spotlight_eyebrow", "Eyebrow", ".spotlight .eyebrow", "Recital Readiness", False),
                    ("spotlight_title", "Heading", ".spotlight h2", "Be ready for recital weekend.", False),
                    ("spotlight_copy", "Paragraph", ".spotlight > div:first-child > p:not(.eyebrow)", "Keep the important recital basics together as June approaches. Dancer-specific instructions can still be communicated by Stage Starz through normal studio channels.", True),
                    ("check_1", "Checklist item 1", ".checklist .check:nth-child(1) span:last-child", "Review your dancer's rehearsal instructions.", False),
                    ("check_2", "Checklist item 2", ".checklist .check:nth-child(2) span:last-child", "Confirm costumes, shoes, tights, and accessories.", False),
                    ("check_3", "Checklist item 3", ".checklist .check:nth-child(3) span:last-child", "Know your arrival and performance timing.", False),
                    ("check_4", "Checklist item 4", ".checklist .check:nth-child(4) span:last-child", "Purchase audience tickets through TutuTix.", False),
                ],
            },
            {
                "label": "Registration & Help",
                "fields": [
                    ("registration_eyebrow", "Registration eyebrow", ".registration-card .eyebrow", "Training & Registration", False),
                    ("registration_title", "Registration heading", ".registration-card h2", "Find your class level.", False),
                    ("registration_copy", "Registration paragraph", ".registration-card .lead", "Jump directly to the current Stage Starz class registration pages.", True),
                    ("help_eyebrow", "Quick-links eyebrow", ".help-card .eyebrow", "Quick Links", False),
                    ("help_title", "Quick-links heading", ".help-card h2", "Stay organized throughout the season.", False),
                    ("help_copy", "Quick-links paragraph", ".help-card > p:not(.eyebrow)", "For schedules, studio events, family resources, and other dancer information, use the main Stage Starz resource pages.", True),
                    ("quick_1", "Quick link 1 text", ".quick-list .quick-item:nth-child(1)", "Events & Important Dates", False),
                    ("quick_2", "Quick link 2 text", ".quick-list .quick-item:nth-child(2)", "Parent Hub", False),
                    ("quick_3", "Quick link 3 text", ".quick-list .quick-item:nth-child(3)", "Competition Auditions", False),
                    ("quick_4", "Quick link 4 text", ".quick-list .quick-item:nth-child(4)", "Studio Contact", False),
                    ("help_note", "Account note", ".help-card .note", "Personal account details such as billing, enrollment, and family-specific information should be accessed through the official Jackrabbit Parent Portal.", True),
                    ("contact_eyebrow", "Contact eyebrow", ".contact-box .eyebrow", "Need Help?", False),
                    ("contact_title", "Contact heading", ".contact-box h2", "Contact Stage Starz", False),
                    ("contact_copy", "Contact paragraph", ".contact-box > p:not(.eyebrow)", "If you're unsure where to find something or have a dancer-specific question, contact the studio directly.", True),
                ],
            },
        ],
    },
    "recital_2027": {
        "label": "2027 Recital Page",
        "filename": "recital-2027.html",
        "public_url": "/recital-2027.html",
        "description": "Edit recital dates, venue wording, event copy, and ticket messaging from the backend.",
        "groups": [
            {
                "label": "Hero",
                "fields": [
                    ("hero_eyebrow", "Eyebrow", ".hero > .eyebrow", "Annual Recital • 2027", False),
                    ("hero_title", "Main heading", ".hero > h1", "Stage Starz Recital 2027", False),
                    ("hero_lead", "Intro paragraph", ".hero > .lead", "Join our Stage Starz dancers for their annual recital at Meyer Theater in the La-Z-Boy Center at Monroe County Community College.", True),
                    ("hero_meta_1", "Date pill", ".hero-meta span:nth-child(1)", "Saturday, June 19, 2027", False),
                    ("hero_meta_2", "Time pill", ".hero-meta span:nth-child(2)", "2:00 PM", False),
                    ("hero_meta_3", "Venue pill", ".hero-meta span:nth-child(3)", "Meyer Theater • Monroe, MI", False),
                ],
            },
            {
                "label": "Dress Rehearsal & Recital",
                "fields": [
                    ("event_1_date", "Dress rehearsal date", ".event-grid .event-card:nth-child(1) .date", "Friday • June 18, 2027", False),
                    ("event_1_title", "Dress rehearsal heading", ".event-grid .event-card:nth-child(1) h2", "Dress Rehearsal", False),
                    ("event_1_time", "Dress rehearsal time", ".event-grid .event-card:nth-child(1) .time", "3:00 PM – 9:00 PM", False),
                    ("event_1_copy", "Dress rehearsal paragraph", ".event-grid .event-card:nth-child(1) p", "Dress rehearsal will be held at Meyer Theater. Additional dancer-specific instructions will be shared through Stage Starz parent communications as the recital approaches.", True),
                    ("event_2_date", "Recital date", ".event-grid .event-card:nth-child(2) .date", "Saturday • June 19, 2027", False),
                    ("event_2_title", "Recital heading", ".event-grid .event-card:nth-child(2) h2", "Recital", False),
                    ("event_2_time", "Recital time", ".event-grid .event-card:nth-child(2) .time", "2:00 PM", False),
                    ("event_2_copy", "Recital paragraph", ".event-grid .event-card:nth-child(2) p", "Stage Starz Academy of Dance takes the stage for our 2027 annual recital.", True),
                ],
            },
            {
                "label": "Venue",
                "fields": [
                    ("venue_eyebrow", "Venue eyebrow", ".venue-copy .eyebrow", "Recital Venue", False),
                    ("venue_title", "Venue heading", ".venue-copy h2", "Meyer Theater", False),
                    ("venue_address", "Venue address", ".venue-copy .address", "Monroe County Community College\nLa-Z-Boy Center\n1555 S. Raisinville Road\nMonroe, MI 48161", True),
                ],
            },
            {
                "label": "Ticket Message",
                "fields": [
                    ("ticket_eyebrow", "Ticket eyebrow", ".ticket-card .eyebrow", "Recital Tickets", False),
                    ("ticket_title", "Ticket heading", ".ticket-card h2", "Ready to join us in the audience?", False),
                    ("ticket_copy", "Ticket paragraph", ".ticket-card > p:not(.eyebrow)", "Stage Starz recital tickets are available through TutuTix. Use the button below to open the Stage Starz ticket page and choose your seats.", True),
                ],
            },
        ],
    },
}


def _all_fields(page):
    fields = []
    for group in page["groups"]:
        for key, label, selector, default, multiline in group["fields"]:
            fields.append(
                {
                    "key": key,
                    "label": label,
                    "selector": selector,
                    "default": default,
                    "multiline": multiline,
                    "group": group["label"],
                }
            )
    return fields


def ensure_public_page_text_schema() -> None:
    connection = get_db()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS public_page_text (
            page_key TEXT NOT NULL,
            field_key TEXT NOT NULL,
            value TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(page_key, field_key)
        )
        """
    )
    connection.commit()
    connection.close()


def _stored_values(page_key: str) -> dict[str, str]:
    ensure_public_page_text_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT field_key, value FROM public_page_text WHERE page_key=?",
        (page_key,),
    ).fetchall()
    connection.close()
    result = {}
    for row in rows:
        try:
            result[row["field_key"]] = row["value"]
        except (TypeError, KeyError, IndexError):
            result[row[0]] = row[1]
    return result


def _save_value(page_key: str, field_key: str, value: str) -> None:
    connection = get_db()
    connection.execute(
        """
        INSERT INTO public_page_text (page_key, field_key, value, updated_at)
        VALUES (?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(page_key, field_key) DO UPDATE SET
            value=excluded.value,
            updated_at=CURRENT_TIMESTAMP
        """,
        (page_key, field_key, value),
    )
    connection.commit()
    connection.close()


def _inject_overrides(response, page_key: str):
    response.direct_passthrough = False
    if response.status_code != 200 or response.mimetype != "text/html":
        return response

    page = PAGE_DEFINITIONS.get(page_key)
    if not page:
        return response

    stored = _stored_values(page_key)
    if not stored:
        return response

    field_map = {field["key"]: field for field in _all_fields(page)}
    updates = []
    for key, value in stored.items():
        field = field_map.get(key)
        if not field:
            continue
        updates.append(
            {
                "selector": field["selector"],
                "value": value,
                "preline": bool(field["multiline"] and "address" in key),
            }
        )

    if not updates:
        return response

    body = response.get_data(as_text=True)
    if not body or "</body>" not in body:
        return response

    payload = json.dumps(updates).replace("</", "<\\/")
    script = f"""
<style id=\"ss-public-page-text-style\">.ss-edit-preline{{white-space:pre-line}}</style>
<script id=\"ss-public-page-text-script\">
(function(){{
  var updates={payload};
  function apply(){{
    updates.forEach(function(item){{
      var node=document.querySelector(item.selector);
      if(!node)return;
      node.textContent=item.value;
      if(item.preline)node.classList.add('ss-edit-preline');
    }});
  }}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply);
  else apply();
}})();
</script>
"""
    body = body.replace("</body>", script + "</body>", 1)
    response.set_data(body)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers.pop("ETag", None)
    response.headers.pop("Last-Modified", None)
    return response


def register_public_page_text_editor(app, permission_required, log_activity=None) -> None:
    ensure_public_page_text_schema()

    @app.route("/admin/website/page-text")
    @permission_required("website")
    def public_page_text_editor():
        page_key = request.args.get("page", "parent_hub").strip()
        if page_key not in PAGE_DEFINITIONS:
            page_key = "parent_hub"
        page = PAGE_DEFINITIONS[page_key]
        stored = _stored_values(page_key)

        groups = []
        for group in page["groups"]:
            items = []
            for key, label, selector, default, multiline in group["fields"]:
                items.append(
                    {
                        "key": key,
                        "label": label,
                        "value": stored[key] if key in stored else default,
                        "default": default,
                        "multiline": multiline,
                        "is_custom": key in stored,
                    }
                )
            groups.append({"label": group["label"], "fields": items})

        return render_template(
            "public_page_text_editor.html",
            pages=PAGE_DEFINITIONS,
            page_key=page_key,
            page=page,
            groups=groups,
        )

    @app.route("/admin/website/page-text/save", methods=["POST"])
    @permission_required("website")
    def save_public_page_text():
        page_key = request.form.get("page_key", "").strip()
        page = PAGE_DEFINITIONS.get(page_key)
        if not page:
            flash("That website page could not be found.", "error")
            return redirect("/admin/website/page-text")

        for field in _all_fields(page):
            value = request.form.get(field["key"], field["default"])
            value = str(value).strip()[:5000]
            _save_value(page_key, field["key"], value)

        if log_activity:
            try:
                log_activity("Website page text updated", page["label"])
            except Exception:
                app.logger.exception("Could not log website page text update")

        flash(f"{page['label']} text was saved.", "success")
        return redirect(f"/admin/website/page-text?page={page_key}")

    @app.route("/admin/website/page-text/reset", methods=["POST"])
    @permission_required("website")
    def reset_public_page_text():
        page_key = request.form.get("page_key", "").strip()
        page = PAGE_DEFINITIONS.get(page_key)
        if not page:
            return redirect("/admin/website/page-text")

        connection = get_db()
        connection.execute("DELETE FROM public_page_text WHERE page_key=?", (page_key,))
        connection.commit()
        connection.close()
        flash(f"{page['label']} text was restored to the built-in wording.", "success")
        return redirect(f"/admin/website/page-text?page={page_key}")

    # The public pages are static files served by app.website_file. Wrap that
    # endpoint so database-backed wording is applied before the response is sent.
    endpoint = "website_file"
    original = app.view_functions.get(endpoint)
    if original and not getattr(original, "_ss_text_editor_wrapped", False):
        filename_to_key = {
            info["filename"].lower(): key for key, info in PAGE_DEFINITIONS.items()
        }

        def website_file_with_text(filename: str, *args, **kwargs):
            response = original(filename, *args, **kwargs)
            clean = (filename or "").strip("/").lower()
            page_key = filename_to_key.get(clean)
            if not page_key:
                return response
            return _inject_overrides(app.make_response(response), page_key)

        website_file_with_text._ss_text_editor_wrapped = True
        website_file_with_text.__name__ = getattr(original, "__name__", endpoint)
        app.view_functions[endpoint] = website_file_with_text
