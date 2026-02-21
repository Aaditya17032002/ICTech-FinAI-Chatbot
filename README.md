# ICTech FinAI Chatbot

An AI-powered investment insight chatbot built with FastAPI and React.

## Features

- 🤖 AI-powered investment advice using PydanticAI and Groq
- 📊 Real-time mutual fund data from AMFI India
- 📈 Stock market data from Yahoo Finance
- 💬 Conversational interface with memory
- 🎨 Modern React frontend with Tailwind CSS

## Project Structure

```
├── Backend/           # FastAPI backend
│   ├── app/
│   │   ├── agents/    # AI agents
│   │   ├── api/       # API routes
│   │   ├── models/    # Data models
│   │   └── services/  # Business logic
│   ├── static/        # Frontend build (generated)
│   └── requirements.txt
├── Frontend/          # React frontend
│   ├── src/
│   └── package.json
└── README.md
```

## Local Development

### Backend

```bash
cd Backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

## Building for Production

Build the frontend and output to Backend/static:

```bash
cd Frontend
npm run build
```

The FastAPI backend will automatically serve the built frontend.

## Deployment on Render

1. Push to GitHub
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Set **Root Directory** to `Backend`
5. Add environment variables:
   - `GROQ_API_KEY`: Your Groq API key
6. Deploy!

The backend serves both the API and the frontend static files.

## Environment Variables

### Backend
- `GROQ_API_KEY` - Groq API key for AI models
- `CORS_ORIGINS` - Allowed CORS origins (default: *)

## API Documentation

Once running, visit:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Disclaimer

This application provides information for educational purposes only. Investment decisions should be made after consulting a qualified financial advisor.
