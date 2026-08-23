from fastapi import WebSocket

type JsonElement = None | bool | int | float | str | list[JsonElement] | dict[
    str, JsonElement
]


class WebSocketManager:
    def __init__(self) -> None:
        self._active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)

    async def broadcast(self, data: JsonElement) -> None:
        for connection in self._active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass
