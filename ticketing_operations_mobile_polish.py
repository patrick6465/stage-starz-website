from __future__ import annotations

from flask import request


OPERATIONS_STYLE = r"""
<style id="ss-ticketing-operations-mobile-polish">
@media (max-width: 760px) {
  body.ss-ticket-checkin-mobile .wrap,
  body.ss-ticket-order-mobile .wrap,
  body.ss-ticket-hold-mobile .wrap {
    width: calc(100% - 20px) !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-bottom: 126px !important;
  }

  body.ss-ticket-checkin-mobile .stats {
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    gap: 8px !important;
  }
  body.ss-ticket-checkin-mobile .stats .card {
    padding: 13px 9px !important;
    margin-bottom: 0 !important;
    text-align: center;
    min-width: 0;
  }
  body.ss-ticket-checkin-mobile .metric {
    font-size: 1.45rem !important;
    line-height: 1 !important;
  }
  body.ss-ticket-checkin-mobile .stats .muted {
    margin-top: 6px;
    font-size: .72rem;
    line-height: 1.15;
  }
  body.ss-ticket-checkin-mobile .scanner {
    max-width: none !important;
  }
  body.ss-ticket-checkin-mobile .scanner .rowline {
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
    gap: 8px !important;
  }
  body.ss-ticket-checkin-mobile .scanner .rowline button {
    width: 100%;
    min-height: 46px;
  }
  body.ss-ticket-checkin-mobile #scanner-video {
    min-height: 210px;
    object-fit: cover;
  }
  body.ss-ticket-checkin-mobile #scan-result {
    font-weight: 800;
    line-height: 1.4;
  }
  body.ss-ticket-checkin-mobile .ss-checkin-quickbar {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin: 0 0 14px;
  }
  body.ss-ticket-checkin-mobile .ss-checkin-quickbar a {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
    padding: 9px 10px;
    border: 1px solid rgba(80,214,208,.28);
    border-radius: 12px;
    background: rgba(80,214,208,.07);
    color: #fff !important;
    font-size: .8rem;
    font-weight: 900;
    text-align: center;
  }
  body.ss-ticket-checkin-mobile .ss-ticket-search-row {
    display: grid !important;
    grid-template-columns: 1fr auto !important;
    align-items: stretch !important;
    gap: 8px !important;
  }
  body.ss-ticket-checkin-mobile .ss-ticket-search-row button {
    min-width: 92px;
  }
  body.ss-ticket-checkin-mobile .ss-ticket-result .rowline {
    display: grid !important;
    grid-template-columns: 1fr !important;
    gap: 10px !important;
  }
  body.ss-ticket-checkin-mobile .ss-ticket-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 8px;
    width: 100%;
  }
  body.ss-ticket-checkin-mobile .ss-ticket-actions form {
    margin: 0 !important;
  }
  body.ss-ticket-checkin-mobile .ss-ticket-actions button {
    width: 100%;
    min-height: 44px;
  }

  body.ss-ticket-order-mobile .ticket {
    grid-template-columns: 1fr !important;
    gap: 10px !important;
    padding: 18px !important;
  }
  body.ss-ticket-order-mobile .ticket-code {
    overflow-wrap: anywhere;
    font-size: 1rem !important;
  }
  body.ss-ticket-order-mobile .no-print > button,
  body.ss-ticket-order-mobile .no-print > .button {
    width: 100%;
    margin: 0 0 8px !important;
    text-align: center;
  }
  body.ss-ticket-order-mobile .no-print form {
    display: grid !important;
    grid-template-columns: 1fr !important;
    gap: 8px;
    width: 100%;
    margin: 8px 0 0 !important;
  }
  body.ss-ticket-order-mobile .no-print form input,
  body.ss-ticket-order-mobile .no-print form button {
    width: 100% !important;
    min-height: 44px;
  }
  body.ss-ticket-order-mobile .ticket .no-print a {
    display: inline-flex;
    margin-top: 6px;
    padding: 9px 11px;
    border: 1px solid rgba(80,214,208,.3);
    border-radius: 10px;
    background: rgba(80,214,208,.07);
    font-weight: 850;
  }

  body.ss-ticket-hold-mobile .grid {
    gap: 12px !important;
  }
  body.ss-ticket-hold-mobile .card form button,
  body.ss-ticket-hold-mobile .card .button {
    min-height: 44px;
  }
  body.ss-ticket-hold-mobile .card form label {
    margin-top: 10px;
  }
  body.ss-ticket-hold-mobile .card form input,
  body.ss-ticket-hold-mobile .card form textarea,
  body.ss-ticket-hold-mobile .card form select {
    min-height: 44px;
  }
}

@media (max-width: 390px) {
  body.ss-ticket-checkin-mobile .stats {
    gap: 6px !important;
  }
  body.ss-ticket-checkin-mobile .stats .card {
    padding: 11px 6px !important;
  }
  body.ss-ticket-checkin-mobile .metric {
    font-size: 1.25rem !important;
  }
  body.ss-ticket-checkin-mobile .stats .muted {
    font-size: .65rem;
  }
}
</style>
"""


