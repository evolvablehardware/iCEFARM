from icefarm.client.lib import EventServer
from icefarm.utils import EventSender, DeviceFailure, DeviceInitialized
from unittest.mock import patch, Mock, call
from flask import Flask
from flask_socketio import SocketIO
from icefarm.utils.web import flask_socketio_adapter_connect, flask_socketio_adapter_on
import threading
import time

@patch("socketio.Client")
def test_create_socket(mock_get):
    """Tests that EventServer.connectControl and EventServer.connectWorker connects sockets"""
    server = EventServer("id", [], Mock())

    server.connectControl("http://localhost:8080")
    mock_get.return_value.connect.assert_called_with("http://localhost:8080", auth={"client_id": server.client_id}, wait_timeout=10)

    server.connectWorker("http://localhost:8081")
    mock_get.return_value.connect.assert_called_with("http://localhost:8081", auth={"client_id": server.client_id}, wait_timeout=10)

def setup(serial_to_client: dict[str, str], port=8080) -> tuple[EventSender, SocketIO, Flask]:
    """Creates an EventSender for testing purposes on a specific port.
    As no database exists, EventSender.__getReservationClientId is patched
    to instead use the provided serial_to_client lookup table.
    NOTE: Need to patch Database.__init__ to prevent connection"""
    app = Flask(__name__)
    socketio = SocketIO(app)

    sender = EventSender(socketio, Mock(), Mock())
    sender.__getReservationClientId = lambda self, serial: serial_to_client[serial]

    sock_id_to_client_id = {}

    @socketio.on("connect")
    @flask_socketio_adapter_connect
    def connection(sid, environ, auth):
        client_id = auth.get("client_id")
        sock_id_to_client_id[sid] = client_id
        sender.addSocket(sid, client_id)

    @socketio.on("disconnect")
    @flask_socketio_adapter_on
    def disconnect(sid, reason):
        client_id = sock_id_to_client_id.pop(sid, None)
        sender.removeSocket(client_id)

    def start():
        socketio.run(app, port=port, allow_unsafe_werkzeug=True)

    threading.Thread(target=start, daemon=True, name="socketio-testing-server").start()
    time.sleep(2)

    return sender, socketio, app

@patch("icefarm.utils.Database.Database.__init__")
@patch("icefarm.client.lib.EventServer.EventServer.handleEvent")
def test_event(handle_event, _):
    """Tests whether EventServer translates socket messages to Events"""
    # TODO need to make a better system than this
    # different across tests as server needs time for shutdown
    PORT = 8082

    server = EventServer("client_id", [], Mock())
    sender, socketio, app = setup({}, port=PORT)

    server.connectControl(f"http://localhost:{PORT}")
    assert server.control_socket

    sender.sendClientJson("test_serial", "client_id", DeviceFailure("test_serial"))
    time.sleep(1)
    handle_event.assert_called_with(DeviceFailure("test_serial"))
    handle_event.reset_mock()

    sender.sendClientJson("test_serial", "client_id", [DeviceFailure("test_serial")])
    time.sleep(1)
    handle_event.assert_called_with(DeviceFailure("test_serial"))

@patch("icefarm.utils.Database.Database.__init__")
@patch("icefarm.client.lib.EventServer.EventServer.handleEvent")
def test_events(handle_event, _):
    PORT = 8083

    server = EventServer("client_id", [], Mock())
    sender, socketio, app = setup({}, port=PORT)

    server.connectControl(f"http://localhost:{PORT}")
    assert server.control_socket

    events = [
        DeviceFailure("test_serial"),
        DeviceInitialized("test_serial"),
        DeviceFailure("test_serial"),
        DeviceInitialized("test_serial"),
    ]

    sender.sendClientJson("test_serial", "client_id", events)
    time.sleep(1)

    handle_event.assert_has_calls([call(event) for event in events])

# TODO should add more tests here





