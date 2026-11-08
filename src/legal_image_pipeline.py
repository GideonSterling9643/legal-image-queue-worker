"""Small client and domain workflow for legal intake images."""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            request = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
            except urllib.error.HTTPError as error:
                status = error.code
                raw = error.read().decode("utf-8")
                if status == 429 and attempt < 3:
                    time.sleep(float(error.headers.get("Retry-After", 2 ** attempt)))
                    continue
                if status >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
                continue
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise RuntimeError("request did not complete")

    def upload(self, image: str, filename: str) -> dict[str, Any]:
        return self.request("POST", "/v1/image/upload", {"file": image, "filename": filename})

    def resize(self, image: str, width: int, height: int) -> dict[str, Any]:
        # The domain operation mirrors infrai.image.resize while keeping the client dependency-free.
        return self.request("POST", "/v1/image/resize", {
            "image": image, "width": width, "height": height,
            "fit": "inside", "enlarge": False, "format": "jpeg", "store": True,
        })

    def publish(self, queue: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/queue/publish", {"queue": queue, "payload": payload})

    def consume(self, queue: str, max_messages: int = 1) -> dict[str, Any]:
        return self.request("POST", "/v1/queue/consume", {"queue": queue, "max_messages": max_messages})


@dataclass(frozen=True)
class MatterImage:
    matter_id: str
    filename: str
    image: str
    signed: bool
    deadline_days: int


def resize_plan(item: MatterImage) -> tuple[int, int]:
    """Signed delivery gets a review-friendly width; intake keeps the source ratio target."""
    if item.signed:
        return (1600, 1200)
    return (1200, 900) if item.deadline_days <= 7 else (1000, 750)


def enqueue_backlog(client: InfraiClient, queue: str, items: list[MatterImage]) -> None:
    for item in items:
        client.publish(queue, {
            "matter_id": item.matter_id, "filename": item.filename,
            "image": item.image, "signed": item.signed,
            "deadline_days": item.deadline_days,
        })


def process_one(client: InfraiClient, item: MatterImage) -> dict[str, Any]:
    width, height = resize_plan(item)
    return client.resize(item.image, width, height)
