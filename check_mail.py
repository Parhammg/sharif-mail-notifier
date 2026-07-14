import email
import imaplib
import json
import os
import urllib.parse
import urllib.request

IMAP_HOST = os.environ["IMAP_HOST"]
IMAP_PORT = int(os.environ["IMAP_PORT"])
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


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
