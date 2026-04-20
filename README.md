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

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 &


cd ../frontend
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &