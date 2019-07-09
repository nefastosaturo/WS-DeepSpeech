from os import path

from DSApp import DSApp
from starlette.config import Config

import logging

appConfig = Config("./appConfig")

app = DSApp(appConfig)

if appConfig('DEBUG', cast=bool):
    app.debug=True

app.add_event_handler("startup",app.startup)
app.add_route("/",app.homepage)
app.add_websocket_route("/ws",app.WSEndpoint)
