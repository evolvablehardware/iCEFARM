import psycopg

from utils.Database import Database

class ControlDatabase(Database):
    def __init__(self, dburl: str):
        super().__init__(dburl)
    
    def reserve(self, amount, subscriptionurl, clientname):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM makeReservations(%s::int, %s::varchar(255), %s::varchar(255))", (amount, subscriptionurl, clientname))

                    data = cur.fetchall()
        except Exception:
            return False
        
        values = []
        for row in data:
            values.append({
                "serial": row[0],
                "ip": str(row[1]),
                "usbipport": row[2],
                "bus": row[3]
            })

        return values
    
    def extend(self, name, serials):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM extendReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

                    data = cur.fetchall()
        except Exception:
            return False
        
        return data
    
    def extendAll(self, name):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM extendAllReservations(%s::varchar(255))", (name,))

                    data = cur.fetchall()
        except Exception:
            return False
        
        return data
    
    def end(self, name, serials):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM endReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

                    data = cur.fetchall()
        except Exception:
            return False
        
        return data
    
    def endAll(self, name):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM endAllReservations(%s::varchar(255))", (name,))

                    data = cur.fetchall()
        except Exception:
            return False
        
        return data



