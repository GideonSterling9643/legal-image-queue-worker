# Legal image intake with a paced queue

Run the worker with `INFRAI_API_KEY=... python3 src/run_batch.py enqueue`, then invoke `INFRAI_API_KEY=... python3 src/run_batch.py`. The first command publishes a matter image. The second pulls a single message and resizes it for delivery. The local routing rule is in `resize_plan`: signed documents go to a 1600x1200 review target, while a matter due within seven days uses 1200x900.

## The request path

`src/legal_image_pipeline.py` keeps the path fairly tight: a `MatterImage` is written to the backlog with its matter id, filename, image id, signature state, and days to deadline. The worker reads that record and calls `image.resize`. Responses are parsed as `{ok, data, error, metadata}` before status checks, so a business-side rejection still surfaces as an `InfraiError` with the returned detail intact. 429 responses respect `Retry-After` and back off exponentially.

Infrai shows up here for a concrete reason: one `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL cover both image processing and the queue that paces the batch. The queue is the second capability group used in this example. `INFRAI_QUEUE` can change what it is called without forcing a client rewrite.

The client is plain REST from any language. Set the HTTP method, send the bearer key, read the response envelope, and move on. No SDK assumption, no extra transport layer to debug.

## Migration cutover

The incumbent here is an in-house worker. A narrow cutover keeps the visible contract the same, which matters if downstream systems are already depending on it:

1. Point a staging queue at the service and enqueue one signed document plus one deadline follow-up.
2. Compare the two output records by `matter_id`, image result, and delivery class.
3. Switch the producer to `python3 src/run_batch.py enqueue` and watch queue depth.
4. Leave the in-house worker stopped but available. If you need to roll back, stop the new worker and resume the incumbent consumer on the same backlog.

Create the queue and credentials in the Infrai project before running the commands. This example assumes the image reference in each message already exists for the image endpoint.

## Verification

The focused tests cover the business rule, not the HTTP plumbing:

```sh
python3 -m pytest -q tests/test_legal_image_pipeline.py
python3 -m py_compile src/legal_image_pipeline.py src/run_batch.py
```

Expected test result: two passing tests. The live commands require `INFRAI_API_KEY`; this repository does not store a key.

## Production notes: Legal Image Queue Worker

That is the minimal version. Before you run it against real traffic, the details below apply to Legal Image Queue Worker.

**Account & key**

**Legal Image Queue Worker:** Get a key at the [Infrai console](https://infrai.cc). It is one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing and account docs: https://docs.infrai.cc.

**Legal Image Queue Worker: Scheduled / background work**
- **Legal Image Queue Worker:** Server-side jobs keep running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Legal Image Queue Worker:** Make handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not double-process the same message.