# Arbie - User Stories

## Actors

- **Property Owner**: Person submitting a property for onboarding
- **Arbie**: The AI agent that processes submissions
- **Operations Team**: Arbio staff who may review flagged properties

---

## Epic 1: Property Submission

### US-1.1: Initial Property Submission
**As a** property owner
**I want to** send an email with my property documents and photos
**So that** I can start the onboarding process without filling out forms

**Acceptance Criteria:**
- Owner sends email to designated Arbie address (e.g., `onboard@arbie.arbio.com`)
- Email can contain: PDFs, images, Word docs, text in body
- Arbie acknowledges receipt within 5 minutes
- A new session is created linking owner to this submission

### US-1.2: Multiple Attachment Types
**As a** property owner
**I want to** attach various file types (PDF, JPG, PNG, DOCX, spreadsheets)
**So that** I can submit information in whatever format I have

**Acceptance Criteria:**
- Supported formats: PDF, JPG, PNG, HEIC, DOCX, XLSX, CSV, TXT
- Files are stored and linked to the session
- Unsupported formats trigger a polite note in acknowledgment

### US-1.3: Submission Acknowledgment
**As a** property owner
**I want to** receive confirmation that my submission was received
**So that** I know the process has started

**Acceptance Criteria:**
- Acknowledgment email sent within 5 minutes
- Includes session reference ID
- Sets expectation for next steps and timeline

---

## Epic 2: Data Extraction

### US-2.1: Automated Data Extraction
**As** Arbie
**I want to** extract structured data from unstructured documents
**So that** I can populate the property profile automatically

**Acceptance Criteria:**
- Extract text from PDFs (including scanned via OCR)
- Extract metadata and content from images
- Parse tables from spreadsheets
- Identify and extract: address, amenities, capacity, rules, etc.

### US-2.2: Photo Analysis
**As** Arbie
**I want to** analyze property photos
**So that** I can identify rooms, amenities, and validate property details

**Acceptance Criteria:**
- Identify room types (bedroom, bathroom, kitchen, etc.)
- Detect visible amenities (pool, parking, appliances)
- Count beds, bathrooms where visible
- Flag low-quality or inappropriate images

### US-2.3: Evidence Linking
**As** Arbie
**I want to** link each extracted data point to its source
**So that** humans can verify where information came from

**Acceptance Criteria:**
- Each property field stores source reference (file + location)
- Can trace any value back to original document/image
- Evidence is preserved even after edits

---

## Epic 3: Information Gaps

### US-3.1: Gap Detection
**As** Arbie
**I want to** identify missing required information
**So that** I can request it from the property owner

**Acceptance Criteria:**
- Compare extracted data against required fields schema
- Identify ambiguous or conflicting information
- Prioritize gaps by importance (blocking vs nice-to-have)

### US-3.2: Follow-up Email
**As** Arbie
**I want to** send a clear, concise follow-up email
**So that** the owner knows exactly what's still needed

**Acceptance Criteria:**
- Email lists specific missing items
- Groups related questions logically
- Uses friendly, professional tone
- Includes context ("You mentioned 3 bedrooms but photos show 4...")

### US-3.3: Process Follow-up Response
**As** Arbie
**I want to** process the owner's reply with additional info
**So that** I can update the property profile

**Acceptance Criteria:**
- Match reply to existing session via thread/reference
- Extract new information from reply
- Update property with new data
- Re-evaluate completeness

### US-3.4: Multiple Follow-up Rounds
**As** Arbie
**I want to** handle multiple back-and-forth exchanges
**So that** complex properties can be fully onboarded

**Acceptance Criteria:**
- Track conversation history in session
- Avoid asking for same info twice
- Escalate after 3+ rounds without resolution
- Set reasonable timeout (e.g., 7 days of no response)

---

## Epic 4: Compliance Research

### US-4.1: Regulatory Lookup
**As** Arbie
**I want to** research local short-term rental regulations
**So that** I can verify the property can be legally listed

**Acceptance Criteria:**
- Determine jurisdiction from property address
- Research permit requirements
- Identify occupancy limits
- Find tax obligations
- Note registration deadlines

### US-4.2: Compliance Checklist Generation
**As** Arbie
**I want to** generate a compliance checklist
**So that** the owner knows what's required in their jurisdiction

