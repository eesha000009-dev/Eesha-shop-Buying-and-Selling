"""
EeshaMart Telegram Bot - Production Ready
Email/Password Authentication for Seamless Account Linking

Bot: https://t.me/eeshamart_bot
"""

import httpx
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import string
import re
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EeshaMart Telegram Bot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8142562507:AAG-_UExIh18e6mz-0URKmv67-CQOk_cuA4")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tcwdbokruvlizkxcpkzj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRjd2Rib2tydXZsaXpreGNwa3pqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAxMDkyNjQsImV4cCI6MjA3NTY4NTI2NH0.p871FXUakrWQ7PhhZr8Ly2BxLOhwQjRJiDGd59wAhyg")
AI_BACKEND_URL = os.environ.get("AI_BACKEND_URL", "https://fuhaddesmond-eeshamart-ai.hf.space/api/chat")

logger.info("🤖 EeshaMart Telegram Bot Starting...")

# Storage
linked_accounts: Dict[int, dict] = {}  # chat_id -> user info
auth_sessions: Dict[int, dict] = {}    # chat_id -> auth session (email waiting, password waiting)
user_sessions: Dict[int, dict] = {}    # chat_id -> shopping session

# Auth states
AUTH_STATE_NONE = "none"
AUTH_STATE_EMAIL = "waiting_email"
AUTH_STATE_PASSWORD = "waiting_password"

async def send_telegram(chat_id: int, text: str, keyboard: list = None):
    """Send message via Telegram API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if keyboard:
        payload["reply_markup"] = json.dumps({"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": True})
    
    logger.info(f"📤 Sending to {chat_id}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            result = response.json()
            if not result.get("ok"):
                logger.error(f"❌ Telegram error: {result}")
            return result
    except Exception as e:
        logger.error(f"❌ Send error: {e}")
        return {"ok": False, "error": str(e)}

async def verify_supabase_auth(email: str, password: str) -> Optional[dict]:
    """Verify user credentials with Supabase Auth"""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "email": email,
        "password": password
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "user_id": data.get("user", {}).get("id"),
                    "email": data.get("user", {}).get("email"),
                    "access_token": data.get("access_token")
                }
            else:
                error = response.json().get("error_description", "Invalid credentials")
                logger.error(f"Auth failed: {error}")
                return None
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return None

async def get_user_profile(user_id: str, token: str) -> Optional[dict]:
    """Get user profile from Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                profiles = response.json()
                return profiles[0] if profiles else None
    except Exception as e:
        logger.error(f"Profile error: {e}")
    return None

async def get_cart(user_id: str) -> List[dict]:
    """Get user's cart"""
    url = f"{SUPABASE_URL}/rest/v1/cart_items?user_id=eq.{user_id}&select=id,quantity,product_id,products(*)"
    headers = {"apikey": SUPABASE_KEY}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            return response.json() if response.status_code == 200 else []
    except Exception as e:
        logger.error(f"Cart error: {e}")
        return []

async def add_to_cart(user_id: str, product_id: int, quantity: int = 1) -> bool:
    """Add product to cart"""
    url = f"{SUPABASE_URL}/rest/v1/cart_items?user_id=eq.{user_id}&product_id=eq.{product_id}&select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            existing = response.json()
            
            if existing:
                await client.patch(
                    f"{SUPABASE_URL}/rest/v1/cart_items?id=eq.{existing[0]['id']}",
                    headers=headers,
                    json={"quantity": existing[0]["quantity"] + quantity}
                )
            else:
                await client.post(
                    f"{SUPABASE_URL}/rest/v1/cart_items",
                    headers=headers,
                    json={"user_id": user_id, "product_id": product_id, "quantity": quantity}
                )
        return True
    except Exception as e:
        logger.error(f"Add to cart error: {e}")
        return False

