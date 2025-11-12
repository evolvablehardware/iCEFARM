from flask import Flask, request, Response, jsonify
import os
import psycopg
from waitress import serve
import logging
import sys
import requests

from control.ControlDatabase import ControlDatabase

def expect_json(parms, fun):
    if request.content_type != "application/json":
        return Response(status=400)
    try:
        json = request.get_json()
    except Exception:
        return Response(status=400)
    
    args = []

    for p in parms:
        value = json.get(p)
        if not value:
            return Response(status=400)
        args.append(value)
    
    if len(args) != len(parms):
        return Response(status=400)
    
    return fun(*args)

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")
    
    SERVER_PORT = int(os.environ.get("USBIPICE_CONTROL_PORT", "8080"))
    logger.info(f"Running on port {SERVER_PORT}")
    
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                pass
    except Exception:
        raise Exception("Failed to connect to database")
    
    database = ControlDatabase(DATABASE_URL)
    app = Flask(__name__)

    @app.get("/reserve")
    def make_reservations():
        return jsonify(expect_json(["amount", "url", "name"], database.reserve))

    @app.get("/extend")
    def extend():
        return jsonify(expect_json(["name", "serials"], database.extend))

    @app.get("/extendall")
    def extendall():
        return jsonify(expect_json(["name"], database.extendAll))

    @app.get("/end")
    def end():
        data = expect_json(["name", "serials"], database.end)

        for row in data:
            try:
                requests.get(data["subscriptionurl"], json={
                    "event": "reservation end",
                    "serial": row["serial"]
                })
            except:
                logger.warning(f"failed to notify {row["subscriptionurl"]} device {row["serial"]} of reservation end")
            
            try:
                requests.get(f"http://{row["workerip"]}:{row["workerport"]}/unreserve", json={
                    "serial": row["serial"]
                })
            except:
                logger.warning(f"failed to notify worker {row["workerip"]} of reservation on {row["serial"]} ending")
        
        return jsonify(list(map(lambda x : x["serial"], row)))

    @app.get("/endall")
    def endall():
        data = expect_json(["name"], database.endAll)

        for row in data:
            try:
                res = requests.get(data["subscriptionurl"], json={
                    "event": "reservation end",
                    "serial": row["serial"]
                })

                if res.status_code != 200:
                    raise Exception
            except:
                logger.warning(f"failed to notify {row["subscriptionurl"]} device {row["serial"]} of reservation end")
            
            try:
                res = requests.get(f"http://{row["workerip"]}:{row["workerport"]}/unreserve", json={
                    "serial": row["serial"]
                })

                if res.status_code != 200:
                    raise Exception
            except:
                logger.warning(f"failed to notify worker {row["workerip"]} of reservation on {row["serial"]} ending")
        
        return jsonify(list(map(lambda x : x["serial"], data)))
    
    serve(app, port=SERVER_PORT)

if __name__ == "__main__":
    main()