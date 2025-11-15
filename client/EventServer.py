import threading    
from waitress.server import create_server
from flask import Flask, request, Response

class EventServer:
    def __init__(self, client, eventhandlers, logger):
        super().__init__()
        self.client = client 
        self.logger = logger

        self.server = None
        self.thread = None

        self.eventhandlers = eventhandlers
        if type(self.eventhandlers) != list:
            self.eventhandlers = [self.eventhandlers]

        self.ip = None
        self.port = None
    
    def getUrl(self):
        return f"http://{self.ip}:{self.port}"
    
    def __callEventhandlers(self, method, args):
        for eh in self.eventhandlers:
            getattr(eh, method)(*args)

    def start(self, client, ip, port):
        self.ip = ip
        self.port = port
        app = Flask(__name__)

        @app.route("/")
        def handle():
            if request.content_type != "application/json":
                return Response(status=400)
            
            try:
                json = request.get_json()
            except:
                return Response(status=400)
            
            serial = json.get("serial")
            event = json.get("event")

            if not serial or not event:
                return Response(status=400)

            match event:
                case "failure":
                    self.__callEventhandlers("handleFailure", (client, serial))
                case "reservation end":
                    self.__callEventhandlers("handleReservationEnd", (client, serial))
                    pass
                case "export":
                    connection_info = self.client.getConnectionInfo(serial)

                    if not connection_info:
                        return Response(status=400)
                    
                    ip, port = connection_info

                    bus = json.get("bus")

                    if not bus:
                        return Response(status=400)

                    self.__callEventhandlers("handleExport", (client, serial, bus, ip, str(port)))
                case "disconnect":
                    self.__callEventhandlers("handleDisconnect", (client, serial))
                case "reservation halfway":
                    self.__callEventhandlers("handleReservationEndingSoon", (client, serial))
                case _:
                    return Response(status=400)
            
            return Response(status=200)
        
        self.server = create_server(app,  port=self.port)
        self.thread = threading.Thread(target=lambda : self.server.run(), name="eventserver")
        self.thread.start()

    def triggerExport(self, serial, bus, ip, port):
        self.__callEventhandlers("handleExport", (self.client, serial, bus, ip, str(port)))

    def triggerTimeout(self, serial, ip, port):
        self.__callEventhandlers("handleTimeout", (self.client, serial, ip, str(port)))
    
    def stop(self):
        if self.server:
            self.server.close()
        
        if self.thread:
            self.thread.join()