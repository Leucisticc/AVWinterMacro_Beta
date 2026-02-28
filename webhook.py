import datetime
import io
import json
from typing import Any

import requests


webhook_url = "YOUR_URL_HERE"


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _format_number(value: Any) -> str:
    return f"{_to_int(value, 0):,}"


def _prepare_image_file(img):
    """
    Accept BytesIO/bytes/file-like objects and return a Discord multipart tuple.
    """
    if img is None:
        return None

    try:
        if hasattr(img, "seek"):
            img.seek(0)
    except Exception:
        pass

    if isinstance(img, (bytes, bytearray)):
        return ("screenshot.png", io.BytesIO(img), "image/png")

    return ("screenshot.png", img, "image/png")


def _build_embed_fields(
    run_time: str,
    task_name: str,
    num_runs: int | None = None,
    win: int | None = None,
    lose: int | None = None,
    rewards: int | None = None,
):
    fields = [
        {"name": "🕒 Run Time", "value": str(run_time), "inline": True},
    ]

    have_wl = win is not None or lose is not None
    if have_wl:
        win_i = _to_int(win, 0)
        lose_i = _to_int(lose, 0)
        total = win_i + lose_i
        success_rate = (win_i / total * 100) if total > 0 else 0.0

        fields.extend(
            [
                {"name": "⚔️ Wins", "value": str(win_i), "inline": True},
                {"name": "📈 Success Rate", "value": f"{success_rate:.2f}%", "inline": True},
                {"name": "🔁 Total Runs", "value": str(total), "inline": True},
                {
                    "name": "💰 Rewards",
                    "value": _format_number(rewards) if rewards is not None else f"about ~{210000 * total} collected",
                    "inline": True,
                },
            ]
        )
    else:
        total = _to_int(num_runs, 0)
        fields.append({"name": "🔁 Total Runs", "value": str(total), "inline": True})

    fields.append({"name": "⚙️ Current Task", "value": str(task_name)})
    return fields


def send_webhook(
    run_time: str,
    num_runs: int | None = None,
    task_name: str = "Winter Event",
    img=None,
    win: int | None = None,
    lose: int | None = None,
    rewards: int | None = None,
):
    """
    Backward compatible with the current project call:
      send_webhook(run_time=..., num_runs=..., task_name=..., img=...)

    Also supports the attached WebhookManager-style call:
      send_webhook(run_time=..., win=..., lose=..., task_name=..., img=...)
    """
    if not webhook_url or "put your url" in webhook_url.lower():
        print("[webhook] webhook_url is not configured")
        return False

    payload = {
        "username": "Kouhaii's Automation",
        "avatar_url": "https://i.pinimg.com/1200x/45/3f/20/453f206d5c6ee3d044f26446552a384c.jpg",
        "embeds": [
            {
                "title": "Kouhaii's Automation",
                "description": "",
                "color": 3447003,
                "fields": _build_embed_fields(
                    run_time=run_time,
                    task_name=task_name,
                    num_runs=num_runs,
                    win=win,
                    lose=lose,
                    rewards=rewards,
                ),
                "image": {"url": "attachment://screenshot.png"} if img is not None else None,
                "thumbnail": {
                    "url": "https://i.pinimg.com/originals/2b/55/a7/2b55a73aca43b29f7d13a1248fa658f1.gif",
                },
                "footer": {
                    "text": f"Kouhaii's Automation | Run time: {run_time}",
                    "icon_url": "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExcDRlMno0eXBhM2Uyb2hoYzJlYnJ6dW05NWQwdTE0dHd6MW9saXJ3eCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/6UL3rqweR5Y2Jcrnqb/giphy.gif",
                },
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        ],
    }

    # Discord rejects null embed keys sometimes; remove image if no screenshot.
    embed = payload["embeds"][0]
    if embed.get("image") is None:
        embed.pop("image", None)

    try:
        files = None
        image_file = _prepare_image_file(img)
        if image_file is not None:
            files = {"file": image_file}

        response = requests.post(
            webhook_url,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=15,
        )

        if 200 <= response.status_code < 300:
            return True

        print(f"[webhook] request failed: {response.status_code} {response.text}")
        return False

    except Exception as e:
        print(f"[webhook] error: {e}")
        return False
