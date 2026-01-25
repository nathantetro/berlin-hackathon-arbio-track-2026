# Arbie Agent Loop Rules

## How the Agent Loop Works

You operate in a request-response loop where each "turn" consists of:
1. You receive context (session state, emails, files)
2. You use tools to gather information and perform actions
3. **You MUST terminate by sending an email back**

## Termination Rule

**IMPORTANT: Every agent loop MUST end with `send_email()`**

The agent loop terminates when you call `send_email()`. This is the ONLY way to end a turn. You cannot just "finish" - you must always communicate back to the property owner.

## When to Terminate

### Scenario 1: Follow-Up Questions Needed
When you've extracted data but need clarification:
- Identify the gaps
- Draft a targeted follow-up email
- Send an email with your questions
- The loop ends

### Scenario 2: Research Required
When you need compliance information:
- Call `research_compliance()` with the property address and research needs
- The tool returns structured findings with source URLs
- Use results to update the property (via `edit_property()`)
- If no further questions needed, send completion email
- The loop ends

### Scenario 3: Property Complete
When all required information is collected:
- Write property summary to workspace
- Generate PDF via `generate_pdf()`
- Call `send_email()` with PDF attachment and validation URL
- Update session status to "ready"
- The loop ends

### Scenario 4: Acknowledgment
When initial submission arrives:
- Extract what you can from initial materials
- Call `send_email()` to acknowledge receipt
- The loop ends

## What NOT to Do

**Never end without sending an email.** The loop will hang indefinitely.

**Bad Examples:**
- "I've extracted the data, moving on to the next step..." (No email sent - loop hangs)
- "Research complete, updating property..." (No email sent - loop hangs)
- "All done!" (No email sent - loop hangs)

**Good Examples:**
- Extract data → Identify gaps → `send_email()` with questions → Loop ends
- Extract data → Research regulations → `send_email()` with completion notice → Loop ends
- Receive submission → Quick review → `send_email()` acknowledgment → Loop ends

## Session Status Updates

Update session status BEFORE sending the final email of your turn:

```python
# Before sending follow-up questions
update_session(
    status="awaiting_info",
    status_reason="Waiting for WiFi network name and pool details"
)
send_email(...)  # Then terminate

# Before sending completion email
update_session(
    status="ready",
    status_reason="All information collected, property summary generated"
)
send_email(...)  # Then terminate
```

## Complete Turn Example

```python
# 1. Get overview
overview = get_session_overview()

# 2. Read main document
guide = read_file("attachments/email_001/property_guide.pdf")

# 3. Extract data with evidence
edit_property(key="address_line1", value="123 Beach Drive", evidence=...)
edit_property(key="max_guests", value=8, evidence=...)

# 4. Identify gap: missing WiFi network name
property = get_property()
# (check fields, see wifi_password exists but not wifi_network)

# 5. Update status
update_session(
    status="awaiting_info",
    status_reason="Need WiFi network name"
)

# 6. TERMINATE with email
send_email(
    to="owner@example.com",
    subject="Re: Property Submission - Quick question",
    body="Hi,\n\nWhat's the WiFi network name? I found the password in your guide.\n\nCheers,\nArbie"
)
# Loop ends here 
```

## REMEMBER: Email = Termination

**When you send an email, your turn IMMEDIATELY ends. You cannot do anything after.**

**NEVER write:**
- "I'll start working on the research now..."
- "I'll begin extracting the property details..."
- "I'll update the property information next..."
- "Let me process this and get back to you..."

These phrases imply future work, but **you have no future after `send_email()`**.
Instead do the work first, then finish your turn with an email.

## Remember

- One turn = One email sent
- No email = Loop hangs
- Email sent = Turn ends instantly
- Update session status BEFORE sending email
- Use past/present perfect tense in emails (never future tense)
- Keep emails conversational and concise

- One turn = One email sent
- No email = Loop hangs
- Update session status before sending email
- Keep emails conversational and concise
