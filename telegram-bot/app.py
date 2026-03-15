"""
EeshaMart Telegram Bot - Production Ready
100% FREE on Render.com!

Bot: https://t.me/eeshamart_bot
"""

import httpx
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import random
import string
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EeshaMart Telegram Bot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Configuration - Uses environment variables (set in Render)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8142562507:AAG-_UExIh18e6mz-0URKmv67-CQOk_cuA4")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tcwdbokruvlizkxcpkzj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRjd2Rib2tydXZsaXpreGNwa3pqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAxMDkyNjQsImV4cCI6MjA3NTY4NTI2NH0.p871FXUakrWQ7PhhZr8Ly2BxLOhwQjRJiDGd59wAhyg")
AI_BACKEND_URL = os.environ.get("AI_BACKEND_URL", "https://fuhaddesmond-eeshamart-ai.hf.space/api/chat")

logger.info(f"🤖 EeshaMart Telegram Bot Starting...")
logger.info(f"📡 Token configured: {'Yes' if TELEGRAM_BOT_TOKEN else 'No'}")

# Storage (in-memory for free tier)
linked_accounts: Dict[int, dict] = {}
pending_links: Dict[str, dict] = {}
user_sessions: Dict[int, dict] = {}

def gen_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def send_telegram(chat_id: int, text: str):
    """Send message via Telegram API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    logger.info(f"📤 Sending to {chat_id}: {text[:50]}...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            result = response.json()
            if result.get("ok"):
                logger.info(f"✅ Message sent successfully!")
            else:
                logger.error(f"❌ Telegram error: {result}")
            return result
    except Exception as e:
        logger.error(f"❌ Send error: {e}")
        return {"ok": False, "error": str(e)}

async def get_cart(user_id: str) -> List[dict]:
    """Get user's cart from Supabase"""
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
    """Add product to cart in Supabase"""
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
    """Call EeshaMart AI backend"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                AI_BACKEND_URL,
                json={"message": message, "context": context}
            )
            return response.json() if response.status_code == 200 else {"success": False}
    except Exception as e:
        logger.error(f"AI error: {e}")
        return {"success": False, "response": "AI service unavailable. Please try again."}

async def process_message(chat_id: int, user_id: int, text: str, username: str = None) -> str:
    """Process incoming message and return response"""
    logger.info(f"📩 Processing from {chat_id}: {text}")
    
    text_lower = text.strip().lower()
    
    # Initialize session
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {"last_products": []}
    
    # ========== COMMANDS ==========
    
    # /start command
    if text_lower.startswith('/start'):
        code = gen_code()
        pending_links[code] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "expires": datetime.now() + timedelta(minutes=10)
        }
        
        if chat_id in linked_accounts:
            return """✅ *Welcome Back to EeshaMart!*

🛒 *I can help you:*
• Search for products
• Add items to cart
• View your cart
• Checkout
• Answer questions

_What would you like to shop for today?_"""
        
        return f"""👋 *Welcome to EeshaMart AI!*

I'm your personal shopping assistant, ready to help you find the best products!

🔗 *To link your account:*
1️⃣ Go to EeshaMart Profile Settings
2️⃣ Click "Link Telegram"
3️⃣ Enter code: `{code}`

_Or reply with:_ `LINK <your-user-id>`

_Code valid for 10 minutes_"""
    
    # Greetings
    if text_lower in ['hi', 'hello', 'hey', 'start', 'link', 'connect']:
        code = gen_code()
        pending_links[code] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "expires": datetime.now() + timedelta(minutes=10)
        }
        
        if chat_id in linked_accounts:
            return """✅ *Welcome Back!*

🛒 Search products
🛍️ Add to cart
📦 View cart
💳 Checkout

_What would you like?_"""
        
        return f"""👋 *EeshaMart AI!*

🔗 Link your account:
Code: `{code}`

Or reply: `LINK <user-id>`"""
    
    # Direct account linking
    if text_lower.startswith('link '):
        parts = text.strip().split()
        if len(parts) >= 2:
            eeshamart_user_id = parts[1]
            linked_accounts[chat_id] = {
                "user_id": eeshamart_user_id,
                "telegram_id": chat_id,
                "username": username,
                "history": []
            }
            return """✅ *Account Linked Successfully!*

🛒 Search products
🛍️ Add to cart
📦 View cart

_What would you like to buy?_"""
    
    # View cart command
    if text_lower in ['/cart', 'cart', 'my cart', 'view cart']:
        if chat_id not in linked_accounts:
            return "🔐 Please link your account first. Reply: `LINK <your-user-id>`"
        
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
                
                response += f"{i}. *{name}*\n"
                response += f"   {qty}x ₦{price:,} = ₦{subtotal:,}\n\n"
            
            response += f"💰 *Total: ₦{total:,}*\n\n"
            response += "_Say 'checkout' to proceed!_"
            return response
        else:
            return "🛒 Your cart is empty. Search for products to add!"
    
    # Checkout
    if text_lower in ['checkout', 'check out', '/checkout']:
        return """💳 *Ready to Checkout!*

To complete your purchase:
1️⃣ Visit eeshamart.com
2️⃣ Log in to your account
3️⃣ Go to your cart
4️⃣ Complete payment

_Your items are waiting!_ 🎉"""
    
    # Need account for other actions
    if chat_id not in linked_accounts:
        code = gen_code()
        pending_links[code] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "expires": datetime.now() + timedelta(minutes=10)
        }
        return f"""🔐 *Link Required*

Your code: `{code}`

