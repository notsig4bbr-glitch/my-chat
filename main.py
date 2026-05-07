from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import sqlite3
import os
from datetime import datetime

app = FastAPI()

# База данных: text (сообщение), time (время)
db = sqlite3.connect("chat.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS messages (user TEXT, text TEXT, time TEXT)")
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
    
    # Загрузка истории с временем
    cursor = db.cursor()
    cursor.execute("SELECT user, text, time FROM messages")
    for row in cursor.fetchall():
        await websocket.send_text(f"[{row[2]}] {row[0]}: {row[1]}")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Получаем время
            current_time = datetime.now().strftime("%H:%M")
            
            # Сохраняем в базу
            db.execute("INSERT INTO messages (user, text, time) VALUES (?, ?, ?)", (username, data, current_time))
            db.commit()
            
            # Рассылаем всем
            for connection in active_connections:
                await connection.send_text(f"[{current_time}] {username}: {data}")
    except:
        active_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
