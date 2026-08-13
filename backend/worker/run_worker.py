import threading
import time

from redis import Redis
from rq import Queue, Worker

from app.config import settings
from worker.jobs import sweep_expired_labs

QUEUE_NAME = "labs"
SWEEP_INTERVAL_SECONDS = 60


def run_sweep_loop() -> None:
    while True:
        try:
            sweep_expired_labs()
        except Exception as exc:  # noqa: BLE001 — defensive: never let the sweep loop die silently
            print(f"sweep_expired_labs failed: {exc}")
        time.sleep(SWEEP_INTERVAL_SECONDS)


def main() -> None:
    threading.Thread(target=run_sweep_loop, daemon=True).start()

    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(QUEUE_NAME, connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()
