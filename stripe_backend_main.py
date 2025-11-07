# main.py - Add these to your existing stripe-fulfillment main.py

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import stripe
import os

app = FastAPI()

# CORS - Allow your GitHub Pages domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sidneym31.github.io",  # Update with YOUR GitHub Pages URL
        "http://localhost:8080",
        "https://4dgaming.games",  # If you have custom domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Service pricing (in cents)
SERVICE_PRICES = {
    "chatbot": {"price": 15000, "name": "AI Chatbot Development"},
    "mobile": {"price": 50000, "name": "Mobile App Development"},
    "game": {"price": 20000, "name": "Game Development & Reskinning"},
    "web3": {"price": 30000, "name": "Web3 & Blockchain Development"},
    "scraping": {"price": 5000, "name": "Web Scraping & Lead Gen"},
    "pdf": {"price": 20000, "name": "PDF Generation"},
    "nft": {"price": 25000, "name": "NFT & Metaverse Assets"},
    "publishing": {"price": 10000, "name": "App Store Publishing"},
    "transcription": {"price": 1000, "name": "AI Transcription Service"},
    "trading": {"price": 50000, "name": "Trading Bot Development"}
}

@app.get("/")
async def root():
    return {"message": "4D Gaming Stripe Backend", "status": "active"}

@app.get("/config")
async def get_config():
    """Return Stripe publishable key for frontend"""
    publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
    if not publishable_key:
        raise HTTPException(status_code=500, detail="Stripe publishable key not configured")
    
    return {"publishableKey": publishable_key}

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """Create Stripe checkout session for 4D Gaming services"""
    try:
        data = await request.json()
        service = data.get("service")
        
        if service not in SERVICE_PRICES:
            raise HTTPException(status_code=400, detail="Invalid service")
        
        service_data = SERVICE_PRICES[service]
        
        # Get origin for redirect URLs
        origin = request.headers.get("origin", "https://sidneym31.github.io")
        
        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": service_data["name"],
                        "description": f"Professional {service_data['name']} service by 4D Gaming",
                        "metadata": {
                            "business": "4D Gaming",
                            "category": service
                        }
                    },
                    "unit_amount": service_data["price"],
                },
                "quantity": 1,
            }],
            mode="payment",
            payment_intent_data={
                "statement_descriptor": "4D GAMING",
                "statement_descriptor_suffix": "DEV",
            },
            success_url=f"{origin}/success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/#services",
            metadata={
                "business": "4D Gaming",
                "service_type": service
            }
        )
        
        return {"id": session.id}
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/checkout-session")
async def get_checkout_session(sessionId: str):
    """Retrieve checkout session details for success page"""
    try:
        session = stripe.checkout.Session.retrieve(sessionId)
        return session
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"Payment successful for 4D Gaming! Session: {session['id']}")
        
        # TODO: Send confirmation email to customer
        # TODO: Send notification to you
        # TODO: Create project in your system
    
    return {"received": True}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)