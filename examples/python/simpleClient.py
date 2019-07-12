import asyncio,websockets,json,wave,base64
from time import sleep
sr = 8000
chunkTimeLength = 0.01
waveFile = wave.open('../8khz_01.wav', 'r')

async def consumer(message,websocket):
    msg = json.loads(message)
    print("msg",msg)
    type = msg.get("type")
    res = None
    if type == 'WELCOME_MSG':
        print("welcome message")
    elif type == 'STATUS':
        data=msg.get("data")

        if data.get("result"):
            await websocket.send(json.dumps({'type':'SETUP'}))
    elif type == 'SETUP':
        data=msg.get("data")
        if data.get("result"):
            length = waveFile.getnframes()
            chunkSize = int(chunkTimeLength*sr)
            while waveFile.tell() < length:

                raw = waveFile.readframes(chunkSize)
                chunk = base64.b64encode(raw)
                msg = {
                    'type':'AUDIO_BUFFER',
                    'data': chunk.decode('utf-8'),
                    'count': int(waveFile.tell()/chunkSize)
                }
                await websocket.send(json.dumps(msg))
                #simulate a real real time voice
                await asyncio.sleep(chunkTimeLength)
            #force last transcription
            await websocket.send(json.dumps({"type":"REQ_TRANSCRIPTION"}))
            res="DONE"

    elif type == 'TRANSCRIPTION':
        data=msg.get("data")
        print(data.get("result"))
    else:
        print(msg)
    return res

async def consumer_handler(websocket):
    async for message in websocket:
        res =await consumer(message,websocket)
        if res=="DONE":
            print("DONE!")
            #and I would like to get out from here to close the connection..

async def client():
    uri = "ws://127.0.0.1:5000/ws"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({'type':'STATUS'}))
        consumer = asyncio.get_event_loop().create_task(consumer_handler(websocket))
        try:
            await consumer
            #TODO: how close the connection when the audio file is finished??
            await websocket.close()
        except:
            raise
        finally:
            consumer.cancel()
            print(consumer.done())
            print(consumer.cancelled())
c = client()
asyncio.get_event_loop().run_until_complete(c)

# #
# # async def handle_socket(uri, ):
# #     async with websockets.connect(uri) as websocket:
# #         async for message in websocket:
# #             print(message)
# #
# # async def handler():
# #     await handle_socket("ws://127.0.0.1:5000/ws")
#
# # import asyncio,websockets,json
# #
# async def hello():
#         async for message in websocket:
#             print(message)
#
#         await websocket.send(json.dumps({'type':'STATUS'}))
#
# #
# asyncio.get_event_loop().run_until_complete(hello())
#
# # asyncio.get_event_loop().run_until_complete(handler())