async def call_ai(message: str, context: dict) -> dict:
    """Call AI backend"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(AI_BACKEND_URL, json={"message": message, "context": context})
            return response.json() if response.status_code == 200 else {"success": False}
    except Exception as e:
        logger.error(f"AI error: {e}")
        return {"success": False, "response": "AI service unavailable"}

async def process_message(chat_id: int, user_id: int, text: str, username: str = None) -> str:
    """Process incoming message"""
    logger.info(f"📩 From {chat_id}: {text}")
    
    text_lower = text.strip().lower()
    
    # Initialize session
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {"last_products": []}
    
    # ========== AUTHENTICATION FLOW ==========
    
    # Check if user is in auth flow
    if chat_id in auth_sessions:
        session = auth_sessions[chat_id]
        
        # Cancel auth
        if text_lower in ['/cancel', 'cancel']:
            del auth_sessions[chat_id]
            return "❌ Authentication cancelled. Send /start to try again."
        
        # Waiting for email
        if session["state"] == AUTH_STATE_EMAIL:
            email = text.strip()
            # Validate email
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return "❌ Invalid email format. Please enter a valid email:\n\nOr send /cancel to cancel."
            
            auth_sessions[chat_id] = {"state": AUTH_STATE_PASSWORD, "email": email}
            return "🔑 *Great! Now enter your password:*\n\n_Your password is secure and not stored._"
        
        # Waiting for password
        if session["state"] == AUTH_STATE_PASSWORD:
            password = text.strip()
            email = session["email"]
            
            # Verify with Supabase
            auth_result = await verify_supabase_auth(email, password)
            
            if auth_result:
                # Get user profile
                profile = await get_user_profile(auth_result["user_id"], auth_result["access_token"])
                name = profile.get("full_name", email.split("@")[0]) if profile else email.split("@")[0]
                
                # Link account
                linked_accounts[chat_id] = {
                    "user_id": auth_result["user_id"],
                    "email": email,
                    "name": name,
                    "telegram_id": chat_id,
                    "username": username,
                    "history": []
                }
                
                del auth_sessions[chat_id]
                
                return f"""✅ *Welcome, {name}!*

🎉 Your account is now linked!

🛒 *You can now:*
• Search for products
• Add items to cart
• View your cart
• Checkout

_What would you like to shop for today?_"""
            else:
                del auth_sessions[chat_id]
                return """❌ *Login Failed*

Invalid email or password. Please try again:
Send /start to retry"""
    
    # ========== COMMANDS ==========
    
    # Start command
    if text_lower.startswith('/start'):
        # Check if already linked
        if chat_id in linked_accounts:
            account = linked_accounts[chat_id]
            name = account.get("name", "there")
            return f"""✅ *Welcome back, {name}!*

🛒 *I can help you:*
• Search for products
• Add items to cart
• View your cart
• Checkout

_What would you like?_"""
        
        # Start auth flow
        auth_sessions[chat_id] = {"state": AUTH_STATE_EMAIL}
        return """👋 *Welcome to EeshaMart AI!*

I'm your personal shopping assistant.

🔐 *To get started, please enter your email:*

_This will link your Telegram to your EeshaMart account._

Or send /cancel to cancel."""
    
    # Login command
    if text_lower in ['/login', 'login']:
        if chat_id in linked_accounts:
            return "✅ You're already logged in! Send /logout to unlink."
        auth_sessions[chat_id] = {"state": AUTH_STATE_EMAIL}
        return "🔐 *Enter your email to login:*"
    
    # Logout command
    if text_lower in ['/logout', 'logout']:
        if chat_id in linked_accounts:
            del linked_accounts[chat_id]
            return "✅ You've been logged out. Send /start to login again."
        return "You're not logged in."
    
    # Cart command
    if text_lower in ['/cart', 'cart', 'my cart', 'view cart']:
        if chat_id not in linked_accounts:
            return "🔐 Please login first. Send /start"
        
        account = linked_accounts[chat_id]
        cart_items = await get_cart(account["user_id"])
        
        if cart_items:
            response = "🛒 *Your Cart:*\n\n"
            total = 0
            for i, item in enumerate(cart_items, 1):
                product = item.get("products", {})
                name = product.get("name", "Item")
                price = product.get("price", 0)
                qty = item.get("quantity", 1)
                subtotal = price * qty
                total += subtotal
                response += f"{i}. *{name}*\n   {qty}x ₦{price:,} = ₦{subtotal:,}\n\n"
            response += f"💰 *Total: ₦{total:,}*\n\n"
            response += "_Say 'checkout' to proceed!_"
            return response
        return "🛒 Your cart is empty. Search for products to add!"
    
    # Checkout
    if text_lower in ['checkout', 'check out', '/checkout']:
        if chat_id not in linked_accounts:
            return "🔐 Please login first. Send /start"
        return """💳 *Ready to Checkout!*

