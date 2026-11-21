# Qazaq IT Networking — AI Smart Networking Assistant

AI-сервис для умного нетворкинга на IT-мероприятиях (команда 3-Bit).

## Запуск через Docker
1. Скопируйте .env.example в .env и укажите GEMINI_API_KEY.
2. Запустите:
   docker compose up --build
3. Откройте http://localhost:8000 (Swagger: http://localhost:8000/docs).

## Локальный запуск
pip install -r requirements.txt
python seed.py
uvicorn main:app --host 0.0.0.0 --port 8000
