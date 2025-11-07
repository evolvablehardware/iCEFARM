from flask import Flask, request, Response, jsonify
import os
import psycopg
from control.ControlDatabase import ControlDatabase

def expect_json(parms, fun):
    if request.content_type != "application/json":
        return Response(400)
    try:
        json = request.get_json()
    except Exception:
        return Response(400)
    
    args = []

    for p in parms:
        value = json.get(p)
        if not value:
            return Response(400)
        args.append(value)
    
    return jsonify(fun(*args))

def main():
    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")
    
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
        return expect_json(["amount", "url", "name"], database.reserve)

    @app.get("/extend")
    def extend():
        return expect_json(["name", "serials"], database.extend)

    @app.get("/extendall")
    def extendall():
        return expect_json(["name"], database.extendAll)

    @app.get("/end")
    def end():
        return expect_json(["name", "serials"], database.end)

    @app.get("/endall")
    def endall():
        return expect_json(["name"], database.endAll)
    
    app.run()

if __name__ == "__main__":
    main()