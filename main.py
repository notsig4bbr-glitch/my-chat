from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import sqlite3
import os
from datetime import datetime

app = FastAPI()

# База данных
db = sqlite3.connect("chat.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS messages (user TEXT, text TEXT, time TEXT)")
db.commit()

# Словарь активных пользователей
active_users = {}  # {websocket: username}
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
    active_users[websocket] = username
    
    # Загрузка истории
    cursor = db.cursor()
    cursor.execute("SELECT user, text, time FROM messages")
    for row in cursor.fetchall():
        await websocket.send_text(f"[{row[2]}] {row[0]}: {row[1]}")
    
    # Отправляем список активных пользователей ВСЕМ
    await broadcast_users()
    
    try:
        while True:
            data = await websocket.receive_text()
            
            current_time = datetime.now().strftime("%H:%M")
            
            # Команда очистки
            if data == '/clear':
                db.execute("DELETE FROM messages")
                db.commit()
                for conn in active_connections[:]:  # Копируем список
                    try:
                        await conn.send_text("🗑️ История чата очищена!")
                    except:
                        pass
                continue
            
            # Обычное сообщение
            db.execute("INSERT INTO messages (user, text, time) VALUES (?, ?, ?)", (username, data, current_time))
            db.commit()
            
            for connection in active_connections[:]:  # Копируем список
                try:
                    await connection.send_text(f"[{current_time}] {username}: {data}")
                except:
                    pass
                    
    except:
        active_connections.remove(websocket)
        if websocket in active_users:
            del active_users[websocket]
        await broadcast_users()  # Обновляем список при отключении

# АСИНХРОННАЯ функция рассылки списка пользователей
async def broadcast_users():
    users_list = [active_users.get(conn, '') for conn in active_connections if conn in active_users]
    users_json = f"USERS:{','.join(users_list)}"
    
    for conn in active_connections[:]:  # Копируем список
        try:
            await conn.send_text(users_json)
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
