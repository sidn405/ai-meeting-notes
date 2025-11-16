"""
4D Gaming Chatbot Backend
Flask endpoint for chatbot using OpenAI API
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# System prompt for the chatbot
SYSTEM_PROMPT = """You are the 4D Gaming AI assistant, helping clients with questions about services, pricing, and the development process.

COMPANY INFO:
- Company: 4D Gaming
- Experience: 10+ years of development experience
- Published Apps: 8+ apps on Google Play & Amazon Appstore
- Projects: 100+ completed projects
- Client Satisfaction: 98%

SERVICES:
1. AI Chatbot Development - $2,500 (3-4 weeks)
   Custom AI chatbots with natural language processing
   
2. Mobile App Development - $5,000 (6-8 weeks)
   Cross-platform mobile apps using Flutter for iOS and Android
   
3. Game Development & Reskinning - $3,000 (4-6 weeks)
   Unity-based game development and app reskinning
   
4. Web3 & Blockchain - $4,000 (5-7 weeks)
   Smart contracts, DApps, NFT platforms, and blockchain integration
   
5. Web Scraping & Lead Generation - $2,000 (2-3 weeks)
   Automated data extraction and lead generation tools
   
6. Trading Bot Development - $4,500 (5-6 weeks)
   Automated trading bots for cryptocurrency and stock markets

PAYMENT PROCESS:
- 3-milestone system: 30% upfront, 50% mid-project, 20% on completion
- Transparent pricing with no hidden fees
- Full source code ownership
- Comprehensive documentation included

PROJECT PROCESS:
- Milestone 1 (30%): Discovery & Consultation - Discuss requirements, goals, timeline
- Milestone 2 (50%): Development & Integration - Building with regular updates
- Milestone 3 (20%): Testing, Revisions & Launch - Final testing and deployment

WEBSITE:
- Homepage: https://4dgaming.games
- Client Portal: https://4dgaming.games/client-login.html
- Pricing: https://4dgaming.games/pricing.html
- About: https://4dgaming.games/about.html

PERSONALITY:
- Professional but friendly
- Clear and concise
- Helpful and solution-oriented
- Avoid technical jargon unless asked

GUIDELINES:
- Always be specific about pricing and timelines when asked
- Encourage users to visit the client portal or contact page
- Direct users to start a project if they're ready
- If unsure, offer to connect them with the team
- Keep responses under 150 words unless explaining the full project process or listing all services
"""

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """Handle chatbot messages"""
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Build messages array for OpenAI
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Add conversation history (limit to last 10 messages)
        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective model
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        # Extract response
        bot_response = response.choices[0].message.content
        
        return jsonify({
            'response': bot_response,
            'success': True
        })
        
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({
            'error': 'Sorry, I encountered an error. Please try again.',
            'success': False
        }), 500

@app.route('/api/chatbot/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': '4D Gaming Chatbot'
    })

if __name__ == '__main__':
    # For Railway deployment
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)