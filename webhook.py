import datetime
import io
import json
import time
from typing import Any

import requests
webhook_url = ''
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_TIMEOUT_SECONDS = 15
DOUBLE_PRESENTS = True
if DOUBLE_PRESENTS:
    PRESENTS = 420000
else:
    PRESENTS = 210000

def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _format_number(value: Any) -> str:
    return f"{_to_int(value, 0):,}"


def _runtime_to_hours(run_time: Any) -> float:
    text = str(run_time).strip()
    if not text:
        return 0.0

    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = (int(part) for part in parts)
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = (int(part) for part in parts)
        else:
            return 0.0
    except Exception:
        return 0.0

    total_seconds = (hours * 3600) + (minutes * 60) + seconds
    return total_seconds / 3600 if total_seconds > 0 else 0.0


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
    num_runs_label: str = "Total Runs",
    win: int | None = None,
    lose: int | None = None,
    rewards: int | None = None,
    reward_name: str = "Rewards",
    average_rewards: int | None = None,
    extra_fields: list[dict[str, Any]] | None = None,
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
        total_rewards = _to_int(rewards, PRESENTS * win_i)
        runtime_hours = _runtime_to_hours(run_time)
        hourly_rate = int(total_rewards / runtime_hours) if runtime_hours > 0 else 0

        fields.extend(
            [
                {"name": "⚔️ Wins", "value": str(win_i), "inline": True},
                {"name": "📈 Success Rate", "value": f"{success_rate:.2f}%", "inline": True},
                {"name": "🔁 Total Runs", "value": str(total), "inline": True},
                {
                    "name": f"💰 {reward_name}",
                    "value": f"~ {_format_number(total_rewards)} collected",
                    "inline": True,
                },
                {
                    "name": f"⏱️ {reward_name} / Hour",
                    "value": f"~ {_format_number(hourly_rate)}/hr" if hourly_rate > 0 else "Calculating...",
                    "inline": True,
                },
            ]
        )
        if average_rewards is not None:
            fields.append(
                {
                    "name": f"📊 Average {reward_name}",
                    "value": f"~ {_format_number(average_rewards)} per win",
                    "inline": True,
                }
            )
    else:
        total = _to_int(num_runs, 0)
        fields.append({"name": f"🔁 {num_runs_label}", "value": str(total), "inline": True})

    if extra_fields:
        fields.extend(extra_fields)

    fields.append({"name": "⚙️ Current Task", "value": str(task_name)})
    return fields


def send_webhook(
    run_time: str,
    num_runs: int | None = None,
    task_name: str = "Winter Event",
    img=None,
    num_runs_label: str = "Total Runs",
    win: int | None = None,
    lose: int | None = None,
    rewards: int | None = None,
    reward_name: str = "Rewards",
    average_rewards: int | None = None,
    enabled: bool = True,
    alert_text: str | None = None,
    extra_fields: list[dict[str, Any]] | None = None,
):
    """
    Backward compatible with the current project call:
      send_webhook(run_time=..., num_runs=..., task_name=..., img=...)

    Also supports the attached WebhookManager-style call:
      send_webhook(run_time=..., win=..., lose=..., task_name=..., img=...)
    """
    if not enabled:
        print("[webhook] disabled by settings")
        return False

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
                    num_runs_label=num_runs_label,
                    win=win,
                    lose=lose,
                    rewards=rewards,
                    reward_name=reward_name,
                    average_rewards=average_rewards,
                    extra_fields=extra_fields,
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
    if alert_text:
        payload["content"] = str(alert_text)

    # Discord rejects null embed keys sometimes; remove image if no screenshot.
    embed = payload["embeds"][0]
    if embed.get("image") is None:
        embed.pop("image", None)

    def _post_once(use_image: bool) -> requests.Response:
        files = None
        body = {"payload_json": json.dumps(payload)}
        if use_image:
            image_file = _prepare_image_file(img)
            if image_file is not None:
                files = {"file": image_file}
        return requests.post(
            webhook_url,
            data=body,
            files=files,
            timeout=WEBHOOK_TIMEOUT_SECONDS,
        )

    def _post_with_retries(use_image: bool) -> bool:
        for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
            try:
                response = _post_once(use_image=use_image)
                if 200 <= response.status_code < 300:
                    return True

                # Retry transient Discord/network statuses.
                if response.status_code in (408, 429, 500, 502, 503, 504):
                    retry_after = response.headers.get("Retry-After")
                    try:
                        sleep_for = float(retry_after) if retry_after else (0.75 * attempt)
                    except Exception:
                        sleep_for = 0.75 * attempt
                    print(f"[webhook] transient failure {response.status_code}, retry {attempt}/{WEBHOOK_MAX_RETRIES} in {sleep_for:.2f}s")
                    time.sleep(sleep_for)
                    continue

                print(f"[webhook] request failed: {response.status_code} {response.text}")
                return False

            except requests.exceptions.SSLError as e:
                if attempt >= WEBHOOK_MAX_RETRIES:
                    print(f"[webhook] SSL error after retries: {e}")
                    return False
                sleep_for = 0.75 * attempt
                print(f"[webhook] SSL error, retry {attempt}/{WEBHOOK_MAX_RETRIES} in {sleep_for:.2f}s")
                time.sleep(sleep_for)
            except requests.exceptions.RequestException as e:
                if attempt >= WEBHOOK_MAX_RETRIES:
                    print(f"[webhook] request error after retries: {e}")
                    return False
                sleep_for = 0.75 * attempt
                print(f"[webhook] request error, retry {attempt}/{WEBHOOK_MAX_RETRIES} in {sleep_for:.2f}s")
                time.sleep(sleep_for)
            except Exception as e:
                print(f"[webhook] error: {e}")
                return False

        return False

    # First try full payload (with screenshot if available).
    ok = _post_with_retries(use_image=True)
    if ok:
        return True

    # Fallback: some clients fail on multipart/TLS path, send without image.
    if img is not None:
        embed.pop("image", None)
        print("[webhook] retrying without image attachment")
        return _post_with_retries(use_image=False)

    return False
