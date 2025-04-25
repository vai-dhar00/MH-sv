Astro
Astro is a next‑generation, web‑based mental health chatbot designed to simulate a warm, empathetic conversational therapist. Built with Flask, Socket.IO, and OpenAI, it supports both a direct Chat Completions flow and an optional RAG (Retrieval‑Augmented Generation) mode sourcing from grounding exercises, CBT reframing, and crisis resources.

🚀 **Features**
Therapeutic Conversation Flow
  Name capture & personalized greeting
  Gentle emotional inquiry & active listening
  Open‑ended support, coping strategies (grounding, breathing, CBT reframing, self‑compassion)
  Crisis intervention guidance when self‑harm is mentioned

Dual AI Modes
  Chat Completions API: Fully dynamic, system‑prompt‑driven therapist behavior.
  RAG Mode: Augments model responses with content from markdown knowledge bases (grounding_exercises.md, cbt_reframing.md, crisis_resources.md).

Web UI
  Responsive dark/light theme toggle
  Scrollable, timestamped chat history
  Voice input (Web Speech API)
  "Download Conversation" button for transcript export
  Reset Conversation endpoint to clear history

Easy Deployment
  Dockerfile (optional) or direct python app.py / python app_rag.py
  Environment‑driven API key & assistant configuration

📂 **Repository Structure**
astro/
├── app.py                   # Chat Completions implementation
├── app_rag.py               # RAG‑augmented implementation
├── templates/
│   ├── index.html           # Redirect landing page
│   ├── astro.html           # Original chat template
│   └── astro_rag.html       # RAG chat template
├── static/
│   ├── styles.css           # Shared styling
│   └── astro_avatar.png     # Bot avatar image
├── grounding_exercises.md   # Grounding technique docs (RAG)
├── cbt_reframing.md         # CBT reframing techniques (RAG)
├── crisis_resources.md      # Crisis hotline & resource info (RAG)
├── abc_config.json          # API keys & feature toggles
├── requirements.txt         # Python dependencies
└── README.md                # This file

⚙️ **Prerequisites**
  Python 3.8+
  Node.js & npm (optional, if extending frontend)
  Docker & Docker Compose (optional)
    Python packages (see requirements.txt):
      flask
      flask-socketio
      eventlet
      openai
      langchain
      faiss-cpu
      python-dotenv

🛠️ **Installation**
1. Clone the repo:
git clone https://github.com/yourusername/astro.git
cd astro

2. Create & activate a virtual environment:
   ```bash
python -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate

3. Install dependencies:
pip install -r requirements.txt
Configure `abc_config.json` with your OpenAI API key and (optionally) assistant ID:
   ```json
{
  "openai_api_key": "sk-...",
  "assistant_id": "asst_...",
  "bot_name": "Astro",
  // other toggles...
}


🏃 **Running the Chatbot**
Chat Completions Mode
python app.py
  Server listens on http://0.0.0.0:5002
  Frontend at http://localhost:5002/

RAG Mode
python app_rag.py
  Loads vectorstore from markdown chunks under the hood
  Frontend at http://localhost:5002/astro

💬 **Usage**
  Upon loading, the UI auto‑redirects to /astro and displays the prompt:
  “Hi, may I know your name?”
  Type or speak your response
  Continue the therapeutic dialogue
  Click “☀/🌙” to switch theme
  Click “➤” to send, “🎤” to speak, and the download icon to save the transcript
  POST to /reset (e.g. via the Reset button in header) to clear the session


🔧 **Customization**
  System Prompt: Edit the SYSTEM_PROMPT constant in app.py or app_rag.py to refine tone, stages, or guidance.
  Knowledge Bases (RAG): Update or add .md files to improve retrieved content.
  Frontend: Modify astro.html / astro_rag.html and styles.css to tailor the visual style or layout.

🤝 **Contributing**
  Fork the repo
  Create a feature branch (git checkout -b feat/YourFeature)
  Commit your changes (git commit -am 'Add awesome feature')
  Push to branch (git push origin feat/YourFeature)
  Open a Pull Request

📜 **License**
This project is licensed under the MIT License. See LICENSE for details.


Happy chatting—and may your journey toward mental wellness be supported by Astro!

