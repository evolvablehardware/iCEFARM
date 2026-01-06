import asyncio
import inspect
import json
from functools import wraps

from flask import Response, jsonify, request
from socketio import AsyncServer

from usbipice.utils.utils import json_to_args, typecheck

def inject_and_return_json(func):
    """Injects request json values into arguments. Uses argument names as the json key. Typechecks arguments,
    only classes are supported. Returns a status=400 if a key is missing or the typecheck fails.
    Returns status=200 on True and status=500 on false. Otherwise, returns flask.jsonify of the result."""
    parameter_strings = [] # func args as string
    parameters = inspect.signature(func).parameters.values()

    for param in parameters:
        parameter_strings.append(param.name)

    @wraps(func)
    def handler_wrapper(*args):
        if request.content_type == "application/json":
            try:
                js = request.get_json()
            except Exception:
                return Response(status=400)
        else:
            try:
                js = json.loads(request.args.get("json"))
            except Exception:
                return Response(status=400)

        args = json_to_args(js, parameter_strings)

        if not typecheck(func, args):
            return Response(status=400)

        res = func(*args)
        if res is True or res is None:
            return Response(status=200)
        if res is False:
            return Response(status=500)

        return jsonify(res)

    return handler_wrapper

def flask_socketio_adapter_connect(func):
    """Adapter to allow flask_socketio.SocketIO eventhandlers to use the same interface as
    socketio.AsyncServer for @socketio.on("connect"). This is
    achieved by injecting an empty environment argument."""
    @wraps(func)
    def event_handler(*args):
        if len(args) == 1:
            return func(request.sid, {}, args[0])

        return func(*args)

    return event_handler

def flask_socketio_adapter_on(func):
    """Adapter to allow flask_socketio.SocketIO eventhandlers to use the same interface as
    socketio.AsyncServer for @socketio.on events. If only one argument is passed, request.sid is
    injected as the first argument. For the connection event, you must use
    flask_socketio_adapter_connection instead."""
    @wraps(func)
    def event_handler(*args):
        if len(args) == 2:
            return func(*args)
        elif len(args) == 1:
            return func(request.sid, *args)

    return event_handler

class SyncAsyncServer(AsyncServer):
    """Adapter to allow flask_socketio.SocketIO to have the same interface as socketio.AsyncServer while
    running as an ASGI app"""
    def emit(self, event, data=None, to=None, room=None, skip_sid=None, namespace=None, callback=None, ignore_queue=False):
        return asyncio.run(super().emit(event, data, to, room, skip_sid, namespace, callback, ignore_queue))

    def sleep(self, seconds=0):
        return asyncio.run(super().sleep(seconds))
