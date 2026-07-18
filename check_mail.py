import email
import imaplib
import json
import os
import sys
import urllib.parse
import urllib.request

IMAP_HOST = os.environ["IMAP_HOST"]
IMAP_PORT = int(os.environ["IMAP_PORT"])
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


def preflight():
    """Fail fast with a clear message if the Telegram secrets are wrong,
    instead of crashing mid-run with a cryptic 404 traceback."""
    if not TELEGRAM_BOT_TOKEN:
        sys.exit(
            "CONFIG ERROR: TELEGRAM_BOT_TOKEN is empty. The GitHub secret is "
            "missing or misspelled. Add a secret named exactly TELEGRAM_BOT_TOKEN "
            "under Settings > Secrets and variables > Actions."
        )
    if not TELEGRAM_CHAT_ID:
        sys.exit("CONFIG ERROR: TELEGRAM_CHAT_ID is empty.")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        with urllib.request.urlopen(url, timeout=10) as r:
            info = json.load(r)
        print(f"Telegram token OK (bot @{info['result'].get('username')}).")
    except urllib.error.HTTPError as e:
        sys.exit(
            f"CONFIG ERROR: Telegram rejected the token (HTTP {e.code}). "
            f"The value in the TELEGRAM_BOT_TOKEN secret is wrong or revoked. "
            f"Token length seen: {len(TELEGRAM_BOT_TOKEN)} chars."
        )


def load_last_uid():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f).get("last_uid")
    return None


def save_last_uid(uid):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_uid": uid}, f)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
    urllib.request.urlopen(url, data=data, timeout=10)


def main():
    preflight()

    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(EMAIL_USER, EMAIL_PASS)
    conn.select("INBOX")

    _, uids = conn.uid("search", None, "ALL")
    all_uids = [int(u) for u in uids[0].split()]
    if not all_uids:
        conn.logout()
        return

    last_uid = load_last_uid()
    if last_uid is None:
        # first run: just record the current top UID, don't notify for old mail
        save_last_uid(max(all_uids))
        conn.logout()
        return

    new_uids = [u for u in all_uids if u > last_uid]
    print(f"last_uid={last_uid}, {len(new_uids)} new email(s) to notify.")
    for uid in new_uids:
        _, msg_data = conn.uid(
            "fetch", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])"
        )
        header = msg_data[0][1].decode(errors="ignore")
        msg = email.message_from_string(header)
        sender = msg.get("From", "unknown")
        subject = msg.get("Subject", "(no subject)")
        send_telegram(f"New email\nFrom: {sender}\nSubject: {subject}")

    if new_uids:
        save_last_uid(max(new_uids))

    conn.logout()


if __name__ == "__main__":
    main()
