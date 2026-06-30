"""Event bus per FerroTrack.

Punto di estensione astratto per integrazioni future con sistemi gestionali esterni
(es. PassPartout, Zucchetti, Fatture in Cloud, Aruba — il cliente non lo sa ancora).

Oggi è un no-op: registra eventi nel log ma non li trasmette altrove.
Quando si saprà il gestionale di destinazione, basterà aggiungere un subscriber
che converte gli eventi in chiamate API esterne, senza toccare il codice che
li pubblica (Order creation, status change, fattura emessa, ecc.).

Eventi previsti (publish() li accetta tutti, oggi nessuno è consumato):
- 'order.created'        payload={order_dict}
- 'order.status_changed' payload={order_id, old_status, new_status}
- 'order.invoiced'       payload={order_id, importo, numero_fattura}
- 'preventivo.accepted'  payload={preventivo_id, order_id}
"""
import logging
from typing import Any

logger = logging.getLogger('events')


class OrderEventBus:
    """No-op event bus. Vedi modulo docstring per design rationale."""

    _subscribers: dict[str, list] = {}

    @classmethod
    def publish(cls, event_name: str, payload: Any) -> None:
        """Pubblica un evento. Oggi logga e basta — in futuro inoltrerà a subscribers."""
        logger.info('event=%s payload=%r', event_name, payload)
        for handler in cls._subscribers.get(event_name, []):
            try:
                handler(payload)
            except Exception as e:
                logger.exception('subscriber failed for event=%s: %s', event_name, e)

    @classmethod
    def subscribe(cls, event_name: str, handler) -> None:
        """Registra un handler per un evento. Pattern publish/subscribe in-process."""
        cls._subscribers.setdefault(event_name, []).append(handler)
