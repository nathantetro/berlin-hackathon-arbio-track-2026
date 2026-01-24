We are building a long-running AI Agent for the company ‘Arbio’. 

Arbio is an agentic AI platform that automates property management operations, turning human-heavy processes into autonomous agent-driven systems.

At Arbio, we have this challenge:
Onboarding a new property into a vacation rental management platform is an incredibly manual, time-consuming process that can take 15-30 hours of work across multiple teams. Operations must collect hundreds of data points: property details (address, size, amenities, capacity), photos, property-specific access instructions (lockbox locations, gate codes, WiFi networks, parking rules), local regulations and tax requirements, cleaning and linen specifications, guidebook content (appliance instructions, emergency contacts, house rules, local recommendations), integration with smart home devices, calendar setup across multiple booking platforms, pricing strategies, and minimum stay rules. Information arrives in unstructured formats - PDFs, emails, phone calls, photos, handwritten notes - and must be validated, standardized, and entered into multiple systems. Errors in onboarding lead to guest confusion, operational chaos, compliance issues, and poor reviews. The bottleneck in onboarding limits how fast property management companies can scale.

And we are trying to solve it in this way:
Build an AI agent that can autonomously extract, validate, and structure all necessary information from diverse unstructured sources (documents, emails, photos, websites) to complete property onboarding. The agent should identify missing information, proactively request it from property owners, validate data against compliance requirements, and populate all necessary systems, reducing manual work from days to hours.

So basically, its an email-native AI agent that:
1. Receives property submissions via email (documents, photos, all kinds of other unstructured data sources)
2. Extracts and structures data using tools
3. Researches local compliance requirements autonomously
4. Identifies missing information, any ambigiuities, etc, and sends follow-up emails (also via tools)
5. Learns patterns over time through trace logging (bottom-up schema discovery)

And then at the end, once the property is ‘ready’, the agent will send an email with all the info and images etc of the property in a PDF. And it will also send a URL in that email where the property owner can view the property, and edit things and then ‘validate’ it. 
So the agent would write in the email: ‘to validate this property, you’ll have to click on this url and review everything one more time and hit validate’. 
And on that URL the property owner can either validate, or if needed it can edit things and submit the edits. 

Validation is important, its part of our human-in-the-loop philosophy. 

We must use these 3 resources in our solution:
Tower.dev for Agent orchestration, workflow scheduling, Iceberg tables for state, and other kinds of storage

Runpod Serverless for GPU endpoints for OCR (PaddleOCR) and vision analysis (Florence-2)

OpenAI GPT-5.2 for the ai agent

And we’ll use the OpenAI Agents SDK to build the actual AI Agents (and any sub agents). Read about it here: https://github.com/openai/openai-agents-python

I recommend you to read about each of these sources.

——

Important DOs:
- Start simple, add complexity only when needed
- Use environment variables for all API keys
- Return summaries from tools, not raw data
- Log traces for every significant action
- Handle errors gracefully with user-friendly messages
- Keep the agent prompts focused and clear


Error Handling
- If OCR fails: fall back to asking owner to re-submit clearer document
- If compliance search fails: note "regulations could not be verified" and continue
- If email send fails: log error, retry once, then alert in dashboard


Think about all this and tell me, whats the best way to approach it? Shall we start with user stories first? or something else?