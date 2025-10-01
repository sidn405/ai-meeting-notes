from pathlib import Path
from ..config import get_settings

settings = get_settings()
SLACK_LOG = (Path(__file__).resolve().parents[2] / "data" / "outbox" / "slack.log")
SLACK_LOG.parent.mkdir(parents=True, exist_ok=True)

def send_slack(text: str):
    if not settings.slack_webhook:
        with open(SLACK_LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n\n---\n\n")
        return
    try:
        import httpx
        with httpx.Client(timeout=10) as c:
            c.post(settings.slack_webhook, json={"text": text})
    except Exception:
        with open(SLACK_LOG, "a", encoding="utf-8") as f:
            f.write("[ERR webhook] " + text + "\n\n---\n\n")
