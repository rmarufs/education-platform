import asyncio
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.user import User

client = TestClient(app)

def test_upload():
    # Создадим фиктивного пользователя если нет
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        print("No users found")
        return
    uid = user.id
    db.close()
    
    # Отправляем запрос с фиктивной сессией
    # Нужно подменить сессию
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        
    # К сожалению Session middleware работает сложнее, лучше протестировать саму утилиту Cloudinary