OPERATIONS_SCRIPT = r"""
<script id="ss-ticketing-operations-mobile-script">
document.addEventListener('DOMContentLoaded', function () {
  const path = window.location.pathname.replace(/\/$/, '');
  const checkin = /^\/admin\/ticketing\/shows\/\d+\/checkin$/.test(path);
  const order = /^\/admin\/ticketing\/orders\/\d+$/.test(path);
  const hold = /^\/admin\/ticketing\/holds\/\d+$/.test(path);

  if (checkin) {
    document.body.classList.add('ss-ticket-checkin-mobile');
    const cards = Array.from(document.querySelectorAll('main.wrap > .card'));
    const scannerCard = cards.find(card => /Camera QR Scanner/i.test(card.textContent || ''));
    const searchCard = cards.find(card => /Search purchaser/i.test(card.textContent || ''));
    const ticketCard = cards.find(card => /^\s*Tickets\s*/i.test(card.textContent || ''));

    if (scannerCard) scannerCard.id = 'door-scanner';
    if (searchCard) {
      searchCard.id = 'ticket-lookup';
      const row = searchCard.querySelector('.rowline');
      if (row) row.classList.add('ss-ticket-search-row');
    }
    if (ticketCard) {
      ticketCard.querySelectorAll('.item').forEach(item => {
        item.classList.add('ss-ticket-result');
        const row = item.querySelector('.rowline');
        if (!row) return;
        const actionWrap = row.children.length > 1 ? row.children[row.children.length - 1] : null;
        if (actionWrap) actionWrap.classList.add('ss-ticket-actions');
      });
    }

    if (scannerCard && searchCard && !document.querySelector('.ss-checkin-quickbar')) {
      const quick = document.createElement('nav');
      quick.className = 'ss-checkin-quickbar';
      quick.setAttribute('aria-label', 'Door check-in quick actions');
      quick.innerHTML = '<a href="#door-scanner">📷 Scan Ticket</a><a href="#ticket-lookup">🔎 Search Ticket</a>';
      const stats = document.querySelector('main.wrap > .stats');
      if (stats) stats.insertAdjacentElement('afterend', quick);
      else scannerCard.parentNode.insertBefore(quick, scannerCard);
    }
  }

  if (order) document.body.classList.add('ss-ticket-order-mobile');
  if (hold) document.body.classList.add('ss-ticket-hold-mobile');
});
</script>
"""


def _supported_path(path: str) -> bool:
    parts = path.split('/')
    if len(parts) == 6 and parts[:4] == ['', 'admin', 'ticketing', 'shows'] and parts[4].isdigit() and parts[5] == 'checkin':
        return True
    if len(parts) == 5 and parts[:4] == ['', 'admin', 'ticketing', 'orders'] and parts[4].isdigit():
        return True
    if len(parts) == 5 and parts[:4] == ['', 'admin', 'ticketing', 'holds'] and parts[4].isdigit():
        return True
    return False


def register_ticketing_operations_mobile_polish(app) -> None:
    """Polish ticket check-in, order, and hold detail screens for phone use."""

    @app.after_request
    def polish_ticketing_operations(response):
        if request.method != 'GET' or response.status_code != 200:
            return response
        if response.mimetype != 'text/html':
            return response

        path = request.path.rstrip('/') or '/'
        if not _supported_path(path):
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body:
                return response
            if 'id="ss-ticketing-operations-mobile-polish"' not in body and '</head>' in body:
                body = body.replace('</head>', OPERATIONS_STYLE + '</head>', 1)
            if 'id="ss-ticketing-operations-mobile-script"' not in body and '</body>' in body:
                body = body.replace('</body>', OPERATIONS_SCRIPT + '</body>', 1)
            response.set_data(body)
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers.pop('ETag', None)
        except Exception:
            app.logger.exception('Could not apply ticketing operations mobile polish')

        return response
