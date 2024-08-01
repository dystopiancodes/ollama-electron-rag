# ollama-electron-rag

install ollama and launch it

open new terminal
ollama pull llama3.1
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main

open new terminal
cd ../frontend
npm install
npm run build  
npm run dev
