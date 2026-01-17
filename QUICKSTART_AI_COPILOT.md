# 🚀 AI Copilot - Quick Start Guide

> **Status Note (Jan 2026):** UI is ready, backend contract alignment is in progress. Streaming responses are available via SSE, but the UI currently uses non-streaming requests.

## Launch in 3 Steps

### Step 1: Start Backend
```bash
cd /home/ahmed/carbon/backend
python manage.py runserver
```

### Step 2: Start Frontend (New Terminal)
```bash
cd /home/ahmed/carbon/carbon-frontend
npm run dev
```

### Step 3: Open Browser
Navigate to: http://localhost:5173

---

## First-Time Setup (If Needed)

### Seed Knowledge Base
```bash
cd /home/ahmed/carbon/backend
python seed_ai_knowledge.py
```

### Start Redis (Optional - for conversation memory)
```bash
redis-server
```

---

## Using the AI Copilot

### Chat Interface
1. Look for the **AI panel on the right side** of the screen
2. Type your question: "What is Scope 1 emissions?"
3. Press **Enter** or click **Send**
4. View the AI response

### Example Questions
- "What is the difference between Scope 1, 2, and 3?"
- "How do I calculate emissions from mobile combustion?"
- "What is the GHG Protocol?"
- "Explain data quality tiers"
- "What are emission factors?"

### Proactive Insights
1. Click the **Insights tab** in the AI panel
2. View AI-generated suggestions
3. Click action buttons to navigate
4. Dismiss insights by clicking the X

### Customize Behavior
1. Click the **Settings icon** (⚙️) in the AI panel header
2. Adjust preferences:
   - Enable/disable proactive insights
   - Choose response detail level (concise, balanced, detailed)
   - Toggle conversation learning
3. Click **Save Preferences**

### Resize/Collapse Panel
- **Resize:** Drag the vertical line between main content and AI panel
- **Collapse:** Click the chevron button (◀) to minimize
- **Expand:** Click the chevron button (▶) to restore

---

## Troubleshooting

### Backend Not Responding
```bash
# Check if backend is running
curl http://localhost:8000/api/v1/ai/chat/history/

# If not, start it:
cd /home/ahmed/carbon/backend
python manage.py runserver
```

### Frontend Not Loading
```bash
# Check if frontend dev server is running
# Should see output like: "Local: http://localhost:5173"

# If not, start it:
cd /home/ahmed/carbon/carbon-frontend
npm run dev
```

### AI Not Responding
1. Check backend logs for errors
2. Verify POE_API_KEY in backend/.env
3. Check internet connection (POE API requires internet)

### Clear Chat History
Click the "Clear History" button above the message input

---

## Features Overview

✅ **Real-time Chat** - Ask questions, get instant AI responses  
✅ **Conversation Memory** - AI remembers context (20 messages)  
✅ **Proactive Insights** - AI suggests improvements automatically  
✅ **Project Context** - AI knows your current project  
✅ **Customizable** - Adjust behavior to your preferences  
✅ **Resizable** - Drag to resize or collapse the panel  
✅ **Persistent** - Settings and panel size saved automatically  

---

## Keyboard Shortcuts

- **Enter** - Send message
- **Shift+Enter** - New line in message

---

## Tips for Best Results

1. **Be specific** - "How to calculate diesel emissions" vs "emissions?"
2. **Provide context** - Mention if you're working on Scope 1, 2, or 3
3. **Ask follow-ups** - AI remembers your conversation
4. **Use insights** - Check the Insights tab regularly for suggestions
5. **Customize preferences** - Set detail level based on your expertise

---

## Need Help?

- **Documentation:** `/home/ahmed/carbon/docs/AI_COPILOT_*`
- **Test Script:** `./test_ai_integration.sh`
- **Backend README:** `backend/ai_copilot/README.md`

---

**Enjoy your AI-powered carbon management assistant! 🌱**
