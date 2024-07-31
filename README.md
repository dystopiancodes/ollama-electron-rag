# ollama-electron-rag

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main

cd ../frontend
npm install
npm run build  
npm run dev
