import asyncio
import websockets

async def test():
    try:
        ws = await websockets.connect('ws://127.0.0.1:8000/ws/chat')
        print('Connected!')
        await ws.close()
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(test())
