// server.js - Stripe Payment Backend
require('dotenv').config();
const express = require('express');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

// Endpoint to get Stripe publishable key
// Add this endpoint for 4D Gaming config
app.get('/config', (req, res) => {
    res.json({
        publishableKey: process.env.STRIPE_PUBLISHABLE_KEY
    });
});

// Add this for 4D Gaming checkout
app.post('/4d-gaming/create-checkout-session', async (req, res) => {
    const { service } = req.body;
    
    const servicePrices = {
        'chatbot': { price: 15000, name: 'AI Chatbot Development' },
        'mobile': { price: 50000, name: 'Mobile App Development' },
        'game': { price: 20000, name: 'Game Development & Reskinning' },
        'web3': { price: 30000, name: 'Web3 & Blockchain Development' },
        'scraping': { price: 5000, name: 'Web Scraping & Lead Gen' },
        'pdf': { price: 20000, name: 'PDF Generation' },
        'nft': { price: 25000, name: 'NFT & Metaverse Assets' },
        'publishing': { price: 10000, name: 'App Store Publishing' },
        'transcription': { price: 1000, name: 'AI Transcription Service' },
        'trading': { price: 50000, name: 'Trading Bot Development' }
    };

    if (!servicePrices[service]) {
        return res.status(400).json({ error: 'Invalid service' });
    }

    const serviceData = servicePrices[service];

    try {
        const session = await stripe.checkout.sessions.create({
            payment_method_types: ['card'],
            line_items: [{
                price_data: {
                    currency: 'usd',
                    product_data: {
                        name: serviceData.name,
                        description: `Professional ${serviceData.name} service by 4D Gaming`,
                        metadata: {
                            business: '4D Gaming',
                            category: service
                        }
                    },
                    unit_amount: serviceData.price,
                },
                quantity: 1,
            }],
            mode: 'payment',
            payment_intent_data: {
                statement_descriptor: '4D GAMING',
                statement_descriptor_suffix: 'DEV',
            },
            success_url: `${req.headers.origin}/success.html?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${req.headers.origin}/#services`,
            metadata: {
                business: '4D Gaming',
                service_type: service
            }
        });

        res.json({ id: session.id });
    } catch (error) {
        console.error('Stripe error:', error);
        res.status(500).json({ error: error.message });
    }
});

// Add this for checkout session retrieval
app.get('/checkout-session', async (req, res) => {
    const { sessionId } = req.query;
    
    try {
        const session = await stripe.checkout.sessions.retrieve(sessionId);
        res.json(session);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Webhook to handle successful payments
app.post('/webhook', express.raw({type: 'application/json'}), async (req, res) => {
    const sig = req.headers['stripe-signature'];
    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

    let event;

    try {
        event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
    } catch (err) {
        console.error('Webhook signature verification failed:', err.message);
        return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    // Handle the checkout.session.completed event
    if (event.type === 'checkout.session.completed') {
        const session = event.data.object;
        
        // Fulfill the order...
        console.log('Payment successful!', session);
        
        // TODO: Send confirmation email to customer
        // TODO: Send notification to you
        // TODO: Create project in your system
    }

    res.json({received: true});
});

// Get session details for success page
app.get('/checkout-session', async (req, res) => {
    const { sessionId } = req.query;
    
    try {
        const session = await stripe.checkout.sessions.retrieve(sessionId);
        res.json(session);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`📧 Business email: ${process.env.BUSINESS_EMAIL || 'info@4dgaming.games'}`);
    console.log(`🌐 Frontend URL: ${process.env.FRONTEND_URL || 'http://localhost:8080'}`);
});