from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import sqlite3
import os

app = FastAPI()

db = sqlite3.connect("chat.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS messages (user TEXT, text TEXT)")
db.commit()

active_connections = []

@app.get("/")
async def get():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/clear")
async def clear_history():
    db.execute("DELETE FROM messages")
    db.commit()
    return {"message": "История удалена!"}

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections.append(websocket)
    
    cursor = db.cursor()
    cursor.execute("SELECT user, text FROM messages")
    for row in cursor.fetchall():
        await websocket.send_text(f"{row[0]}: {row[1]}")
    
    try:
        while True:
            data = await websocket.receive_text()
            db.execute("INSERT INTO messages (user, text) VALUES (?, ?)", (username, data))
            db.commit()
            for connection in active_connections:
                await connection.send_text(f"{username}: {data}")
    except:
        active_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
