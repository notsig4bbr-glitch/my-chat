from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import sqlite3
import os
from datetime import datetime

app = FastAPI()

db = sqlite3.connect("chat.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS messages (user TEXT, text TEXT, time TEXT)")
db.commit()

connections = []
users = {}

@app.get("/")
async def get():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/clear")
async def clear_history():
    db.execute("DELETE FROM messages")
    db.commit()
    return {"ok": True}

async def broadcast_users():
    unique_users = list(dict.fromkeys(users.values()))
    msg = f"USERS:{','.join(unique_users)}"
    for conn in connections[:]:
        try:
            await conn.send_text(msg)
        except:
            pass

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    connections.append(websocket)
    users[websocket] = username

    cursor = db.cursor()
    cursor.execute("SELECT user, text, time FROM messages ORDER BY rowid ASC")
    for user, text, time_str in cursor.fetchall():
        await websocket.send_text(f"[{time_str}] {user}: {text}")

    await broadcast_users()

    try:
        while True:
            data = await websocket.receive_text()
            current_time = datetime.now().strftime("%H:%M")

            if data == "/clear":
                db.execute("DELETE FROM messages")
                db.commit()
                for conn in connections[:]:
                    try:
                        await conn.send_text("🗑️ История очищена")
                    except:
                        pass
                continue

            db.execute(
                "INSERT INTO messages (user, text, time) VALUES (?, ?, ?)",
                (username, data, current_time)
            )
            db.commit()

            msg = f"[{current_time}] {username}: {data}"
            for conn in connections[:]:
                try:
                    await conn.send_text(msg)
                except:
                    pass

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connections:
            connections.remove(websocket)
        if websocket in users:
            del users[websocket]
        await broadcast_users()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
