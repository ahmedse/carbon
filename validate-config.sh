#!/bin/bash
# ============================================================================
# Configuration Validation Script
# ============================================================================
# Validates that backend and frontend configurations match
# Run this before starting the application
# ============================================================================

echo "🔍 Carbon Platform - Configuration Validator"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# ----------------------------------------------------------------------------
# 1. Check .env files exist
# ----------------------------------------------------------------------------
echo "📄 Checking configuration files..."
echo ""

if [ ! -f "backend/.env" ]; then
    echo -e "${RED}❌ backend/.env not found${NC}"
    echo "   Create it from: cp backend/.env.example backend/.env"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ backend/.env exists${NC}"
fi

if [ ! -f "carbon-frontend/.env" ]; then
    echo -e "${RED}❌ carbon-frontend/.env not found${NC}"
    echo "   Create it from: cp carbon-frontend/.env.example carbon-frontend/.env"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ carbon-frontend/.env exists${NC}"
fi

echo ""

# ----------------------------------------------------------------------------
# 2. Extract and validate backend configuration
# ----------------------------------------------------------------------------
echo "🔧 Validating backend configuration..."
echo ""

if [ -f "backend/.env" ]; then
    DJANGO_API_PREFIX=$(grep "^DJANGO_API_PREFIX=" backend/.env | cut -d '=' -f2)
    CORS_ORIGINS=$(grep "^CORS_ALLOWED_ORIGINS=" backend/.env | cut -d '=' -f2)
    
    echo "   DJANGO_API_PREFIX: $DJANGO_API_PREFIX"
    
    if [ "$DJANGO_API_PREFIX" == "/api/v1/" ]; then
        echo -e "   ${GREEN}✅ API prefix is correct${NC}"
    else
        echo -e "   ${RED}❌ API prefix should be /api/v1/ not $DJANGO_API_PREFIX${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    
    echo "   CORS_ALLOWED_ORIGINS: $CORS_ORIGINS"
    
    if [[ $CORS_ORIGINS == *"localhost:5173"* ]]; then
        echo -e "   ${GREEN}✅ CORS includes localhost:5173${NC}"
    else
        echo -e "   ${YELLOW}⚠️  CORS should include http://localhost:5173${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

echo ""

# ----------------------------------------------------------------------------
# 3. Extract and validate frontend configuration
# ----------------------------------------------------------------------------
echo "🔧 Validating frontend configuration..."
echo ""

if [ -f "carbon-frontend/.env" ]; then
    VITE_API_BASE_URL=$(grep "^VITE_API_BASE_URL=" carbon-frontend/.env | cut -d '=' -f2)
    
    echo "   VITE_API_BASE_URL: $VITE_API_BASE_URL"
    
    if [ "$VITE_API_BASE_URL" == "http://localhost:8000/api/v1/" ]; then
        echo -e "   ${GREEN}✅ Frontend API URL is correct${NC}"
    else
        echo -e "   ${RED}❌ Should be http://localhost:8000/api/v1/ not $VITE_API_BASE_URL${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""

# ----------------------------------------------------------------------------
# 4. Check if backend and frontend match
# ----------------------------------------------------------------------------
echo "🔄 Checking backend-frontend alignment..."
echo ""

if [ "$DJANGO_API_PREFIX" == "/api/v1/" ] && [ "$VITE_API_BASE_URL" == "http://localhost:8000/api/v1/" ]; then
    echo -e "${GREEN}✅ Backend and frontend configurations MATCH${NC}"
else
    echo -e "${RED}❌ Backend and frontend configurations DO NOT MATCH${NC}"
    echo "   Backend API prefix: $DJANGO_API_PREFIX"
    echo "   Frontend expects:   /api/v1/ (from $VITE_API_BASE_URL)"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# ----------------------------------------------------------------------------
# 5. Check if servers are running
# ----------------------------------------------------------------------------
echo "🚀 Checking running services..."
echo ""

# Check backend
if curl -s -f http://localhost:8000/api/v1/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running on port 8000${NC}"
else
    echo -e "${YELLOW}⚠️  Backend not running or not responding${NC}"
    echo "   Start with: cd backend && python manage.py runserver"
    WARNINGS=$((WARNINGS + 1))
fi

# Check frontend (dev server)
if curl -s -f http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is running on port 5173${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend not running${NC}"
    echo "   Start with: cd carbon-frontend && npm run dev"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${YELLOW}⚠️  Redis not running (AI conversation memory won't work)${NC}"
    echo "   Start with: redis-server"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ----------------------------------------------------------------------------
# 6. Check for hardcoded URLs in code
# ----------------------------------------------------------------------------
echo "🔎 Checking for hardcoded URLs..."
echo ""

HARDCODED_BACKEND=$(grep -r "localhost:800[0-9]" backend/**/*.py 2>/dev/null | grep -v ".env" | grep -v "__pycache__" | wc -l)
HARDCODED_FRONTEND=$(grep -r "localhost:800[0-9]" carbon-frontend/src/**/*.{js,jsx} 2>/dev/null | grep -v "config.js" | wc -l)

if [ "$HARDCODED_BACKEND" -eq 0 ]; then
    echo -e "${GREEN}✅ No hardcoded URLs in backend Python files${NC}"
else
    echo -e "${YELLOW}⚠️  Found $HARDCODED_BACKEND hardcoded URL(s) in backend${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$HARDCODED_FRONTEND" -eq 0 ]; then
    echo -e "${GREEN}✅ No hardcoded URLs in frontend code${NC}"
else
    echo -e "${YELLOW}⚠️  Found $HARDCODED_FRONTEND hardcoded URL(s) in frontend${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
echo "=============================================="
echo "📊 Validation Summary"
echo "=============================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}🎉 PERFECT! All checks passed!${NC}"
    echo ""
    echo "You're ready to start:"
    echo "  Terminal 1: cd backend && python manage.py runserver"
    echo "  Terminal 2: cd carbon-frontend && npm run dev"
    echo "  Browser:    http://localhost:5173"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}✅ Configuration is valid with $WARNINGS warning(s)${NC}"
    echo ""
    echo "You can proceed but consider fixing warnings"
else
    echo -e "${RED}❌ Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo ""
    echo "❗ Fix errors before starting the application"
    echo ""
    echo "Quick fixes:"
    echo "  1. Set DJANGO_API_PREFIX=/api/v1/ in backend/.env"
    echo "  2. Set VITE_API_BASE_URL=http://localhost:8000/api/v1/ in carbon-frontend/.env"
    echo "  3. Add http://localhost:5173 to CORS_ALLOWED_ORIGINS in backend/.env"
    echo "  4. Restart both servers"
    exit 1
fi

echo ""
