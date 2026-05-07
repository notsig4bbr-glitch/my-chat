from fastapi import FastAPI, WebSocket, File, UploadFile, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import sqlite3
import os
from datetime import datetime
import base64

app = FastAPI()

db = sqlite3.connect("chat.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS messages (user TEXT, text TEXT, time TEXT, image BLOB)")
db.commit()

active_users = {}
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

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    # Берем первые 100KB (достаточно для превью)
    image_data = contents[:100000]
    return {"image_b64": base64.b64encode(image_data).decode()}

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections.append(websocket)
    active_users[websocket] = username
    
    cursor = db.cursor()
    cursor.execute("SELECT user, text, time, image FROM messages ORDER BY rowid DESC LIMIT 50")
    for row in reversed(cursor.fetchall()):
        parts = [f"[{row[2]}] {row[0]}: {row[1]}"]
        if row[3]:
            parts.append(f"<img src='data:image/png;base64,{row[3].decode()}' style='max-width:100%;border-radius:10px;'>")
        await websocket.send_text("|||".join(parts))
    
    await broadcast_users()
    
    try:
        while True:
            data = await websocket.receive_text()
            
            current_time = datetime.now().strftime("%H:%M")
            
            if data == '/clear':
                db.execute("DELETE FROM messages")
                db.commit()
                for conn in active_connections[:]:
                    try:
                        await conn.send_text("🗑️ История чата очищена!")
                    except: pass
                continue
            
            image_data = None
            text_content = data
            if data.startswith("IMG:"):
                image_b64 = data[4:]
                image_data = base64.b64encode(base64.b64decode(image_b64))[:100000]
                text_content = "🖼️ Картинка"
            
            db.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", 
                      (username, text_content, current_time, image_data))
            db.commit()
            
            parts = [f"[{current_time}] {username}: {text_content}"]
            if image_data:
                parts.append(f"<img src='data:image/png;base64,{image_data.decode()}' style='max-width:100%;border-radius:10px;'>")
            
            for conn in active_connections[:]:
                try:
                    await conn.send_text("|||".join(parts))
                except: pass
                    
    except WebSocketDisconnect:
        if websocket in active_connections: active_connections.remove(websocket)
        if websocket in active_users: del active_users[websocket]
        await broadcast_users()

async def broadcast_users():
    users = list(set(active_users.values()))
    for conn in active_connections[:]:
        try:
            await conn.send_text(f"USERS:{','.join(users)}")
        except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
