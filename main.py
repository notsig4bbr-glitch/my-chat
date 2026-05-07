from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketState
import sqlite3
import os
from datetime import datetime
import base64

app = FastAPI()

db = sqlite3.connect("chat.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS messages (user TEXT, text TEXT, time TEXT, image TEXT)")
db.commit()

active_connections = []
active_users = {}

@app.get("/")
async def get():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/clear")
async def clear_history():
    db.execute("DELETE FROM messages")
    db.commit()
    return {"message": "История удалена"}

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    data = await file.read()
    return {"image_b64": base64.b64encode(data).decode()}

async def broadcast_users():
    users = list(dict.fromkeys(active_users.values()))
    msg = f"USERS:{','.join(users)}"
    for conn in active_connections[:]:
        try:
            if conn.client_state == WebSocketState.CONNECTED:
                await conn.send_text(msg)
        except:
            pass

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections.append(websocket)
    active_users[websocket] = username

    cursor = db.cursor()
    cursor.execute("SELECT user, text, time, image FROM messages ORDER BY rowid ASC")
    rows = cursor.fetchall()

    for user, text, time_str, image in rows:
        parts = [f"[{time_str}] {user}: {text}"]
        if image:
            parts.append(f"<img src='data:image/png;base64,{image}' style='max-width:100%;border-radius:10px;margin-top:5px;'>")
        await websocket.send_text("|||".join(parts))

    await broadcast_users()

    try:
        while True:
            data = await websocket.receive_text()
            current_time = datetime.now().strftime("%H:%M")

            if data == "/clear":
                db.execute("DELETE FROM messages")
                db.commit()
                for conn in active_connections[:]:
                    try:
                        if conn.client_state == WebSocketState.CONNECTED:
                            await conn.send_text("🗑️ История чата очищена!")
                    except:
                        pass
                continue

            if data.startswith("IMG:"):
                image_b64 = data[4:]
                text_content = "🖼️ Картинка"
                db.execute(
                    "INSERT INTO messages (user, text, time, image) VALUES (?, ?, ?, ?)",
                    (username, text_content, current_time, image_b64)
                )
                db.commit()

                msg = f"[{current_time}] {username}: {text_content}|||<img src='data:image/png;base64,{image_b64}' style='max-width:100%;border-radius:10px;margin-top:5px;'>"
            else:
                db.execute(
                    "INSERT INTO messages (user, text, time, image) VALUES (?, ?, ?, ?)",
                    (username, data, current_time, None)
                )
                db.commit()
                msg = f"[{current_time}] {username}: {data}"

            for conn in active_connections[:]:
                try:
                    if conn.client_state == WebSocketState.CONNECTED:
                        await conn.send_text(msg)
                except:
                    pass

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        if websocket in active_users:
            del active_users[websocket]
        await broadcast_users()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
