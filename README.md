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
