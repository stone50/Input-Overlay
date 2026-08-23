from evdev import InputEvent
from asyncio import create_task, CancelledError, Task
from contextlib import asynccontextmanager
from evdev import list_devices, ecodes, InputDevice
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from json import load
from os.path import abspath, dirname, join
from sys import stderr
from typing import AsyncGenerator
from uvicorn import run
from web_socket_manager import WebSocketManager

EVENTS_TO_READ: dict[int, tuple[set[int], set[int]]] = {
    ecodes.EV_KEY: (
        {
            ecodes.KEY_ESC,
            ecodes.KEY_F1,
            ecodes.KEY_F2,
            ecodes.KEY_F3,
            ecodes.KEY_F4,
            ecodes.KEY_F5,
            ecodes.KEY_F6,
            ecodes.KEY_F7,
            ecodes.KEY_F8,
            ecodes.KEY_F9,
            ecodes.KEY_F10,
            ecodes.KEY_F11,
            ecodes.KEY_F12,
            ecodes.KEY_GRAVE,
            ecodes.KEY_0,
            ecodes.KEY_1,
            ecodes.KEY_2,
            ecodes.KEY_3,
            ecodes.KEY_4,
            ecodes.KEY_5,
            ecodes.KEY_6,
            ecodes.KEY_7,
            ecodes.KEY_8,
            ecodes.KEY_9,
            ecodes.KEY_MINUS,
            ecodes.KEY_EQUAL,
            ecodes.KEY_BACKSPACE,
            ecodes.KEY_A,
            ecodes.KEY_B,
            ecodes.KEY_C,
            ecodes.KEY_D,
            ecodes.KEY_E,
            ecodes.KEY_F,
            ecodes.KEY_G,
            ecodes.KEY_H,
            ecodes.KEY_I,
            ecodes.KEY_J,
            ecodes.KEY_K,
            ecodes.KEY_L,
            ecodes.KEY_M,
            ecodes.KEY_N,
            ecodes.KEY_O,
            ecodes.KEY_P,
            ecodes.KEY_Q,
            ecodes.KEY_R,
            ecodes.KEY_S,
            ecodes.KEY_T,
            ecodes.KEY_U,
            ecodes.KEY_V,
            ecodes.KEY_W,
            ecodes.KEY_X,
            ecodes.KEY_Y,
            ecodes.KEY_Z,
            ecodes.KEY_TAB,
            ecodes.KEY_CAPSLOCK,
            ecodes.KEY_LEFTSHIFT,
            ecodes.KEY_LEFTCTRL,
            ecodes.KEY_LEFTMETA,
            ecodes.KEY_LEFTALT,
            ecodes.KEY_SPACE,
            ecodes.KEY_LEFTBRACE,
            ecodes.KEY_RIGHTBRACE,
            ecodes.KEY_BACKSLASH,
            ecodes.KEY_SEMICOLON,
            ecodes.KEY_APOSTROPHE,
            ecodes.KEY_ENTER,
            ecodes.KEY_COMMA,
            ecodes.KEY_DOT,
            ecodes.KEY_SLASH,
            ecodes.KEY_RIGHTSHIFT,
            ecodes.KEY_RIGHTALT,
            ecodes.KEY_FN,
            ecodes.KEY_MENU,
            ecodes.KEY_RIGHTCTRL,
            ecodes.KEY_SYSRQ,
            ecodes.KEY_SCROLLLOCK,
            ecodes.KEY_PAUSE,
            ecodes.KEY_INSERT,
            ecodes.KEY_HOME,
            ecodes.KEY_PAGEUP,
            ecodes.KEY_DELETE,
            ecodes.KEY_END,
            ecodes.KEY_PAGEDOWN,
            ecodes.KEY_UP,
            ecodes.KEY_DOWN,
            ecodes.KEY_LEFT,
            ecodes.KEY_RIGHT,
            ecodes.KEY_NUMLOCK,
            ecodes.KEY_KPSLASH,
            ecodes.KEY_KPASTERISK,
            ecodes.KEY_KPMINUS,
            ecodes.KEY_KPPLUS,
            ecodes.KEY_KPENTER,
            ecodes.KEY_KPDOT,
            ecodes.KEY_KP0,
            ecodes.KEY_KP1,
            ecodes.KEY_KP2,
            ecodes.KEY_KP3,
            ecodes.KEY_KP4,
            ecodes.KEY_KP5,
            ecodes.KEY_KP6,
            ecodes.KEY_KP7,
            ecodes.KEY_KP8,
            ecodes.KEY_KP9,
            ecodes.BTN_LEFT,
            ecodes.BTN_RIGHT,
            ecodes.BTN_MIDDLE,
            ecodes.BTN_SIDE,
            ecodes.BTN_EXTRA,
        },
        {1, 0},
    ),
    ecodes.EV_REL: ({ecodes.REL_WHEEL}, {1, -1}),
}


base_dir: str = dirname(abspath(__file__))
config_path: str = join(base_dir, "config.json")
overlay_html_path: str = join(base_dir, "overlay.html")
icon_path: str = join(base_dir, "logo.ico")

with open(config_path, "r") as f:
    config = load(f)


api_port: int = config["API_PORT"]


ws_manager = WebSocketManager()


def should_read_device(device: InputDevice[str]) -> bool:
    for event, codes in device.capabilities().items():
        data_to_read: tuple[set[int], set[int]] | None = EVENTS_TO_READ.get(event)
        if not data_to_read:
            continue

        codes_to_read, values_to_read = data_to_read
        if any(c in codes_to_read for c in codes):
            return True

    return False


def get_devices() -> list[InputDevice[str]]:
    all_devices: list[InputDevice[str]] = [InputDevice(path) for path in list_devices()]
    return list(filter(should_read_device, all_devices))


async def read_device_events(device: InputDevice[str]) -> None:
    async for event in device.async_read_loop():
        input_event: InputEvent = event

        data_to_read: tuple[set[int], set[int]] | None = EVENTS_TO_READ.get(
            input_event.type
        )
        if not data_to_read:
            continue

        codes_to_read, values_to_read = data_to_read
        if input_event.code not in codes_to_read:
            continue

        if input_event.value not in values_to_read:
            continue

        await ws_manager.broadcast(
            {
                "type": input_event.type,
                "code": input_event.code,
                "value": input_event.value,
            }
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    devices: list[InputDevice[str]] = get_devices()
    tasks: list[Task[None]] = []
    for device in devices:
        tasks.append(create_task(read_device_events(device)))

    try:
        yield
    except CancelledError:
        pass
    except Exception as e:
        print(e, file=stderr)
    finally:
        print()
        print("Shutting down")
        for task in tasks:
            task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(icon_path)


@app.websocket("/ws")
async def overlay_websocket(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, CancelledError):
        pass
    finally:
        ws_manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def overlay() -> HTMLResponse:
    with open(overlay_html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    run("main:app", host="127.0.0.1", port=api_port)
