import os
from celery import Celery

BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery('worker', broker=BROKER_URL)

@app.task
def hello():
    print("Hello from worker - TODO: implement queue consumer and agent runner")
