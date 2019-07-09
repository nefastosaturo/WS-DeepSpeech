from DSEngine import DSEngine
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.endpoints import WebSocketEndpoint

from logging import getLogger

from time import time
from os import kill,getpid,path
from signal import SIGTERM

logger = getLogger('DSApp')

class DSApp(Starlette):

    def __init__(self,config):
        self.config = config
        self.CLIENTS = {}
        super().__init__(self)

    def startup(self):
        print(getpid(),':ready to go')
    def homepage(self,request):
        return PlainTextResponse('Hello, world!')

    class WSEndpoint(WebSocketEndpoint):

        encoding = "json"
        async def on_connect(self,websocket):

            await websocket.accept()
            t = time()
            welcomeMessage = {
                "type": "WELCOME_MSG",
                "data": {
                    "message": "WELCOME "+str(websocket.client[1]),
                    "timestamp":int(round(t*1000)),
                    "timestampExtended":t*1000
                }
            }

            await websocket.send_json(welcomeMessage)

        async def send_app_status(self,websocket):
            t = time()
            msg = {
                "type": "STATUS",
                "data": {
                    "result": False,
                    "message": "DeepSpeech is not ready. Please retry later!",
                    "timestamp":int(round(t*1000)),
                    "timestampExtended":t*1000
                }

            }
            if not path.isfile("lockfile"):
                msg["data"]["result"] = True
                msg["data"]["message"] = "DeepSpeech data ready"

            await websocket.send_json(msg)

        async def setup_model(self,websocket):
            t = time()
            app=self.scope.get("app")

            id=websocket.client[1]
            app.CLIENTS[id] = {
                "socket": websocket,
                "model": await DSEngine.create(websocket=websocket,**app.config.file_values)
            }

            setupMessage = {
                "type": "SETUP",
                "data": {
                    "result": True,
                    "message": "DeepSpeech model loaded",
                    "timestamp":int(round(t*1000)),
                    "timestampExtended":t*1000
                }
            }
            await websocket.send_json(setupMessage)


        async def on_receive(self, websocket, data):

            app=self.scope.get("app")

            if 'type' not in data:
                logger.error("%s: unsupported event: %s",getpid(), data)
            else:
                msgType = data.get("type")
                if msgType == "STATUS":
                    await self.send_app_status(websocket)
                elif msgType == "SETUP":
                    await self.setup_model(websocket)
                else:
                    id = websocket.client[1]
                    ds = app.CLIENTS[id].get("model")
                    await ds.enqueue(data)

        async def on_disconnect(self,websocket,close_code):
            logger.info("DISCONNECT EVENT")
            id = websocket.client[1]
            app=self.scope.get("app")
            client = app.CLIENTS.get(id)
            if client:

                await client.get("model").clear()
                del app.CLIENTS[id]
                logger.info("len %s",len(app.CLIENTS))

            if websocket.application_state.name is not "DISCONNECTED":
                await websocket.close()
                logger.info("WS client state: %s ; application state: %s",websocket.client_state,websocket.application_state)

                nrRegClients = len(app.CLIENTS)
                logger.warning("DISCONNECT EVENT WITH CODE %s. CLIENTS REGISTERED: %s",close_code,nrRegClients)

                # TODO: How to free memory correctly?? I would like to not force restart!
                if nrRegClients==0:
                    logger.warning("%s:FORCE RESTART",getpid())
                    kill(getpid(), SIGTERM)
