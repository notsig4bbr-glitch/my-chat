from fastapi import FastAPI, WebSocket, File, UploadFile, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import sqlite3
import os
from datetime import datetime
from PIL import Image
import io
import base64

app = FastAPI()

# Папка для картинок (не нужна, используем base64)
os.makedirs("uploads", exist_ok=True)

# База данных
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

# API для загрузки картинок
@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        return {"error": "Только картинки!"}
    
    contents = await file.read()
    image = Image.open(io.BytesIO(contents))
    
    # Сжимаем до 400x400
    image.thumbnail((400, 400), Image.Resampling.LANCZOS)
    
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_data = buffer.getvalue()
    
    return {"image_b64": base64.b64encode(image_data).decode()}

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections.append(websocket)
    active_users[websocket] = username
    
    # Загрузка истории с картинками
    cursor = db.cursor()
    cursor.execute("SELECT user, text, time, image FROM messages ORDER BY rowid DESC LIMIT 100")
    for row in reversed(cursor.fetchall()):
        msg_parts = [f"[{row[2]}] {row[0]}: {row[1]}"]
        if row[3]:
            img_src = f"data:image/png;base64,{base64.b64decode(row[3]).decode()}"
            msg_parts.append(f"<img src='{img_src}' style='max-width:100%;border-radius:10px;margin-top:5px;'>")
        await websocket.send_text("|||".join(msg_parts))
    
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
                    except:
                        pass
                continue
            
            image_data = None
            text_content = data
            
            # Если картинка
            if data.startswith("IMG:"):
                image_b64 = data[4:]
                image_data = base64.b64encode(base64.b64decode(image_b64)).decode()
                text_content = "🖼️ Картинка"
            
            # Сохраняем
            db.execute("INSERT INTO messages (user, text, time, image) VALUES (?, ?, ?, ?)", 
                      (username, text_content, current_time, image_data))
            db.commit()
            
            # Формируем сообщение для отправки
            msg_parts = [f"[{current_time}] {username}: {text_content}"]
            if image_data:
                img_src = f"data:image/png;base64,{image_data}"
                msg_parts.append(f"<img src='{img_src}' style='max-width:100%;border-radius:10px;margin-top:5px;'>")
            
            final_msg = "|||".join(msg_parts)
            
            for conn in active_connections[:]:
                try:
                    await conn.send_text(final_msg)
                except:
                    pass
                    
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
        if websocket in active_users:
            del active_users[websocket]
        await broadcast_users()

async def broadcast_users():
    users_list = list(set(active_users.get(conn, '') for conn in active_connections if conn in active_users))
    users_json = f"USERS:{','.join(users_list)}"
    
    for conn in active_connections[:]:
        try:
            await conn.send_text(users_json)
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