Reply: `LINK <your-user-id>`"""
    
    # ========== PROCESS WITH AI ==========
    
    account = linked_accounts[chat_id]
    eeshamart_user_id = account["user_id"]
    
    # Get cart for context
    cart = await get_cart(eeshamart_user_id)
    
    # Build context for AI
    context = {
        "lastShownProducts": user_sessions[chat_id]["last_products"],
        "cartItems": cart,
        "cartTotal": sum(
            (item.get("products", {}).get("price", 0) * item.get("quantity", 1))
            for item in cart
        ),
        "isLoggedIn": True,
        "conversationHistory": account.get("history", [])[-10:]
    }
    
    # Call AI
    ai_result = await call_ai(text, context)
    
    if not ai_result.get("success"):
        return "❌ _Sorry, an error occurred. Please try again._"
    
    response = ai_result.get("response", "I'm here to help!")
    
    # Handle products returned
    if ai_result.get("products"):
        user_sessions[chat_id]["last_products"] = ai_result["products"]
        
        response += "\n\n📦 *Products Found:*\n"
        for i, p in enumerate(ai_result["products"][:5], 1):
            name = p.get("name", "Product")
            price = p.get("price", 0)
            response += f"\n{i}. *{name}*\n   💰 ₦{price:,}\n"
        
        response += "\n_Reply with a number to add to cart!_"
    
    # Handle actions
    action = ai_result.get("action")
    if action:
        action_type = action.get("type")
        
        if action_type == "add_to_cart":
            quantity = action.get("quantity", 1)
            
            if action.get("all"):
                for p in user_sessions[chat_id]["last_products"]:
                    await add_to_cart(eeshamart_user_id, p["id"], quantity)
                response = f"✅ Added all items to cart!"
            
            elif action.get("product_index"):
                idx = action["product_index"] - 1
                products = user_sessions[chat_id]["last_products"]
                
                if 0 <= idx < len(products):
                    product = products[idx]
                    await add_to_cart(eeshamart_user_id, product["id"], quantity)
                    response = f"✅ Added *{product.get('name')}* (x{quantity}) to your cart!"
                else:
                    response = "❌ Invalid product number. Please try again."
        
        elif action_type == "view_cart":
            cart_items = await get_cart(eeshamart_user_id)
            
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
                    
                    response += f"{i}. *{name}*\n"
                    response += f"   {qty}x ₦{price:,} = ₦{subtotal:,}\n\n"
                
                response += f"💰 *Total: ₦{total:,}*\n\n"
                response += "_Say 'checkout' to proceed!_"
            else:
                response = "🛒 Your cart is empty."
    
    # Update conversation history
    account.setdefault("history", []).extend([
        {"role": "user", "content": text},
        {"role": "assistant", "content": response}
    ])
    account["history"] = account["history"][-20:]
    
    return response


# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "EeshaMart Telegram Bot",
        "bot": "https://t.me/eeshamart_bot",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Health check for Render"""
    return {"status": "healthy"}

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram webhook"""
    try:
        body = await request.json()
        logger.info(f"📬 Webhook received: {json.dumps(body, indent=2)}")
        
        if "message" in body:
            message = body["message"]
            chat_id = message.get("chat", {}).get("id")
            user_id = message.get("from", {}).get("id")
            username = message.get("from", {}).get("username", "")
            
            text = message.get("text", "")
            
            # Handle photo messages
            if "photo" in message and not text:
                text = "What is this product?"
            
            if text:
                reply = await process_message(chat_id, user_id, text, username)
                result = await send_telegram(chat_id, reply)
                logger.info(f"📤 Send result: {result}")
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/setwebhook")
async def set_webhook(request: Request):
    """Set Telegram webhook - call this after deployment"""
    host = request.headers.get("host", "")
    if not host:
        return {"error": "Cannot determine host URL"}
    
    webhook_url = f"https://{host}/webhook/telegram"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json={"url": webhook_url})
        result = response.json()
    
    logger.info(f"🔗 Webhook set: {webhook_url}")
    return {
        "webhook_url": webhook_url,
        "result": result
    }

@app.get("/getme")
async def get_me():
    """Get bot info"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        return response.json()

@app.get("/getwebhookinfo")
async def get_webhook_info():
    """Get current webhook info"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        return response.json()

# API for account linking from website
@app.post("/api/link")
async def link_api(request: Request):
    """Link Telegram to EeshaMart account (called from website)"""
    try:
        body = await request.json()
        action = body.get("action")
        
        if action == "verify":
            code = body.get("code", "").upper()
            user_id = body.get("user_id")
            
            pending = pending_links.get(code)
            if not pending:
                return {"success": False, "error": "Invalid code"}
            
            if datetime.now() > pending["expires"]:
                del pending_links[code]
                return {"success": False, "error": "Code expired"}
            
            # Link account
            chat_id = pending["chat_id"]
            linked_accounts[chat_id] = {
                "user_id": user_id,
                "telegram_id": chat_id,
                "username": pending.get("username"),
                "history": []
            }
            
            del pending_links[code]
            
            # Notify user on Telegram
            await send_telegram(
                chat_id,
                "✅ *Account Linked Successfully!*\n\nYou can now shop via Telegram!"
            )
            
            return {"success": True}
        
        if action == "status":
            user_id = body.get("user_id")
            for chat_id, account in linked_accounts.items():
                if account["user_id"] == user_id:
                    return {"linked": True, "telegram_id": chat_id}
            return {"linked": False}
        
        return {"error": "Invalid action"}
    
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
