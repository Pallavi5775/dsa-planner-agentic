# DSA Revision Planner

## How to Run

### 1. Start the FastAPI backend
```
cd backend
pip install fastapi uvicorn pydantic
uvicorn main:app --reload
```

### 2. Start the Streamlit frontend
```
cd ../frontend
pip install streamlit requests
streamlit run app.py
```

- The backend runs at http://localhost:8000
- The frontend runs at http://localhost:8501

You can now add questions, log practice, and view revision suggestions in your browser.



cd ~/DSA_TRACKER/backend
uvicorn main:app --host 0.0.0.0 --port 8000 &

cd ../frontend
streamlit run app.py --server.port 8501 --server.address 0.0.0.0

redeploy
ps aux | grep uvicorn
ps aux | grep streamlit
kill <PID>


cd /path/to/DSA_PROGRAM_REVISION
git pull


cd backend
pip install -r requirements.txt
cd ../frontend
pip install -r requirements.txt


cd /path/to/DSA_PROGRAM_REVISION/backend
uvicorn main:app --host 0.0.0.0 --port 8000 &


cd /path/to/DSA_PROGRAM_REVISION/frontend
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &


sudo tail -n 50 /var/log/nginx/error.log

sudo nano /etc/nginx/sites-available/dsa
sudo nginx -t
sudo systemctl reload nginx
export OPENAI_API_KEY="your-openai-api-key"


sudo fuser -k 8501/tcp
sudo fuser -k 8000/tcp

nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

nohup streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0 > frontend.log 2>&1 &