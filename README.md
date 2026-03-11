# 🏥 Swasthya Saathi — स्वास्थ्य साथी

> *"Mere ghar ke paas koi doctor nahi tha. Meri nani ko typhoid tha — hum log nahi jaante the ki sarkari aspatal mein muft ilaaj milta hai, na yeh ki unhe kaunsi dawai di gayi thi. Yeh tool usi sawaal ka jawab dene ke liye banaya gaya hai."*
>
> — Shivam Singh, Builder (Rural UP)

A **Hindi-first AI health agent** for rural Uttar Pradesh and Bihar. Built for people who don't have easy access to doctors, who can't afford private hospitals, and who don't know what medicines they've been prescribed.

---

## 🤖 What It Does

Swasthya Saathi is a **LangGraph ReAct agent** backed by a production-grade **hybrid RAG pipeline** (BM25 + FAISS + RRF fusion). The agent autonomously decides which tools to call based on what the user asks — no hardcoded if/else routing.

**Five tools, each backed by RAG:**

| Tool | Kya karta hai |
|------|---------------|
| `symptom_checker` | Lakshan sun ke bimari ki jaankari deta hai |
| `medicine_explainer` | Dawa ko simple Hindi mein samjhata hai |
| `scheme_checker` | PMJAY / Ayushman Bharat eligibility check karta hai |
| `health_center_locator` | Nazdeeki sarkari PHC/CHC dhundh ta hai |
| `prescription_reader` | Puri prescription ki ek ek dawa explain karta hai |

---

## 🏗️ Architecture

```
User Query (Hindi/English)
        │
        ▼
   FastAPI /chat
        │
        ▼
  LangGraph ReAct Agent
  ┌─────────────────────────────────────────┐
  │                                         │
  │  agent_node (Groq llama-3.3-70b)       │
  │      │                                  │
  │      ├── tool_calls? ──► tools_node    │
  │      │       │                          │
  │      │       └── tool result ──► back  │
  │      │                                  │
  │      └── final answer ──► END          │
  │                                         │
  └─────────────────────────────────────────┘
        │
        ▼
  Hybrid RAG Retriever (per tool)
  ┌──────────────────────────┐
  │  BM25 (keyword)          │
  │      +                   │
  │  FAISS (semantic, BGE)   │
  │      │                   │
  │  RRF Fusion              │
  └──────────────────────────┘
        │
        ▼
  Grounded Hindi Response
```

---

## 🚀 Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Current | Text agent, 5 RAG tools, FastAPI, CI/CD |
| **Phase 2** | 🔜 Next | Hindi Voice I/O (Sarvam TTS + Google STT) |
| **Phase 3** | 🔜 | React frontend + prescription image upload |
| **Phase 4** | 🔜 | Docker, evaluation harness, observability (Langfuse) |

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|------------|
| Agent Orchestration | LangGraph (ReAct pattern) |
| LLM | Groq — llama-3.3-70b-versatile |
| Embedder | BGE-small-en-v1.5 (SentenceTransformers) |
| Vector Search | FAISS IndexFlatIP (cosine similarity) |
| Keyword Search | BM25Okapi (rank-bm25) |
| Retrieval Fusion | RRF (Reciprocal Rank Fusion) |
| Backend API | FastAPI + uvicorn |
| CI/CD | GitHub Actions |

---

## 📦 Setup

### Prerequisites
- Python 3.10+
- Git with SSH configured
- A [Groq API key](https://console.groq.com) (free tier works)

### 1. Clone

```bash
git clone git@github.com:YOUR_USERNAME/swasthya-saathi.git
cd swasthya-saathi/backend
```

### 2. Virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Open .env and add your GROQ_API_KEY
```

### 5. Build FAISS indexes (run once)

```bash
python build_indexes.py
```

### 6. Start the server

```bash
uvicorn main:app --reload
```

Server runs at: `http://localhost:8000`

API docs: `http://localhost:8000/docs`

---

## 🧪 Example Queries

```bash
# Symptom check
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "mujhe 3 din se bukhar hai aur sar dard ho raha hai"}'

# Medicine question
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Paracetamol kab lena chahiye?"}'

# Prescription reading
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Doctor ne yeh dawaiyan di hain: Paracetamol, Amoxicillin, ORS"}'

# Government scheme
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Kya mujhe Ayushman Bharat card milega? Main UP mein rehta hoon"}'

# Find health center
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Varanasi mein sarkari aspatal kahan hai?"}'
```

---

## 🧪 Run Tests

```bash
pytest tests/ -v
```

---

## 🔧 Adding New Data

Drop `.txt` files into the relevant folder, then rebuild indexes:

```
backend/data/symptoms/     ← bimariyon ki jaankari
backend/data/medicines/    ← dawaon ki jaankari  
backend/data/schemes/      ← sarkari yojanaon ki jaankari
```

```bash
python build_indexes.py
```

---

## ⚠️ Disclaimer

Swasthya Saathi sirf jaankari dene ke liye bana hai. Yeh doctor ki jagah nahi hai. Kisi bhi serious bimari ya emergency mein **turant doctor se milein ya 108 dial karein.**

*This tool provides health information only, not medical advice. Always consult a qualified doctor for diagnosis and treatment.*

---

## 👤 Author

**Shivam Singh** — GenAI Engineer, rural UP
[LinkedIn](https://linkedin.com/in/shivam-singh) | [GitHub](https://github.com/shivamsinghssr)
