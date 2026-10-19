### Backend

pip install -r requirements.txt

Create an .env file in the root directory:  
ANTHROPIC_API_KEY=...  OPENAI_API_KEY=...  CHROMA_API_KEY=...

cd backend  
uvicorn main:app --reload

### Frontend

cd frontend  
npm install  
ng serve  
