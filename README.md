### Backend

pip install -r requirements.txt

Kreirati .env fajl u root direktoriju:
ANTHROPIC_API_KEY=...

OPENAI_API_KEY=...

CHROMA_API_KEY=...

cd backend
uvicorn main:app --reload

### Frontend

cd frontend
npm install
ng serve
