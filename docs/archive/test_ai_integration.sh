#!/bin/bash
# Quick test script for AI Copilot integration

echo "🧪 Testing AI Copilot Integration"
echo "=================================="
echo ""

# Check if backend is running
echo "1. Checking backend..."
curl -s http://localhost:8000/api/v1/ai/chat/history/ > /dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Backend is responding"
else
    echo "   ❌ Backend not responding - start with: python manage.py runserver"
fi
echo ""

# Check if frontend is built
echo "2. Checking frontend build..."
if [ -d "/home/ahmed/carbon/carbon-frontend/dist" ]; then
    echo "   ✅ Frontend is built"
else
    echo "   ⚠️  Frontend not built - run: npm run build"
fi
echo ""

# Check migrations
echo "3. Checking AI Copilot migrations..."
cd /home/ahmed/carbon/backend
MIGRATION_STATUS=$(python manage.py showmigrations ai_copilot 2>/dev/null | grep -c "\[X\]")
if [ "$MIGRATION_STATUS" -gt 0 ]; then
    echo "   ✅ Migrations applied ($MIGRATION_STATUS migrations)"
else
    echo "   ❌ Migrations not applied - run: python manage.py migrate"
fi
echo ""

# Check Redis
echo "4. Checking Redis..."
redis-cli ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Redis is running"
else
    echo "   ⚠️  Redis not running - some features may not work"
fi
echo ""

# Check ChromaDB directory
echo "5. Checking ChromaDB..."
if [ -d "/home/ahmed/carbon/backend/chroma_db" ]; then
    echo "   ✅ ChromaDB directory exists"
else
    echo "   ⚠️  ChromaDB not initialized - run: python seed_ai_knowledge.py"
fi
echo ""

echo "=================================="
echo "🎉 Setup Status Summary"
echo "=================================="
echo ""
echo "To start the full application:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd /home/ahmed/carbon/backend"
echo "  python manage.py runserver"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd /home/ahmed/carbon/carbon-frontend"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:5173"
echo ""
