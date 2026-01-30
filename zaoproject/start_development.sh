#!/bin/bash
# Development startup script for ZaoConnect with automatic ngrok tunnel

echo "🚀 Starting ZaoConnect Development Environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONFIG_DIR="$HOME/.zaoconnect_config"
TOKEN_FILE="$CONFIG_DIR/ngrok_token"
SETUP_SCRIPT="$CONFIG_DIR/setup_token.sh"

# Load ngrok token from secure storage
load_ngrok_token() {
    if [ ! -f "$TOKEN_FILE" ]; then
        echo -e "${YELLOW}⚠️  ngrok auth token not found.${NC}"
        echo -e "${YELLOW}Setting up secure token storage...${NC}"
        
        if [ ! -f "$SETUP_SCRIPT" ]; then
            setup_ngrok_token
        else
            bash "$SETUP_SCRIPT"
        fi
    fi
    
    if [ -f "$TOKEN_FILE" ]; then
        NGROK_AUTHTOKEN=$(cat "$TOKEN_FILE")
        echo -e "${GREEN}✓ Loaded ngrok auth token from secure storage${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to load ngrok token${NC}"
        return 1
    fi
}

# Setup ngrok token interactively
setup_ngrok_token() {
    mkdir -p "$CONFIG_DIR"
    chmod 700 "$CONFIG_DIR"
    
    echo "🔐 ngrok authentication token not found."
    echo "Get your token from: https://dashboard.ngrok.com/auth"
    echo ""
    read -sp "Enter your ngrok auth token: " NGROK_AUTHTOKEN
    echo ""
    
    echo "$NGROK_AUTHTOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    
    echo "✓ Token saved securely to $TOKEN_FILE"
}

# Install ngrok if not present
install_ngrok() {
    if ! command -v ngrok &> /dev/null; then
        echo -e "${YELLOW}⚠️  ngrok is not installed. Installing...${NC}"
        sudo snap install ngrok
    fi
}

# Validate environment
validate_environment() {
    install_ngrok
    
    if [ ! -f ".env" ]; then
        echo -e "${RED}✗ .env file not found!${NC}"
        echo -e "${YELLOW}Please create a .env file first.${NC}"
        exit 1
    fi
}

# Start ngrok tunnel
start_ngrok() {
    echo ""
    echo -e "${BLUE}Starting ngrok tunnel on port 8000...${NC}"
    
    pkill -f "ngrok http" 2>/dev/null
    
    ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
    NGROK_PID=$!
    
    echo -e "${YELLOW}Waiting for ngrok to establish tunnel...${NC}"
    sleep 3
    
    NGROK_URL=""
    for i in {1..10}; do
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -oP '"public_url":"https://[^"]+' | head -1 | cut -d'"' -f4)
        if [ -n "$NGROK_URL" ]; then
            break
        fi
        echo -e "${YELLOW}Attempt $i/10: Waiting for ngrok...${NC}"
        sleep 1
    done
    
    if [ -z "$NGROK_URL" ]; then
        echo -e "${RED}✗ Could not establish ngrok tunnel${NC}"
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo "1. Check your ngrok auth token: $TOKEN_FILE"
        echo "2. Verify internet connection"
        echo "3. Check ngrok logs: tail -f /tmp/ngrok.log"
        kill $NGROK_PID 2>/dev/null
        exit 1
    fi
    
    echo -e "${GREEN}✓ ngrok tunnel established!${NC}"
    echo -e "${GREEN}✓ Public URL: $NGROK_URL${NC}"
}

# Update .env with ngrok URL
update_env() {
    echo -e "${BLUE}Updating .env with ngrok URL...${NC}"
    if grep -q "^MPESA_CALLBACK_HOST=" .env; then
        sed -i "s|^MPESA_CALLBACK_HOST=.*|MPESA_CALLBACK_HOST=$NGROK_URL|g" .env
    else
        echo "MPESA_CALLBACK_HOST=$NGROK_URL" >> .env
    fi
    echo -e "${GREEN}✓ .env updated${NC}"
}

# Main execution
main() {
    validate_environment
    
    if ! load_ngrok_token; then
        exit 1
    fi
    
    ngrok config add-authtoken "$NGROK_AUTHTOKEN" 2>/dev/null
    
    start_ngrok
    update_env
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ ngrok running on: $NGROK_URL${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}Starting Django development server...${NC}"
    echo ""
    
    python manage.py runserver
    
    trap "echo -e '\n${YELLOW}Shutting down...${NC}'; kill $NGROK_PID 2>/dev/null" EXIT
}

main
