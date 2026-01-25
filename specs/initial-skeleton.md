We are building a long-running AI Agent for the company ‘Arbio’. 

Arbio is an agentic AI platform that automates property management operations, turning human-heavy processes into autonomous agent-driven systems.

At Arbio, we have this challenge:
Onboarding a new property into a vacation rental management platform is an incredibly manual, time-consuming process that can take 15-30 hours of work across multiple teams. Operations must collect hundreds of data points: property details (address, size, amenities, capacity), photos, property-specific access instructions (lockbox locations, gate codes, WiFi networks, parking rules), local regulations and tax requirements, cleaning and linen specifications, guidebook content (appliance instructions, emergency contacts, house rules, local recommendations), integration with smart home devices, calendar setup across multiple booking platforms, pricing strategies, and minimum stay rules. Information arrives in unstructured formats - PDFs, emails, phone calls, photos, handwritten notes - and must be validated, standardized, and entered into multiple systems. Errors in onboarding lead to guest confusion, operational chaos, compliance issues, and poor reviews. The bottleneck in onboarding limits how fast property management companies can scale.

And we are trying to solve it in this way:
Build an AI agent that can autonomously extract, validate, and structure all necessary information from diverse unstructured sources (documents, emails, photos, websites) to complete property onboarding. The agent should identify missing information, proactively request it from property owners, validate data against compliance requirements, and populate all necessary systems, reducing manual work from days to hours.

So basically, its an email-native AI agent, called 'Arbie', that:
1. Receives property submissions via email (documents, photos, all kinds of other unstructured data sources)
2. Extracts and structures data using tools
3. Researches local compliance requirements autonomously
4. Identifies missing information, any ambigiuities, etc, and sends follow-up emails (also via tools)
5. Learns patterns over time through trace logging (bottom-up schema discovery)

And then at the end, once the property is ‘ready’, Arbie, the agent will send an email with all the info and images etc of the property in a PDF. 

And Arbie will also send a URL in that email where the property owner can view the property, and edit things and then ‘validate’ it. 

So Arbie would write in the email: ‘to validate this property, you’ll have to click on this url and review everything one more time and hit validate’. 

And on that URL the property owner can either validate, or if needed it can edit things and submit the edits. 

Validation is important, its part of our human-in-the-loop philosophy. 

-------

So we’re going to build it in this way:

- All in python
- Tower.dev for Agent orchestration, workflow scheduling, Iceberg tables for state, and other kinds of storage (there is an MCP available for that)
- OpenAI GPT-5.2 for the main LLM (Arbie agent)
- OpenAI Agents SDK to build the AI Agent (and any sub agents). (https://github.com/openai/openai-agents-python)
- MailerSend for the email client (mailersend.com)

I recommend you to read about each of these sources.

——

And we'll build the agent architecture in this way:

There are a few things here: 
1. Environment: 
   All the files/attachments, files that the agent can create as well, ...

2. Framework / methodology
- Arbie's main goal is to create a property. To do so, it will first have to plan and define what information is necessary. So it has to get a clear picture of what information is actually needed. Then it should extract all information. If any information is missing, it has to collect the missing info in a notepad, and then write a nice/concise/clear email back to the property owner with some questions, to collect missing info. And it keeps doing so until satisfied.
- While doing this, Arbie should also do some research and validate local short-term rental regulations, and make sure the property meets the regulations and can actually be published or not.

We need
   
3. Tools
"edit_property(property_id, status, session_id, key, value, evidence) -> this can also create the property initially and responds with property ID", "send_email()", "read_file", "fetch_email", "regulation_researcher", and then some other tools probably (still TBD)

4. Sub Agents (also available as 'tools') (part of handoff in OpenAI Agent SDK)

- Research Agent: A sub agent that can research all kinds of things using web search (we use Tavily). For example, it can research and validate local short-term rental regulations based on property address (permit requirements, occupancy limits, tax obligations, registration deadlines). Cross-check property details against legal requirements and flag potential compliance issues. Generate checklists of required documentation and registration steps specific to each jurisdiction.

- 

Think about all this and tell me, whats the best way to approach it? Shall we start with user stories first? or something else?
It would be good if you research all the different tools that we want to use. And then we can start creating a high level plan. And then you could make the base structure. Let's use UV for the project.