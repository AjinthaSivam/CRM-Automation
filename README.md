# 🧠 CRM Automation – Multi-Agent Customer Relationship Management System

## 📘 Overview
This backend is part of my research project:  
**“Optimizing Open-Source LLMs for CRM Automation in E-Commerce”**

It uses **Django** as the core backend and integrates with **LangGraph** and **DeepInfra (LLaMA models)** to automate complex **Customer Relationship Management (CRM)** tasks.

The system coordinates **multiple specialized AI agents** that work together to handle CRM tasks such as:
- **Named Entity Disambiguation (NED)**
- **Policy Violation Identification (PVI)**
- **Knowledge-based Question Answering (KQA)**

---

## 🎯 Research Goals
- Improve open-source LLM performance in complex CRM scenarios.  
- Implement task-specific agents to handle subtasks efficiently.  
- Benchmark against **CRMArena** tasks to evaluate system accuracy and reasoning.

---

## 🧩 Tech Stack
- **Backend:** Django (Python 3.10+)  
- **Framework:** LangGraph (Multi-agent system)  
- **Model Runtime:** DeepInfra (for LLaMA models)  

---

## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/AjinthaSivam/CRM-Automation.git
cd CRM-Automation/backend
```

### 2️⃣ Create and Activate Virtual Environment
```
python -m venv venv
source venv/bin/activate       # macOS/Linux
venv\Scripts\activate          # Windows
```

### 3️⃣ Install Dependencies
```
pip install -r requirements.txt
```

### 4️⃣ Run the Server
```
python manage.py runserver
```

### 🤖 Running the LLaMA Model (via DeepInfra)
Make sure you have access to DeepInfra API and your API key configured.
The backend will use DeepInfra to run the LLaMA model for all agent tasks.

### 🔍 API Endpoint
smart-query/