**Acceptance Criteria:**
- Checklist specific to property's location
- Includes required documents/permits
- Notes deadlines and renewal periods
- Links to official sources where available

### US-4.3: Compliance Flag
**As** Arbie
**I want to** flag potential compliance issues
**So that** problems are caught before listing

**Acceptance Criteria:**
- Flag if property appears to violate regulations
- Flag if required permits are missing
- Include explanation of the issue
- Suggest remediation steps

---

## Epic 5: Property Completion

### US-5.1: Completeness Check
**As** Arbie
**I want to** verify all required information is present
**So that** the property can move to validation

**Acceptance Criteria:**
- All required fields populated
- All compliance checks passed or acknowledged
- Minimum photo requirements met
- No unresolved ambiguities

### US-5.2: Property Summary Generation
**As** Arbie
**I want to** generate a comprehensive property summary PDF
**So that** the owner can review everything in one document

**Acceptance Criteria:**
- PDF includes all property details
- Photos included and organized by room
- Compliance status included
- Professional, branded layout

### US-5.3: Ready Notification
**As a** property owner
**I want to** receive notification when my property is ready
**So that** I can review and validate it

**Acceptance Criteria:**
- Email includes summary PDF attachment
- Email includes validation URL
- Clear instructions on next steps
- Deadline for validation (optional)

---

## Epic 6: Owner Validation

### US-6.1: Validation Portal Access
**As a** property owner
**I want to** access a web page to review my property
**So that** I can verify all information is correct

**Acceptance Criteria:**
- Secure, tokenized URL (no login required)
- Shows all property information
- Shows all uploaded photos
- Shows compliance status

### US-6.2: Edit Property Details
**As a** property owner
**I want to** edit incorrect information
**So that** the final listing is accurate

**Acceptance Criteria:**
- Inline editing of all fields
- Can add/remove/reorder photos
- Changes tracked with timestamp
- Original values preserved for audit

### US-6.3: Validate Property
**As a** property owner
**I want to** confirm the property information is correct
**So that** it can be published

**Acceptance Criteria:**
- Clear "Validate" action
- Requires explicit confirmation
- Records validation timestamp and IP
- Triggers downstream publishing flow

### US-6.4: Request Changes
**As a** property owner
**I want to** request changes I can't make myself
**So that** complex issues can be resolved

**Acceptance Criteria:**
- Free-text feedback field
- Creates new message in session
- Arbie processes and responds
- Loops back to follow-up flow if needed

---

## Epic 7: Session Management

### US-7.1: Session Timeline
**As a** property owner
**I want to** see the history of my onboarding
**So that** I understand what's happened

**Acceptance Criteria:**
- Chronological list of events
- Shows emails sent/received
- Shows extraction milestones
- Shows status changes

### US-7.2: Session Timeout Handling
**As** Arbie
**I want to** handle stale sessions appropriately
**So that** incomplete submissions don't hang forever

**Acceptance Criteria:**
- Send reminder after X days of inactivity
- Send final notice after Y days
- Archive session after Z days
- Owner can reactivate by replying

---

## Epic 8: Observability & Learning

### US-8.1: Trace Logging
**As** Arbie
**I want to** log all my decisions and actions
**So that** the system can be debugged and improved

**Acceptance Criteria:**
- Log each extraction with confidence scores
- Log each tool call and result
- Log reasoning for follow-up questions
- Structured format for analysis

### US-8.2: Pattern Learning
**As** Arbie
**I want to** learn from successful onboardings
**So that** future extractions improve over time

**Acceptance Criteria:**
- Track which extractions were correct (validated unchanged)
- Track which needed correction
- Feed into prompt improvement
- Bottom-up schema discovery from patterns

---

## Non-Functional Requirements

### NFR-1: Response Time
- Acknowledgment emails within 5 minutes
- Follow-up emails within 1 hour of processing
- Validation portal loads in < 3 seconds

### NFR-2: Security
- All emails encrypted in transit
- Stored files encrypted at rest
- Validation URLs expire after 30 days
- No PII in logs

### NFR-3: Scalability
- Handle 100+ concurrent sessions
- Process 1000+ emails per day
- Store 10GB+ of attachments per property

### NFR-4: Reliability
- 99.9% uptime for email ingestion
- No data loss on failures
- Graceful degradation if research APIs unavailable