To complete your purchase:
1️⃣ Visit eeshamart.com
2️⃣ Your cart is synced!
3️⃣ Complete payment

🎉 _Your items are waiting!_"""
    
    # Help command
    if text_lower in ['/help', 'help']:
        return """🆘 *Help - EeshaMart AI Bot*

📋 *Commands:*
/start - Login to your account
/cart - View your cart
/checkout - Proceed to checkout
/logout - Sign out
/help - Show this help

🛒 *Shopping:*
• Just type what you want to buy
• "Show me phones under 50000"
• "I need a laptop for school"
• "Add 1 to cart"

❓ *Need help?* Contact support@eeshamart.com"""
    
    # Check if logged in
    if chat_id not in linked_accounts:
        return """🔐 *Please login first!*

Send /start to login to your EeshaMart account."""
    
    # ========== SHOPPING WITH AI ==========
    
    account = linked_accounts[chat_id]
    cart = await get_cart(account["user_id"])
    
    context = {
        "lastShownProducts": user_sessions[chat_id]["last_products"],
        "cartItems": cart,
        "cartTotal": sum((item.get("products", {}).get("price", 0) * item.get("quantity", 1)) for item in cart),
        "isLoggedIn": True,
        "conversationHistory": account.get("history", [])[-10:]
    }
    
    ai_result = await call_ai(text, context)
    
    if not ai_result.get("success"):
        return "❌ _Error. Please try again._"
    
    response = ai_result.get("response", "I'm here to help!")
    
    # Handle products
    if ai_result.get("products"):
        user_sessions[chat_id]["last_products"] = ai_result["products"]
        response += "\n\n📦 *Products Found:*\n"
        for i, p in enumerate(ai_result["products"][:5], 1):
            response += f"\n{i}. *{p.get('name')}* - ₦{p.get('price'):,}\n"
        response += "\n_Reply with a number to add to cart!_"
    
    # Handle actions
    action = ai_result.get("action")
    if action:
        action_type = action.get("type")
        
        if action_type == "add_to_cart":
            quantity = action.get("quantity", 1)
            
            if action.get("all"):
                for p in user_sessions[chat_id]["last_products"]:
                    await add_to_cart(account["user_id"], p["id"], quantity)
                response = "✅ Added all items to cart!"
            elif action.get("product_index"):
                idx = action["product_index"] - 1
                products = user_sessions[chat_id]["last_products"]
                if 0 <= idx < len(products):
                    product = products[idx]
                    await add_to_cart(account["user_id"], product["id"], quantity)
                    response = f"✅ Added *{product.get('name')}* (x{quantity}) to cart!"
                else:
                    response = "❌ Invalid product number."
        
        elif action_type == "view_cart":
            return await process_message(chat_id, user_id, "/cart", username)
    
    # Update history
    account.setdefault("history", []).extend([
        {"role": "user", "content": text},
        {"role": "assistant", "content": response}
    ])
    account["history"] = account["history"][-20:]
    
    return response


# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    return {"status": "online", "service": "EeshaMart Telegram Bot", "bot": "https://t.me/eeshamart_bot"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        body = await request.json()
        logger.info(f"📬 Webhook: {json.dumps(body)}")
        
        if "message" in body:
            message = body["message"]
            chat_id = message.get("chat", {}).get("id")
            user_id = message.get("from", {}).get("id")
            username = message.get("from", {}).get("username", "")
            text = message.get("text", "")
            
            if "photo" in message and not text:
                text = "What is this product?"
            
            if text:
                reply = await process_message(chat_id, user_id, text, username)
                await send_telegram(chat_id, reply)
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/setwebhook")
async def set_webhook(request: Request):
    host = request.headers.get("host", "")
    webhook_url = f"https://{host}/webhook/telegram"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json={"url": webhook_url})
        return {"webhook_url": webhook_url, "result": response.json()}

@app.get("/getwebhookinfo")
async def get_webhook_info():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        return (await client.get(url)).json()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
