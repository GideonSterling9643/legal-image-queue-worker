import json
import os
import sys

from legal_image_pipeline import InfraiClient, MatterImage, enqueue_backlog, process_one


def main() -> None:
    client = InfraiClient()
    queue = os.environ.get("INFRAI_QUEUE", "legal-image-backlog")
    items = [MatterImage("matter-104", "signed-order.jpg", "upload-1", True, 3)]
    if len(sys.argv) > 1 and sys.argv[1] == "enqueue":
        enqueue_backlog(client, queue, items)
        print(json.dumps({"queued": len(items), "queue": queue}))
        return
    envelope = client.consume(queue)
    messages = envelope.get("data", {}).get("messages", [])
    for message in messages:
        payload = message.get("payload", {})
        item = MatterImage(payload["matter_id"], payload["filename"], payload["image"], payload["signed"], payload["deadline_days"])
        result = process_one(client, item)
        print(json.dumps({"matter_id": item.matter_id, "delivery": "signed-document", "result": result}))


if __name__ == "__main__":
    main()
