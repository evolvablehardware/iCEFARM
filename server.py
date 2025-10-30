from blacksheep import get, Application, Response, json, Request
import uvicorn
import os
import psycopg

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0")
else:
    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")
    
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                pass
    except Exception as e:
        raise Exception("Failed to connect to database")
    
    app = Application()

@get("/reserve")
async def make_reservations(req: Request):
    args = await req.json()
    if not args:
        return Response(400)

    amount = args.get("amount")
    url = args.get("url")
    name = args.get("name")

    if not amount or not url or not name:
        return Response(400)
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM makeReservations(%s::int, %s::varchar(255), %s::varchar(255))", (amount, url, name))

                data = cur.fetchall()
    except:
        return Response(500)
    
    values = []
    for row in data:
        values.append({
            "serial": row[0],
            "ip": str(row[1]),
            "usbipport": row[2],
            "bus": row[3]
        })

    return json(values)

@get("/extend")
async def extend(req: Request):
    args = await req.json()
    if not args:
        return Response(400)

    serials = args.get("serials")
    name = args.get("name")

    if not serials or not name:
        return Response(400)
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM extendReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

                data = cur.fetchall()
    except Exception:
        return Response(500)
    
    return json(data)

@get("/extendall")
async def extendall(req: Request):
    args = await req.json()
    if not args:
        return Response(400)

    name = args.get("name")

    if not name:
        return Response(400)
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM extendAllReservations(%s::varchar(255))", (name,))

                data = cur.fetchall()
    except Exception:
        return Response(500)
    
    return json(data)

@get("/end")
async def end(req: Request):
    args = await req.json()
    if not args:
        return Response(400)

    serials = args.get("serials")
    name = args.get("name")

    if not serials or not name:
        return Response(400)
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM endReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

                data = cur.fetchall()
    except Exception:
        return Response(500)
    
    return json(data)

@get("/endall")
async def endall(req: Request):
    args = await req.json()
    if not args:
        return Response(400)

    name = args.get("name")

    if not name:
        return Response(400)
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM endAllReservations(%s::varchar(255))", (name,))

                data = cur.fetchall()
    except Exception:
        return Response(500)
    
    return json(data)