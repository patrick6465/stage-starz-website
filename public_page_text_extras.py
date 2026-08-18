from __future__ import annotations

from public_page_text_editor import PAGE_DEFINITIONS


def install_public_page_text_extras() -> None:
    """Add page-specific button/link/label copy to the safe text editor."""

    parent = PAGE_DEFINITIONS["parent_hub"]
    parent["groups"].append(
        {
            "label": "Buttons & Link Labels",
            "fields": [
                ("hero_button_1", "Hero button 1", ".hero-copy .actions .btn:nth-child(1)", "Open Parent Portal", False),
                ("hero_button_2", "Hero button 2", ".hero-copy .actions .btn:nth-child(2)", "2027 Recital Info", False),
                ("panel_button", "Coming-up button", ".hero-panel .actions .btn", "Buy Tickets", False),
                ("resource_1_kicker", "Jackrabbit card label", "#resources .resource-card:nth-child(1) .card-kicker", "Account", False),
                ("resource_1_link", "Jackrabbit card link text", "#resources .resource-card:nth-child(1) .card-link", "Open Portal →", False),
                ("resource_2_kicker", "Recital card label", "#resources .resource-card:nth-child(2) .card-kicker", "Recital", False),
                ("resource_2_link", "Recital card link text", "#resources .resource-card:nth-child(2) .card-link", "View Recital Info →", False),
                ("resource_3_kicker", "Events card label", "#resources .resource-card:nth-child(3) .card-kicker", "Calendar", False),
                ("resource_3_link", "Events card link text", "#resources .resource-card:nth-child(3) .card-link", "View Events →", False),
                ("resource_4_kicker", "Dancer Portal card label", "#resources .resource-card:nth-child(4) .card-kicker", "Dancers", False),
                ("resource_4_link", "Dancer Portal card link text", "#resources .resource-card:nth-child(4) .card-link", "Open Dancer Portal →", False),
                ("resource_5_kicker", "Classes card label", "#resources .resource-card:nth-child(5) .card-kicker", "Classes", False),
                ("resource_5_link", "Classes card link text", "#resources .resource-card:nth-child(5) .card-link", "Find Classes →", False),
                ("resource_6_kicker", "Competition card label", "#resources .resource-card:nth-child(6) .card-kicker", "Team", False),
                ("resource_6_link", "Competition card link text", "#resources .resource-card:nth-child(6) .card-link", "Competition Hub →", False),
                ("resource_7_kicker", "Store card label", "#resources .resource-card:nth-child(7) .card-kicker", "Shop", False),
                ("resource_7_link", "Store card link text", "#resources .resource-card:nth-child(7) .card-link", "Visit Store →", False),
                ("resource_8_kicker", "Contact card label", "#resources .resource-card:nth-child(8) .card-kicker", "Help", False),
                ("resource_8_link", "Contact card link text", "#resources .resource-card:nth-child(8) .card-link", "Contact Stage Starz →", False),
                ("spotlight_button_1", "Recital spotlight button 1", ".spotlight .actions .btn:nth-child(1)", "Full Recital Details", False),
                ("spotlight_button_2", "Recital spotlight button 2", ".spotlight .actions .btn:nth-child(2)", "Buy Tickets", False),
                ("spotlight_button_3", "Recital spotlight button 3", ".spotlight .actions .btn:nth-child(3)", "Get Directions", False),
                ("reg_1", "Registration label 1", "#registration .reg-link:nth-child(1) span:first-child", "Preschool", False),
                ("reg_2", "Registration label 2", "#registration .reg-link:nth-child(2) span:first-child", "Primary", False),
                ("reg_3", "Registration label 3", "#registration .reg-link:nth-child(3) span:first-child", "Elementary", False),
                ("reg_4", "Registration label 4", "#registration .reg-link:nth-child(4) span:first-child", "Intermediate / Advanced", False),
                ("reg_5", "Registration label 5", "#registration .reg-link:nth-child(5) span:first-child", "Specialized Classes", False),
                ("reg_6", "Registration label 6", "#registration .reg-link:nth-child(6) span:first-child", "Competition Teams", False),
                ("reg_button", "View-all-classes button", "#registration .actions .btn", "View All Classes", False),
                ("contact_phone", "Contact phone link", ".contact-box .contact-row:nth-of-type(1)", "Call: (734) 497-3740", False),
                ("contact_email", "Contact email link", ".contact-box .contact-row:nth-of-type(2)", "Email: stagestarzdance@aol.com", False),
                ("contact_page", "Contact page link", ".contact-box .contact-row:nth-of-type(3)", "Open Contact Page →", False),
            ],
        }
    )

    dancer = PAGE_DEFINITIONS["dancer_portal"]
    dancer["groups"].append(
        {
            "label": "Buttons & Link Labels",
            "fields": [
                ("hero_button_1", "Hero button 1", ".hero-copy .actions .btn:nth-child(1)", "2027 Recital Info", False),
                ("hero_button_2", "Hero button 2", ".hero-copy .actions .btn:nth-child(2)", "Open Jackrabbit Portal", False),
                ("panel_button", "Recital panel button", ".hero-panel .actions .btn", "Buy Tickets", False),
                ("resource_1_kicker", "Recital card label", "#resources .resource-card:nth-child(1) .card-kicker", "Performance", False),
                ("resource_1_link", "Recital card link text", "#resources .resource-card:nth-child(1) .card-link", "Open Recital Info →", False),
                ("resource_2_kicker", "Classes card label", "#resources .resource-card:nth-child(2) .card-kicker", "Training", False),
                ("resource_2_link", "Classes card link text", "#resources .resource-card:nth-child(2) .card-link", "Explore Classes →", False),
                ("resource_3_kicker", "Competition card label", "#resources .resource-card:nth-child(3) .card-kicker", "Competition", False),
                ("resource_3_link", "Competition card link text", "#resources .resource-card:nth-child(3) .card-link", "Competition Resources →", False),
                ("resource_4_kicker", "Team-only card label", "#resources .resource-card:nth-child(4) .card-kicker", "Team Members", False),
                ("resource_4_link", "Team-only card link text", "#resources .resource-card:nth-child(4) .card-link", "Open Team Area →", False),
                ("resource_5_kicker", "Store card label", "#resources .resource-card:nth-child(5) .card-kicker", "Spirit Wear", False),
                ("resource_5_link", "Store card link text", "#resources .resource-card:nth-child(5) .card-link", "Shop Stage Starz →", False),
                ("resource_6_kicker", "Jackrabbit card label", "#resources .resource-card:nth-child(6) .card-kicker", "Account", False),
                ("resource_6_link", "Jackrabbit card link text", "#resources .resource-card:nth-child(6) .card-link", "Open Jackrabbit →", False),
                ("spotlight_button_1", "Readiness button 1", ".spotlight .actions .btn:nth-child(1)", "Full Recital Details", False),
                ("spotlight_button_2", "Readiness button 2", ".spotlight .actions .btn:nth-child(2)", "Meyer Theater Directions", False),
                ("reg_1", "Registration label 1", ".registration-card .reg-link:nth-child(1) span:first-child", "Preschool", False),
                ("reg_2", "Registration label 2", ".registration-card .reg-link:nth-child(2) span:first-child", "Primary", False),
                ("reg_3", "Registration label 3", ".registration-card .reg-link:nth-child(3) span:first-child", "Elementary", False),
                ("reg_4", "Registration label 4", ".registration-card .reg-link:nth-child(4) span:first-child", "Intermediate / Advanced", False),
                ("reg_5", "Registration label 5", ".registration-card .reg-link:nth-child(5) span:first-child", "Specialized Classes", False),
                ("reg_6", "Registration label 6", ".registration-card .reg-link:nth-child(6) span:first-child", "Competition Teams", False),
                ("contact_phone", "Contact phone link", ".contact-box .contact-row:nth-of-type(1)", "Call (734) 497-3740 →", False),
                ("contact_email", "Contact email link", ".contact-box .contact-row:nth-of-type(2)", "Email Stage Starz →", False),
                ("contact_parent_hub", "Parent Hub link", ".contact-box .contact-row:nth-of-type(3)", "Open Parent Hub →", False),
            ],
        }
    )

    recital = PAGE_DEFINITIONS["recital_2027"]
    recital["groups"].append(
        {
            "label": "Button Labels",
            "fields": [
                ("hero_button_1", "Hero button 1", ".hero .actions .btn:nth-child(1)", "Buy Recital Tickets", False),
                ("hero_button_2", "Hero button 2", ".hero .actions .btn:nth-child(2)", "Recital Details", False),
                ("venue_button_1", "Venue button 1", ".venue-copy .actions .btn:nth-child(1)", "Get Directions", False),
                ("venue_button_2", "Venue button 2", ".venue-copy .actions .btn:nth-child(2)", "Buy Tickets", False),
                ("ticket_button_1", "Ticket button 1", ".ticket-card .actions .btn:nth-child(1)", "Buy Recital Tickets", False),
                ("ticket_button_2", "Ticket button 2", ".ticket-card .actions .btn:nth-child(2)", "Get Directions", False),
                ("ticket_button_3", "Ticket button 3", ".ticket-card .actions .btn:nth-child(3)", "Parent Resources", False),
                ("back_button", "Back button", ".back-link .btn", "← All Events", False),
            ],
        }
    )
