"""Starts a graceful shutdown. Waits until the shutdown is complete to exit. Takes worker port as arg."""
import time
import sys
import threading
import socketio

port = sys.argv[1]

cv = threading.Condition()
shutdown = False

sio = socketio.Client()
@sio.event
def shutdown_complete(_):
    global shutdown
    with cv:
        shutdown = True
        cv.notify_all()

sio.connect(f"http://localhost:{port}", auth={"client_id":f"local_graceful_shutdown_{time.time()}"}, wait_timeout=10)
sio.emit("graceful_shutdown", "")

with cv:
    if not shutdown:
        cv.wait_for(lambda : shutdown)

sio.disconnect()