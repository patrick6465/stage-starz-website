STAGE STARZ RESERVED TICKETING V2.0

REPLACE:
- app.py
- templates/ticket_venue.html

INSTALL:
git checkout railway-deployment
git add app.py templates/ticket_venue.html
git commit -m "Add mouse drag positioning to venue designer"
git push origin railway-deployment

NEW MOUSE CONTROLS:
- Click and drag any seating section on the venue canvas.
- Click and drag the stage, crew booth, labels, and other theater objects.
- Positions save automatically when the mouse button is released.
- A live status message confirms the saved X and Y coordinates.
- The numeric X/Y fields update automatically after each drag.
- Items cannot be dragged outside the canvas boundaries.
- If saving fails, the item returns to its previous position.
- Pointer events support both mouse and touchscreen dragging.
- Dragging is disabled automatically after ticket history exists.
- The live recital ticket-selling map continues using the saved coordinates.

TEST:
1. Deploy V2.0.
2. Verify /health and /ready.
3. Open an unfinished venue.
4. Drag Upper Orchestra to a new location.
5. Confirm the status reports Saved.
6. Confirm its X/Y fields changed.
7. Refresh the page and confirm the section remains in its new position.
8. Drag the stage and crew booth and repeat the test.
