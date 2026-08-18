"""Invio email via SMTP configurabile — nessuna credenziale nel codice.

Tutta la configurazione arriva da variabili d'ambiente (file app/.env, caricato
da run.py con load_dotenv). Serve a spedire il PDF del preventivo al cliente.

Variabili (.env):
    SMTP_HOST       host del server SMTP (es. smtps.aruba.it, smtp.gmail.com)
    SMTP_PORT       porta (465 per SSL, 587 per STARTTLS). Default 465.
    SMTP_USER       utente/casella (di solito l'indirizzo email completo)
    SMTP_PASSWORD   password della casella (per Gmail: "password per app")
    SMTP_SECURITY   'ssl' (465) | 'starttls' (587) | 'none'. Default 'ssl'.
    SMTP_FROM       mittente visualizzato (default = SMTP_USER)
    SMTP_FROM_NAME  nome mittente (es. "Carpenteria L.S. S.r.l.")

Progettato per fallire in modo pulito: se manca la config, `is_configured()`
è False e `send_email()` ritorna (False, messaggio) senza sollevare eccezioni.
"""
import os
import ssl
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _cfg() -> dict:
    try:
        port = int(os.environ.get('SMTP_PORT', '465') or '465')
    except (ValueError, TypeError):
        port = 465
    return {
        'host': (os.environ.get('SMTP_HOST', '') or '').strip(),
        'port': port,
        'user': (os.environ.get('SMTP_USER', '') or '').strip(),
        'password': os.environ.get('SMTP_PASSWORD', '') or '',
        'security': ((os.environ.get('SMTP_SECURITY', '') or 'ssl').strip().lower()),
        'from_addr': ((os.environ.get('SMTP_FROM', '') or os.environ.get('SMTP_USER', '') or '').strip()),
        'from_name': (os.environ.get('SMTP_FROM_NAME', '') or '').strip(),
    }


def is_configured() -> bool:
    """True se ci sono host + utente + password (il minimo per tentare l'invio)."""
    c = _cfg()
    return bool(c['host'] and c['user'] and c['password'])


def config_summary() -> dict:
    """Riepilogo NON sensibile della config (per diagnostica UI). Niente password."""
    c = _cfg()
    return {
        'configured': is_configured(),
        'host': c['host'],
        'port': c['port'],
        'security': c['security'],
        'from': c['from_addr'],
        'from_name': c['from_name'],
    }


def send_email(to_addr: str, subject: str, body_text: str,
               attachments=None) -> tuple[bool, str | None]:
    """Invia una email. Ritorna (ok, errore).

    attachments: lista di tuple (filename, bytes, maintype, subtype), es.
                 ('preventivo.pdf', b'...', 'application', 'pdf').
    """
    c = _cfg()
    if not (c['host'] and c['user'] and c['password']):
        return False, 'SMTP non configurato: mancano SMTP_HOST/SMTP_USER/SMTP_PASSWORD nel file app/.env'
    to_addr = (to_addr or '').strip()
    if not to_addr:
        return False, 'Destinatario mancante'

    from_addr = c['from_addr'] or c['user']
    msg = EmailMessage()
    msg['From'] = f"{c['from_name']} <{from_addr}>" if c['from_name'] else from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject or '(senza oggetto)'
    msg.set_content(body_text or '')
    for att in (attachments or []):
        try:
            fname, data, main, sub = att
            msg.add_attachment(data, maintype=main, subtype=sub, filename=fname)
        except Exception as e:
            logger.warning('allegato ignorato (%s): %s', att[0] if att else '?', e)

    try:
        if c['security'] == 'ssl':
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(c['host'], c['port'], context=ctx, timeout=30) as s:
                s.login(c['user'], c['password'])
                s.send_message(msg)
        else:
            with smtplib.SMTP(c['host'], c['port'], timeout=30) as s:
                s.ehlo()
                if c['security'] == 'starttls':
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                s.login(c['user'], c['password'])
                s.send_message(msg)
        logger.info('Email inviata a %s (oggetto: %s)', to_addr, subject)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, 'Autenticazione SMTP fallita: utente o password errati (per Gmail serve una "password per app").'
    except (smtplib.SMTPException, OSError) as e:
        logger.exception('send_email failed')
        return False, f'Invio fallito: {e}'
