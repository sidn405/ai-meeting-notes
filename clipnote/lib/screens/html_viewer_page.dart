<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Q4 Planning Meeting - Meeting Summary</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .header .meta {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .offline-badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
            margin-top: 10px;
        }
        
        .content {
            padding: 30px;
        }
        
        .section {
            margin-bottom: 30px;
        }
        
        .section h2 {
            font-size: 20px;
            color: #667eea;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background: transparent;
            border: none;
            font-size: 16px;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        
        .tab:hover {
            color: #667eea;
        }
        
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .summary-text {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            line-height: 1.8;
        }
        
        .list-item {
            background: #f9f9f9;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }
        
        .transcript {
            background: #fafafa;
            padding: 20px;
            border-radius: 8px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.8;
            max-height: 600px;
            overflow-y: auto;
        }
        
        .no-content {
            color: #999;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }
        
        .footer {
            background: #f9f9f9;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }
        
        @media print {
            body {
                background: white;
                padding: 0;
            }
            .container {
                box-shadow: none;
            }
            .tabs {
                display: none;
            }
            .tab-content {
                display: block !important;
                page-break-before: always;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Q4 Planning Meeting</h1>
            <div class="meta">
                Meeting ID: 123 | 
                Created: 2025-10-27 10:30 |
                Status: complete
            </div>
            <div class="offline-badge">✓ Works Offline</div>
        </div>
        
        <div class="content">
            <div class="tabs">
                <button class="tab active" onclick="showTab('summary')">Summary</button>
                <button class="tab" onclick="showTab('action-items')">Action Items</button>
                <button class="tab" onclick="showTab('key-points')">Key Points</button>
                <button class="tab" onclick="showTab('transcript')">Full Transcript</button>
            </div>
            
            <div id="summary" class="tab-content active">
                <div class="section">
                    <h2>Meeting Summary</h2>
                    <div class="summary-text">
                        The Q4 planning meeting focused on strategic initiatives for the final quarter of 2025. The team discussed revenue targets, product launches, and resource allocation. Key decisions were made regarding the new mobile app feature set and marketing campaign timing. The group agreed on a phased rollout approach to minimize risk while maximizing market impact. Budget concerns were addressed with a proposal to reallocate funds from underperforming channels. Overall consensus was reached on prioritizing customer retention over new acquisition in Q4.
                    </div>
                </div>
            </div>
            
            <div id="action-items" class="tab-content">
                <div class="section">
                    <h2>Action Items</h2>
                    <div class="list-item">Sarah to finalize Q4 budget proposal by Friday and circulate to leadership team for approval</div>
                    <div class="list-item">Marketing team to draft campaign timeline for mobile app launch, including social media strategy</div>
                    <div class="list-item">Engineering to provide technical feasibility assessment for proposed features by next Monday</div>
                    <div class="list-item">John to schedule follow-up meeting with sales team regarding revenue targets and pipeline review</div>
                    <div class="list-item">HR to begin recruitment process for two additional customer success positions</div>
                </div>
            </div>
            
            <div id="key-points" class="tab-content">
                <div class="section">
                    <h2>Key Points</h2>
                    <div class="list-item">Q4 revenue target increased by 15% based on strong Q3 performance</div>
                    <div class="list-item">Mobile app launch date set for November 15th with soft launch to beta users</div>
                    <div class="list-item">Customer retention rate has improved to 94%, exceeding industry benchmark</div>
                    <div class="list-item">Budget reallocation approved: $50K moved from paid ads to content marketing</div>
                    <div class="list-item">New partnership with TechCorp will provide additional distribution channel</div>
                    <div class="list-item">Team headcount to increase by 3 positions before year-end</div>
                </div>
            </div>
            
            <div id="transcript" class="tab-content">
                <div class="section">
                    <h2>Full Transcript</h2>
                    <div class="transcript">[00:00] Sarah: Good morning everyone. Thanks for joining today's Q4 planning session. Let's start by reviewing our Q3 performance before diving into Q4 goals.

[00:45] John: Our Q3 numbers exceeded expectations. We hit 112% of our revenue target, which puts us in a strong position heading into the final quarter.

[01:20] Sarah: That's excellent news. Based on this momentum, I'm proposing we increase our Q4 target by 15%. Is that feasible from a sales perspective?

[02:05] John: Absolutely. Our pipeline is robust and we have several large deals in late stages. I'm confident we can hit the increased target.

[03:10] Mike: From an engineering standpoint, we need to discuss the mobile app launch timeline. We're on track for a November 15th release date, but we should plan a soft launch with beta users first.

[04:30] Sarah: Good point. Marketing team, can you work with Mike to coordinate the beta launch and plan the full marketing campaign?

[05:15] Jennifer: Yes, we'll get that timeline drafted this week. I also want to discuss our marketing budget allocation. Our paid ads haven't been performing as well as content marketing.

[06:40] Sarah: Let's address that. I'm open to reallocating funds if we can show better ROI with content marketing. Can you put together a proposal?

[07:30] Jennifer: Will do. I'm thinking we shift about $50K from paid ads to content for Q4.

[08:45] Sarah: Sounds reasonable. Let's make that change and monitor results closely. Now, regarding headcount...

[09:20] Lisa from HR: We've approved three new positions: two in customer success and one in engineering. We'll start the recruitment process immediately.

[10:15] Sarah: Perfect. Let's wrap up with action items. John, can you schedule a follow-up with the sales team? Mike, we need that technical assessment by Monday. Jennifer, get that campaign timeline to us ASAP.

[11:00] All: Agreed.

[11:10] Sarah: Great meeting everyone. Thanks for your time.</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Generated: 2025-10-27 16:00:00<br>
            This file works completely offline and contains all meeting data.
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            // Hide all tab contents
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.classList.remove('active'));
            
            // Remove active class from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
        }
    </script>
</body>
</html>