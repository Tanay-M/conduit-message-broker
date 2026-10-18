import os
import sys
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def create_presentation(output_path):
    prs = pptx.Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color Palette
    BG_DARK = RGBColor(15, 23, 42)       # Slate 900 #0f172a
    CARD_BG = RGBColor(30, 41, 59)       # Slate 800 #1e293b
    CARD_BORDER = RGBColor(51, 65, 85)   # Slate 700 #334155
    ACCENT_CYAN = RGBColor(56, 189, 248) # Sky 400 #38bdf8
    ACCENT_BLUE = RGBColor(99, 102, 241) # Indigo 500 #6366f1
    ACCENT_GREEN = RGBColor(52, 211, 153)# Emerald 400 #34d399
    ACCENT_AMBER = RGBColor(251, 191, 36)# Amber 400 #fbbf24
    ACCENT_ROSE = RGBColor(251, 113, 133)# Rose 400 #fb7185
    TEXT_WHITE = RGBColor(248, 250, 252) # Slate 50 #f8fafc
    TEXT_MUTED = RGBColor(148, 163, 184) # Slate 400 #94a3b8
    CODE_BG = RGBColor(10, 15, 29)       # Deep Navy #0a0f1d

    def apply_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG_DARK
        bg.line.fill.background()
        return bg

    def add_header(slide, category_tag, title_text, subtitle_text=""):
        # Top banner with badge and title
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.1))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

        # Category Tag
        p_tag = tf.paragraphs[0]
        p_tag.text = category_tag.upper()
        p_tag.font.name = "Arial"
        p_tag.font.size = Pt(10)
        p_tag.font.bold = True
        p_tag.font.color.rgb = ACCENT_CYAN
        p_tag.space_after = Pt(2)

        # Title
        p_title = tf.add_paragraph()
        p_title.text = title_text
        p_title.font.name = "Arial"
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_WHITE

        # Subtitle
        if subtitle_text:
            p_sub = tf.add_paragraph()
            p_sub.text = subtitle_text
            p_sub.font.name = "Arial"
            p_sub.font.size = Pt(11)
            p_sub.font.color.rgb = TEXT_MUTED

    def add_card(slide, left, top, width, height, title="", title_color=ACCENT_CYAN, bg_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1.2)

        tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), height - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

        if title:
            p_head = tf.paragraphs[0]
            p_head.text = title
            p_head.font.name = "Arial"
            p_head.font.size = Pt(13)
            p_head.font.bold = True
            p_head.font.color.rgb = title_color
            p_head.space_after = Pt(6)

        return tf

    def add_bullet(tf, bold_prefix, text, font_size=10.5, color=TEXT_WHITE, space_after=5):
        p = tf.add_paragraph()
        p.space_after = Pt(space_after)
        
        run_bold = p.add_run()
        run_bold.text = bold_prefix + " " if bold_prefix else ""
        run_bold.font.name = "Arial"
        run_bold.font.size = Pt(font_size)
        run_bold.font.bold = True
        run_bold.font.color.rgb = ACCENT_CYAN if bold_prefix else color

        run_text = p.add_run()
        run_text.text = text
        run_text.font.name = "Arial"
        run_text.font.size = Pt(font_size)
        run_text.font.color.rgb = color

    def add_notes(slide, notes_text):
        notes_slide = slide.notes_slide
        text_frame = notes_slide.notes_text_frame
        text_frame.text = notes_text

    # ==========================================
    # SLIDE 1: TITLE SLIDE
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    apply_background(s1)

    # Accent decorative top bar
    bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.2), Inches(2.5), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT_CYAN
    bar.line.fill.background()

    # Title box
    tb = s1.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.733), Inches(3.2))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "CONDUIT"
    p0.font.name = "Arial"
    p0.font.size = Pt(48)
    p0.font.bold = True
    p0.font.color.rgb = TEXT_WHITE
    p0.space_after = Pt(4)

    p1 = tf.add_paragraph()
    p1.text = "A High-Throughput Message Broker Built on PostgreSQL Engine Primitives"
    p1.font.name = "Arial"
    p1.font.size = Pt(20)
    p1.font.bold = True
    p1.font.color.rgb = ACCENT_CYAN
    p1.space_after = Pt(12)

    p2 = tf.add_paragraph()
    p2.text = "DBMS Project Review 2: Database Implementation, Operations & Advanced Features (10 Marks)"
    p2.font.name = "Arial"
    p2.font.size = Pt(13)
    p2.font.color.rgb = TEXT_MUTED

    # Team Box
    card_tf = add_card(s1, Inches(0.8), Inches(4.8), Inches(11.733), Inches(1.8), "PROJECT DETAILS & TEAM 17", ACCENT_GREEN)
    add_bullet(card_tf, "Team Members:", "G Anirudh (24BDS0335)  ·  Tanay Mohta (24BDS0294)  ·  Dhyey Dhumasia (24BCE0529)", 11, TEXT_WHITE, 6)
    add_bullet(card_tf, "Architecture Thesis:", "The DBMS is not an accessory to the broker — the DBMS IS the broker. Messages are rows, producing is a transaction, consuming is SKIP LOCKED, and durability is PostgreSQL's WAL.", 11, TEXT_WHITE, 6)
    add_bullet(card_tf, "Technology Stack:", "PostgreSQL 16 · Procedural PL/pgSQL · Row-Level Security · FastAPI REST/SSE · Pure-Python Conduit SDK", 11, TEXT_WHITE, 0)

    add_notes(s1, 
        "Welcome professors and evaluators. This is Team 17 presenting Conduit for DBMS Project Review 2.\n"
        "Our team consists of G Anirudh, Tanay Mohta, and Dhyey Dhumasia.\n"
        "Our core thesis: rather than running a complex message broker alongside a database with dual-write synchronization issues, we prove that modern PostgreSQL provides all necessary primitives to function as an enterprise-grade message broker natively."
    )

    # ==========================================
    # SLIDE 2: REVIEW 1 PIVOT & ARCHITECTURE
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    apply_background(s2)
    add_header(s2, "Context & Architectural Evolution", "The Review 1 Pivot: Transition to Full RDBMS-Core Architecture", "Shifting message storage and concurrency entirely inside PostgreSQL 16")

    c1 = add_card(s2, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Review 1 (Initial Submission)", ACCENT_AMBER)
    add_bullet(c1, "Architecture:", "Hybrid custom data-plane + RDBMS metadata control plane.", 10.5, TEXT_WHITE, 8)
    add_bullet(c1, "Flaw Identified:", "PostgreSQL only held administrative metadata (6 tables: USER, TOPIC, etc.). Messages never touched the relational schema.", 10.5, TEXT_WHITE, 8)
    add_bullet(c1, "Perception:", "'A distributed systems project with a DBMS panel bolted on.' Core course concepts (transactions, locks, joins) were missing from the hot path.", 10.5, TEXT_WHITE, 8)
    add_bullet(c1, "Recovery:", "Hand-rolled file-based WAL and custom in-memory offset indexes.", 10.5, TEXT_WHITE, 8)
    add_bullet(c1, "Verdict:", "Failed to showcase the full power of advanced database mechanisms.", 10.5, TEXT_WHITE, 0)

    c2 = add_card(s2, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Review 2 (Current Implementation)", ACCENT_GREEN)
    add_bullet(c2, "Full RDBMS Core:", "PostgreSQL 16 serves and stores messages directly as partitioned relational rows.", 10.5, TEXT_WHITE, 8)
    add_bullet(c2, "Rubric Saturation:", "Every course concept is on the hot path: Transactions, Procedural PL/pgSQL, Triggers, RLS, Partitioning, and BRIN Indexing.", 10.5, TEXT_WHITE, 8)
    add_bullet(c2, "Prior Art Justification:", "Builds upon proven industrial architectures: pgmq, Message DB, Graphile-Worker, and Quartz JDBC store.", 10.5, TEXT_WHITE, 8)
    add_bullet(c2, "ACID Durability:", "PostgreSQL's Write-Ahead Log (WAL) completely replaces hand-rolled logging with proven crash durability.", 10.5, TEXT_WHITE, 8)
    add_bullet(c2, "Concurrency Control:", "Engine-level SELECT ... FOR UPDATE SKIP LOCKED provides lock-free queue draining without duplicates.", 10.5, TEXT_WHITE, 0)

    add_notes(s2,
        "In Review 1, our evaluator noted that the database was relegated to an admin panel while messages were handled in custom files.\n"
        "For Review 2, we performed a 100% pivot to an RDBMS-core architecture.\n"
        "Messages are now relational rows; producing is an ACID transaction; consuming uses SKIP LOCKED; durability is guaranteed by PostgreSQL's WAL."
    )

    # ==========================================
    # SLIDE 3: CRITERION 1 - RELATIONAL SCHEMA (15 TABLES)
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    apply_background(s3)
    add_header(s3, "Criterion 1: Database Implementation (10 Marks)", "Relational Schema Architecture: 15 Tables in 3NF / BCNF", "Fully normalized schema categorised into three cohesive functional tiers")

    t1 = add_card(s3, Inches(0.8), Inches(1.6), Inches(3.7), Inches(5.2), "1. Identity & Security (4 Tables)", ACCENT_CYAN)
    add_bullet(t1, "ROLE:", "role_id (PK), role_name (admin, operator, producer, consumer, viewer). Normalized out of user.", 9.5, TEXT_WHITE, 6)
    add_bullet(t1, "APP_USER:", "user_id (BIGSERIAL PK), username, email, role_id (FK), status (active, suspended).", 9.5, TEXT_WHITE, 6)
    add_bullet(t1, "APPLICATION:", "app_id (PK), app_name, api_key (UUID), owner_user_id (FK), app_type (producer, consumer, both), status.", 9.5, TEXT_WHITE, 6)
    add_bullet(t1, "ACCESS:", "access_id (PK), user_id (FK), topic_id (FK), access_type (produce, consume, admin). Unique ACL triple.", 9.5, TEXT_WHITE, 0)

    t2 = add_card(s3, Inches(4.7), Inches(1.6), Inches(3.9), Inches(5.2), "2. Messaging Domain (5 Tables)", ACCENT_BLUE)
    add_bullet(t2, "TOPIC:", "topic_id (PK), topic_name, retention_days, max_message_bytes, status, created_by (FK).", 9.5, TEXT_WHITE, 6)
    add_bullet(t2, "PARTITION:", "partition_id (PK), topic_id (FK), partition_number, next_offset (monotonic counter under row lock).", 9.5, TEXT_WHITE, 6)
    add_bullet(t2, "SCHEMA_VERSION:", "schema_id (PK), topic_id (FK), version, format, definition (JSONB validation contract).", 9.5, TEXT_WHITE, 6)
    add_bullet(t2, "MESSAGE:", "The core: created_at, topic_id, partition_id, msg_offset, payload (JSONB), status, attempts. Monthly partitioned.", 9.5, TEXT_WHITE, 6)
    add_bullet(t2, "PRODUCER_SEQUENCE:", "Composite PK (producer_app_id, producer_seq). Dedicated outbox ledger for exact deduplication.", 9.5, TEXT_WHITE, 0)

    t3 = add_card(s3, Inches(8.8), Inches(1.6), Inches(3.733), Inches(5.2), "3. Consumption & Ops (6 Tables)", ACCENT_GREEN)
    add_bullet(t3, "CONSUMER_GROUP:", "group_id (PK), group_name, max_delivery_attempts (1..10), status (active, paused).", 9.5, TEXT_WHITE, 6)
    add_bullet(t3, "GROUP_SUBSCRIPTION:", "Composite PK (group_id, topic_id). Resolves M:N group-to-topic mapping cleanly.", 9.5, TEXT_WHITE, 6)
    add_bullet(t3, "GROUP_OFFSET:", "Composite PK (group_id, partition_id), committed_offset. Protected by monotonic trigger.", 9.5, TEXT_WHITE, 6)
    add_bullet(t3, "DEAD_LETTER_MESSAGE:", "dlq_id (PK), original_topic_id, msg_key, payload, failure_reason, attempts, status.", 9.5, TEXT_WHITE, 6)
    add_bullet(t3, "AUDIT_LOG:", "log_id (PK), user_id, app_id, topic_id, event_type, status, details (JSONB). BRIN-indexed.", 9.5, TEXT_WHITE, 6)
    add_bullet(t3, "BROKER_CONFIG:", "config_id (PK), config_key, config_value, updated_at.", 9.5, TEXT_WHITE, 0)

    add_notes(s3,
        "Here is our complete 15-table relational schema.\n"
        "We have zero denormalization anomalies. All tables are in BCNF/3NF.\n"
        "Notice the separation of concern: Identity, Core Messaging, and Consumption/Ops.\n"
        "Important detail: PRODUCER_SEQUENCE is separated from MESSAGE because in PostgreSQL, unique constraints on a partitioned table must include the partition key."
    )

    # ==========================================
    # SLIDE 4: CRITERION 1 - CONSTRAINTS & DATA VALIDATION (157 CONSTRAINTS)
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    apply_background(s4)
    add_header(s4, "Criterion 1: Database Implementation (10 Marks)", "Data Integrity: 157 Engine-Level Constraints & JSON Validation", "Guaranteed correctness at the storage layer without relying on external application code")

    c1 = add_card(s4, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Integrity Constraints Enforced", ACCENT_CYAN)
    add_bullet(c1, "157 Total Constraints:", "Verified via PostgreSQL's information_schema.table_constraints catalog.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Composite Primary Keys:", "Enforced across junction and ledger tables: (group_id, topic_id), (group_id, partition_id), (producer_app_id, producer_seq).", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Foreign Key Cascades & Restricts:", "Deliberate ON DELETE policies: CASCADE on memberships; RESTRICT on topics/apps to prevent orphaned message data; SET NULL on audit actors.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Domain CHECK Constraints:", "Enforces valid states: status IN ('pending', 'claimed', 'delivered', 'dead'); attempts BETWEEN 1 AND 10; retention_days BETWEEN 1 AND 3650.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Strict UNIQUE Constraints:", "Protects natural keys: app_name, topic_name, username, email, API key UUIDs, and ACL triples (user_id, topic_id, access_type).", 10, TEXT_WHITE, 0)

    c2 = add_card(s4, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Dynamic JSON Schema Validation", ACCENT_BLUE)
    add_bullet(c2, "JSONB Message Contracts:", "Topics can enforce optional JSON contracts stored in schema_version.definition.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "In-Database Validator Function:", "fn_validate_schema(payload JSONB, schema JSONB) executes inside PL/pgSQL on the produce hot path.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Required Field Enforcement:", "Extracts schema['required'] using jsonb_array_elements_text() and verifies payload ? key.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Immediate Rejection:", "Invalid payloads raise custom exception CDT04 (Schema Validation Failed), rolling back the insert immediately.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Zero Bad Data:", "Malicious or malformed payloads never pollute the storage layer.", 10, TEXT_WHITE, 0)

    add_notes(s4,
        "A critical evaluation criteria is constraints and validation. Conduit enforces 157 constraints directly in PostgreSQL.\n"
        "This includes composite primary keys, intentional foreign key cascading, and domain check constraints.\n"
        "Furthermore, we implement schema validation directly in SQL functions so messages violate topic contracts get rejected at the database level."
    )

    # ==========================================
    # SLIDE 5: CRITERION 1 - TABLE PARTITIONING & PHYSICAL DESIGN
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    apply_background(s5)
    add_header(s5, "Criterion 1: Database Implementation (10 Marks)", "Physical Database Design: Monthly Range Partitioning", "Partition pruning, storage lifecycle management, and PG16 partitioned FK integrity")

    c1 = add_card(s5, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Partitioning Scheme (MESSAGE Table)", ACCENT_AMBER)
    add_bullet(c1, "Partition by Range:", "PARTITION BY RANGE (created_at) splits message storage across monthly boundary tables.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Partition Relations:", "message_2026_09 through message_2027_03 + message_default catch-all partition.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Composite Partition PK:", "PRIMARY KEY (created_at, topic_id, partition_id, msg_offset) strictly satisfies PostgreSQL's partition key inclusion rule.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Automated Management:", "create_monthly_partition(target_date) dynamically attaches future partitions before boundary rollovers.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Partition Pruning:", "Queries filtering by time range prune unneeded physical tables, reading only active disk blocks.", 10, TEXT_WHITE, 0)

    c2 = add_card(s5, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "PG16 Milestone & Retention Drops", ACCENT_GREEN)
    add_bullet(c2, "PostgreSQL 16 FK Milestone:", "Historically, foreign keys referencing partitioned tables were restricted. In PG16, Conduit successfully enforces 4 real foreign keys on MESSAGE directly.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Split Retention Architecture:", "A critical design defense: per-topic retention vs global physical partition drops.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Per-Topic Purge (DELETE):", "purge_retention(topic_id) deletes rows older than topic.retention_days without affecting other topics.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Global Drop Floor (DETACH):", "drop_old_partitions(keep_days) performs zero-downtime ALTER TABLE DETACH PARTITION + DROP TABLE for months older than the retention floor.", 10, TEXT_WHITE, 0)

    add_notes(s5,
        "Here is our physical partitioning design. The MESSAGE table is partitioned by range on created_at.\n"
        "This allows partition pruning during queries and instant truncation of old months without table-level vacuums.\n"
        "We also highlight a key PG16 finding: foreign keys from partitioned tables work natively, providing true referential integrity."
    )

    # ==========================================
    # SLIDE 6: CRITERION 2 - DATA INSERTION & PRODUCE LIFECYCLE
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    apply_background(s6)
    add_header(s6, "Criterion 2: Data Insertion & Management (10 Marks)", "The Produce Transaction: 5-Step Atomic Ingestion Pipeline", "Comprehensive data insertion workflow inside the produce() stored procedure")

    steps = [
        ("Step 1: Advisory Lock", "pg_advisory_xact_lock(app_id, seq) serializes concurrent retries from the same client without table locking.", ACCENT_CYAN),
        ("Step 2: Idempotency Check", "Queries producer_sequence. If (app, seq) exists, returns original location (is_duplicate=true). Zero double-inserts.", ACCENT_BLUE),
        ("Step 3: Hash Routing", "Key-based routing: partition = abs(hashtext(msg_key)) % partition_count. Round-robin for unkeyed messages.", ACCENT_GREEN),
        ("Step 4: Offset Allocation", "SELECT next_offset FROM partition FOR UPDATE. Monotonically increments next_offset (gap-free per partition).", ACCENT_AMBER),
        ("Step 5: Insert & Notify", "Inserts into message and producer_sequence. Trigger fires pg_notify('conduit_events', ...) for real-time SSE.", ACCENT_ROSE)
    ]

    top_pos = 1.6
    for i, (title, desc, col) in enumerate(steps):
        c = add_card(s6, Inches(0.8), Inches(top_pos), Inches(11.733), Inches(0.95), f"{title}", col)
        add_bullet(c, "", desc, 10.5, TEXT_WHITE, 0)
        top_pos += 1.05

    add_notes(s6,
        "Criterion 2 covers data insertion and management. In Conduit, data insertion is not a blind INSERT.\n"
        "The produce() procedure executes a 5-step atomic pipeline:\n"
        "Advisory lock -> Idempotency check -> Hash routing -> Monotonic row-locked offset assignment -> Insert & Notify."
    )

    # ==========================================
    # SLIDE 7: CRITERION 2 - DATA MANAGEMENT & SEED DATASET
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    apply_background(s7)
    add_header(s7, "Criterion 2: Data Insertion & Management (10 Marks)", "Dataset Seeding, Dead-Lettering & Housekeeping Procedures", "Realistic production dataset and autonomous message lifecycle operations")

    c1 = add_card(s7, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "The 2,000-Message Seed Dataset", ACCENT_GREEN)
    add_bullet(c1, "Production Simulation:", "50_seed.sql provisions an exact enterprise message distribution across 4 topics and 6 applications.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Status Breakdown:", "1,580 Delivered (79%), 390 Pending (19.5%), 29 Claimed (1.45%), 1 Dead letter message.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Application Ecosystem:", "checkout-service (producer), payment-service (both), fraud-detector (both), email-service (consumer), analytics-worker.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Subscription Matrix:", "6 Consumer group subscriptions (billing-workers, payment-processors, email-workers, fraud-team, analytics-team).", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Deterministic Seeding:", "Gated via CONDUIT_SEED=true; reproducible across all teammate machines.", 10, TEXT_WHITE, 0)

    c2 = add_card(s7, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Poison Pills & Housekeeping Procedures", ACCENT_ROSE)
    add_bullet(c2, "Dead Letter Queue (DLQ):", "Messages failing delivery >= max_delivery_attempts (default 3) are snapped into dead_letter_message and marked dead.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Requeue Procedure:", "requeue_dlq(dlq_id, app, topic) re-inserts dead messages as a fresh produce with an incremented sequence, setting dlq.status = 'requeued'.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Crashed Consumer Reaper:", "reap_expired_claims() scans WHERE status='claimed' AND visible_at <= now(). Restores un-acked claims to 'pending' or routes to DLQ.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Housekeeping Procedures:", "purge_retention(), drop_old_partitions(), and refresh_dashboard() provide scheduled maintenance.", 10, TEXT_WHITE, 0)

    add_notes(s7,
        "For testing and demonstration, we created a 2,000-message production dataset exhibiting all realistic states.\n"
        "We also manage the full lifecycle: poison messages that fail 3 times are captured in the Dead Letter Queue, and our reaper procedure automatically reclaims messages from crashed consumers."
    )

    # ==========================================
    # SLIDE 8: CRITERION 3 - DATABASE OPERATIONS (QUERIES & FILTERING)
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    apply_background(s8)
    add_header(s8, "Criterion 3: Database Operations (10 Marks)", "Operational Queries: Non-Blocking Consumption via SKIP LOCKED", "Executing high-concurrency queue drainage without lock contention or duplicate reads")

    c1 = add_card(s8, Inches(0.8), Inches(1.6), Inches(6.0), Inches(5.2), "The Hot-Path Consume Query", ACCENT_CYAN)
    add_bullet(c1, "Core SQL Operation:", "Executed inside consume(group_id, topic_id, batch_size, timeout):", 10, TEXT_WHITE, 6)
    
    code_text = (
        "SELECT created_at, partition_id, msg_offset,\n"
        "       payload, attempts\n"
        "FROM message\n"
        "WHERE topic_id = p_topic_id\n"
        "  AND status = 'pending'\n"
        "  AND (visible_at IS NULL OR visible_at <= now())\n"
        "ORDER BY msg_offset ASC\n"
        "LIMIT p_batch_size\n"
        "FOR UPDATE SKIP LOCKED;"
    )
    add_bullet(c1, "SQL Definition:", code_text, 9.5, ACCENT_AMBER, 8)
    add_bullet(c1, "FOR UPDATE:", "Acquires exclusive row-level locks on selected message records.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "SKIP LOCKED:", "The key engine primitive! Skips already-locked rows instead of waiting. Multiple consumer instances drain simultaneously with ZERO contention.", 10, TEXT_WHITE, 0)

    c2 = add_card(s8, Inches(7.1), Inches(1.6), Inches(5.433), Inches(5.2), "Query Execution & Filtering", ACCENT_GREEN)
    add_bullet(c2, "Dynamic Filtering Clauses:", "Filters on composite keys (topic_id, partition_id), discrete states (status='pending'), and temporal bounds (visible_at <= now()).", 10, TEXT_WHITE, 8)
    add_bullet(c2, "Partial Index Scanning:", "The planner scans idx_message_pending. Because 'delivered' messages are excluded, the scanned index is miniscule.", 10, TEXT_WHITE, 8)
    add_bullet(c2, "Concurrency Proof (Demo 02):", "3 racing worker processes consuming concurrently from the same partition: 12 messages claimed, 12 delivered, EXACTLY ZERO duplicates.", 10, TEXT_WHITE, 8)
    add_bullet(c2, "LockRows Plan Node:", "EXPLAIN ANALYZE confirms execution plan: LockRows -> Limit -> Bitmap Index Scan.", 10, TEXT_WHITE, 0)

    add_notes(s8,
        "Criterion 3 covers operational queries. The heart of Conduit is our non-blocking consume query.\n"
        "Traditional database queues suffer from lock waits. By utilizing SELECT ... FOR UPDATE SKIP LOCKED, multiple workers can pull batches concurrently without waiting on each other.\n"
        "In our concurrency race benchmark, 5 workers drained 5,000 messages with exactly zero duplicate deliveries."
    )

    # ==========================================
    # SLIDE 9: CRITERION 3 - RELATIONAL JOINS & AGGREGATIONS
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    apply_background(s9)
    add_header(s9, "Criterion 3: Database Operations (10 Marks)", "Complex Relational Joins, FILTER Aggregations & Window Functions", "Multi-table relational operations powering operational observability")

    c1 = add_card(s9, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Multi-Table Joins & Derived State", ACCENT_BLUE)
    add_bullet(c1, "v_consumer_lag View (4-Table Join):", "Joins consumer_group cg JOIN group_subscription gs ON cg.group_id = gs.group_id JOIN partition p ON gs.topic_id = p.topic_id JOIN group_offset go ON go.group_id = cg.group_id AND go.partition_id = p.partition_id JOIN topic t ON p.topic_id = t.topic_id.", 9.5, TEXT_WHITE, 8)
    add_bullet(c1, "Deterministic Lag Calculation:", "Lag is not an arbitrary broker memory metric; it is calculated deterministically: lag = p.next_offset - go.committed_offset.", 10, TEXT_WHITE, 8)
    add_bullet(c1, "v_audit_recent View:", "Performs multi-table outer joins across audit_log, app_user, application, and topic to resolve UUIDs and IDs into human-readable actor trails.", 10, TEXT_WHITE, 0)

    c2 = add_card(s9, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "FILTER Aggregations & Window Functions", ACCENT_GREEN)
    add_bullet(c2, "Single-Pass FILTER Aggregates (v_topic_stats):", "Avoids multiple table scans using PostgreSQL's FILTER syntax:", 10, TEXT_WHITE, 6)
    code_filter = (
        "SELECT t.topic_name,\n"
        "  count(*) FILTER (WHERE m.status = 'pending') AS pending,\n"
        "  count(*) FILTER (WHERE m.status = 'claimed') AS claimed,\n"
        "  count(*) FILTER (WHERE m.status = 'delivered') AS delivered,\n"
        "  count(*) FILTER (WHERE m.status = 'dead') AS dead\n"
        "FROM topic t LEFT JOIN message m ON t.topic_id = m.topic_id\n"
        "GROUP BY t.topic_name;"
    )
    add_bullet(c2, "", code_filter, 9, ACCENT_AMBER, 8)
    add_bullet(c2, "Window Functions (v_throughput_by_minute):", "Uses date_trunc('minute', created_at) and SUM(count(*)) OVER (ORDER BY minute) to compute historical velocity and running totals.", 10, TEXT_WHITE, 0)

    add_notes(s9,
        "In Criterion 3, we demonstrate advanced joins and aggregations.\n"
        "Our consumer lag view joins 4 relational entities to compute lag on the fly.\n"
        "Our topic stats view uses single-pass FILTER aggregations, and throughput metrics leverage SQL window functions for running totals."
    )

    # ==========================================
    # SLIDE 10: CRITERION 4 - ADVANCED FEATURES: PROCEDURES & TXNS
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    apply_background(s10)
    add_header(s10, "Criterion 4: Advanced Database Features (10 Marks)", "Stored Procedures & Atomic Multi-Table Transactions", "Encapsulating the entire message broker data-plane inside PL/pgSQL routines")

    c1 = add_card(s10, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Complete Procedural Surface (10_functions.sql)", ACCENT_CYAN)
    add_bullet(c1, "produce() / produce_batch():", "Atomic ingestion, deduplication, schema validation, and offset assignment.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "consume():", "Non-blocking batch claim via SELECT ... FOR UPDATE SKIP LOCKED.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "ack():", "The exactly-once guarantee! Atomically flips status='delivered' AND advances group_offset.committed_offset in ONE single transaction.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "nack():", "Increments attempts counter; transitions to DLQ if max attempts reached.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "reap_expired_claims():", "Background recovery for crashed consumers.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "requeue_dlq():", "Restores dead messages into circulation.", 10, TEXT_WHITE, 0)

    c2 = add_card(s10, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Custom SQLSTATE Exception Hierarchy", ACCENT_AMBER)
    add_bullet(c2, "Defensive Exception Architecture:", "Conduit defines custom SQLSTATE error codes (CDT01-CDT21) mapped to HTTP errors in the API layer:", 10, TEXT_WHITE, 7)
    add_bullet(c2, "CDT01 / CDT02:", "Unknown or inactive topic.", 10, TEXT_WHITE, 5)
    add_bullet(c2, "CDT04 / CDT05:", "Schema validation failed / Message exceeds max_bytes.", 10, TEXT_WHITE, 5)
    add_bullet(c2, "CDT07 / CDT08:", "Unknown group / Group not subscribed to topic.", 10, TEXT_WHITE, 5)
    add_bullet(c2, "CDT17 / CDT18:", "ACL produce permission denied / Consume permission denied.", 10, TEXT_WHITE, 5)
    add_bullet(c2, "CDT19:", "Monotonic committed offset regression attempt rejected.", 10, TEXT_WHITE, 5)
    add_bullet(c2, "CDT20 / CDT21:", "Unauthorized application type / User account suspended.", 10, TEXT_WHITE, 0)

    add_notes(s10,
        "Criterion 4 is our strongest area: Advanced Database Features.\n"
        "We have implemented the complete broker business logic in stored procedures in 10_functions.sql.\n"
        "Notice the ack() procedure: it updates message status and commits the group offset in a single ACID transaction.\n"
        "We also defined a complete custom SQLSTATE hierarchy from CDT01 to CDT21."
    )

    # ==========================================
    # SLIDE 11: CRITERION 4 - ACTIVE DATABASE TRIGGERS (15 TRIGGERS)
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    apply_background(s11)
    add_header(s11, "Criterion 4: Advanced Database Features (10 Marks)", "Active Database Architecture: 15 Automated Triggers", "Autonomous audit trails, ACL security enforcement, and event notification")

    c1 = add_card(s11, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Security & Invariant Triggers (20_triggers.sql)", ACCENT_ROSE)
    add_bullet(c1, "1. ACL Enforcement Trigger (trg_acl_produce_check):", "BEFORE INSERT ON message: verifies the app owner holds produce access and status='active'. Raises CDT17/CDT21 on violation.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "2. Consume Authorization Trigger:", "BEFORE UPDATE ON message: verifies claiming consumer group holds consume permission before status flips to 'claimed'.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "3. Monotonic Offset Guard (trg_group_offset_monotonic):", "BEFORE UPDATE ON group_offset: enforces NEW.committed_offset >= OLD.committed_offset. Aborts regressions with CDT19.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "4. Updated_At Auto-Stamp:", "BEFORE UPDATE ON broker_config: automatically stamps current_timestamp, preventing forged update dates.", 10, TEXT_WHITE, 0)

    c2 = add_card(s11, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Audit & Real-Time Notification Triggers", ACCENT_GREEN)
    add_bullet(c2, "5. Immutable Audit Triggers (Terminal Events Only):", "Fires AFTER INSERT/UPDATE to record PRODUCE, DELIVERED, DLQ, and ACL changes into audit_log. Bypassing audit is physically impossible.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "6. Auth Failure Persistence Pattern:", "Because an aborted transaction rolls back trigger inserts, triggers raise clean exceptions; callers invoke log_auth_failure() to persist the failed attempt.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "7. Inter-Process NOTIFY Trigger (trg_message_notify):", "AFTER INSERT ON message: fires pg_notify('conduit_events', ...). Asynchronous listeners receive event JSON instantly without polling.", 10, TEXT_WHITE, 0)

    add_notes(s11,
        "We have 15 triggers actively operating across the database.\n"
        "They enforce invariants that application software cannot bypass: ACL checks, account suspension checks, monotonic offset regression guards, immutable audit logs, and real-time NOTIFY signaling."
    )

    # ==========================================
    # SLIDE 12: CRITERION 4 - ROW-LEVEL SECURITY (RLS)
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    apply_background(s12)
    add_header(s12, "Criterion 4: Advanced Database Features (10 Marks)", "Multi-Tenant Isolation via Native Row-Level Security (RLS)", "Engine-level access control: unauthorized apps cannot see rows even via raw SELECT")

    c1 = add_card(s12, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "RLS Architecture (30_rls.sql)", ACCENT_CYAN)
    add_bullet(c1, "Dedicated Role (conduit_app):", "PostgreSQL superusers bypass RLS by design. We provisioned the non-superuser conduit_app role for hot-path application connections.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Session GUC Context:", "FastAPI sets the verified identity per transaction using SET LOCAL app.user_id = '<user_id>'.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Default-Deny Policy:", "If app.user_id is unset or invalid, RLS defaults to zero visibility (empty result set).", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Selective Table Scope:", "RLS is enabled on MESSAGE and DEAD_LETTER_MESSAGE, maintaining maximum performance while securing message contents.", 10, TEXT_WHITE, 0)

    c2 = add_card(s12, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "5 Concrete RLS Policies Enforced", ACCENT_BLUE)
    add_bullet(c2, "Policy 1 (SELECT on message):", "USING (fn_can_access_topic(topic_id, 'consume') OR fn_can_access_topic(topic_id, 'produce') OR fn_is_admin()).", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Policy 2 (INSERT on message):", "WITH CHECK (fn_can_access_topic(topic_id, 'produce') OR fn_is_admin()).", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Policy 3 (UPDATE on message):", "USING (fn_can_access_topic(topic_id, 'consume') OR fn_is_admin()).", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Policy 4 & 5 (DLQ Read/Write):", "Scoped to users holding consumer permissions on the original topic.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Security Invoker Views:", "All analytical views are created with security_invoker = true, forcing views to obey the caller's RLS permissions.", 10, TEXT_WHITE, 0)

    add_notes(s12,
        "Another advanced feature is native Row-Level Security (RLS).\n"
        "We created a dedicated conduit_app role and set session variables per connection.\n"
        "If Bob has access to Topic A but not Topic B, even if he executes 'SELECT * FROM message', PostgreSQL physically hides Topic B rows from his result set at the storage engine level."
    )

    # ==========================================
    # SLIDE 13: CRITERION 4 - ADVANCED INDEXING STRATEGIES
    # ==========================================
    s13 = prs.slides.add_slide(blank_layout)
    apply_background(s13)
    add_header(s13, "Criterion 4: Advanced Database Features (10 Marks)", "Engine Optimization: Partial Indexes, BRIN & EXPLAIN Proofs", "Strategic indexing tailored to message queue lifecycle and append-only workloads")

    c1 = add_card(s13, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Strategic Indexing Hierarchy", ACCENT_AMBER)
    add_bullet(c1, "Partial Index (idx_message_pending):", "CREATE INDEX ... ON message(topic_id, partition_id, msg_offset) WHERE status = 'pending'. Indexes only unconsumed messages. Index remains tiny even with 10M delivered rows.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Partial Index (idx_message_claimed_visible_at):", "WHERE status = 'claimed'. Backs the reaper procedure to find expired claims instantly without scanning active messages.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "BRIN Index (Block Range Index):", "ON message(created_at) and audit_log(event_timestamp). Stores min/max per block range. 99% smaller footprint than B-Tree for time-ordered logs.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Composite PK Index:", "ON producer_sequence(producer_app_id, producer_seq) for instantaneous O(1) deduplication lookups.", 10, TEXT_WHITE, 0)

    c2 = add_card(s13, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "EXPLAIN at 30,000-Message Scale", ACCENT_GREEN)
    add_bullet(c2, "The Milestone 2 vs 8 Finding:", "At demo scale (<200 rows), the PostgreSQL planner correctly chooses a sequential scan over index scans (cheaper disk I/O).", 10, TEXT_WHITE, 7)
    add_bullet(c2, "The 30k Scale Proof (explain_at_scale.py):", "With 30,000 total messages and 100 pending, EXPLAIN (ANALYZE, BUFFERS) proves the planner shifts 100% to Bitmap Index Scan using idx_message_pending.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Execution Speed:", "1.9 ms execution time across 30,000 rows with ZERO sequential scans.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Dead-TID Insight:", "Directly captures autovacuum dynamics: bitmap scan rechecks live vs dead index entries, proving deep course understanding.", 10, TEXT_WHITE, 0)

    add_notes(s13,
        "We also excelled in indexing strategies.\n"
        "We use partial indexes for the pending queue, BRIN indexes for append-only logs, and composite B-Trees for offsets.\n"
        "In our Milestone 8 benchmarks, we ran EXPLAIN ANALYZE on 30,000 rows, proving that PostgreSQL uses our partial index and finishes in 1.9 ms without scanning delivered rows."
    )

    # ==========================================
    # SLIDE 14: CRITERION 4 - MATERIALIZED VIEWS & WAL DURABILITY
    # ==========================================
    s14 = prs.slides.add_slide(blank_layout)
    apply_background(s14)
    add_header(s14, "Criterion 4: Advanced Database Features (10 Marks)", "Materialized Views & WAL Crash Recovery Verification", "Non-blocking reporting aggregation and empirical durability testing")

    c1 = add_card(s14, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Materialized View (mv_topic_stats)", ACCENT_CYAN)
    add_bullet(c1, "CQRS Analytical Decoupling:", "Aggregating millions of messages for dashboard statistics creates read lock contention. mv_topic_stats caches precomputed aggregates.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Non-Blocking Concurrent Refresh:", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_topic_stats. Backed by unique index on topic_name.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Zero Read Blocking:", "Concurrent refresh allows background updates while readers continue reading cached data without table locks.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Automated Refresh Function:", "refresh_dashboard() encapsulates maintenance; administrative callers trigger it via API or dashboard button.", 10, TEXT_WHITE, 0)

    c2 = add_card(s14, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Durability & WAL Crash Recovery (Demo 08)", ACCENT_AMBER)
    add_bullet(c2, "Write-Ahead Logging (WAL):", "Durability is guaranteed by PostgreSQL's native fsync-backed WAL, eliminating hand-rolled log vulnerabilities.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "The Kill -9 Crash Test (08_wal_recovery.ps1):", "1. Ingests 100 acknowledged messages.\n2. Executes docker kill -s 9 conduit-db (hard ungraceful crash).\n3. Re-spins the PostgreSQL container.\n4. Database enters automated crash recovery mode and replays the WAL.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "Empirical Durability Result:", "All 100 acknowledged messages and committed offsets survive intact. In-flight uncommitted transactions vanish cleanly. ZERO data corruption.", 10, TEXT_WHITE, 0)

    add_notes(s14,
        "To support dashboard reads without locking operational tables, we deployed a materialized view refreshed concurrently.\n"
        "For durability, we ran a destructive recovery test: we killed PostgreSQL with SIGKILL (kill -9) during active operations.\n"
        "Upon reboot, PostgreSQL replayed its Write-Ahead Log, successfully recovering every committed message with zero data loss."
    )

    # ==========================================
    # SLIDE 15: EMPIRICAL BENCHMARKS & DEFENSE NUMBERS
    # ==========================================
    s15 = prs.slides.add_slide(blank_layout)
    apply_background(s15)
    add_header(s15, "Defense & Empirical Evaluation", "Production Benchmarks: Throughput, Concurrency & The Price of Guarantees", "Hard numbers measured on the system demonstrating scalability and trade-offs")

    c1 = add_card(s15, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Throughput & Scaling Metrics", ACCENT_GREEN)
    add_bullet(c1, "Produce Throughput:", "495 msg/s (batch=1) -> 1,521 msg/s (batch=10) -> 2,562 msg/s (batch=1000). Batching yields a 5x to 15x scaling curve.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Contention Resilience:", "4 concurrent producers contending on 2 partitions saw only a 7% throughput penalty (2,085 msg/s). Advisory locks serialize gracefully.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Consume Throughput:", "Up to 3,379 msg/s across 5 workers.", 10, TEXT_WHITE, 7)
    add_bullet(c1, "Zero-Duplicate Drain:", "5 concurrent workers draining 5,000 messages achieved 100% disjoint claims via SKIP LOCKED.", 10, TEXT_WHITE, 0)

    c2 = add_card(s15, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "The 'Price of Guarantees' Defense", ACCENT_ROSE)
    add_bullet(c2, "Benchmark Tiers (bench_overhead.py):", "Evaluates what ACID and security guarantees cost compared to raw storage:", 10, TEXT_WHITE, 7)
    add_bullet(c2, "1. Bare INSERT (No Guarantees):", "106,183 msg/s (Baseline: 1.0x).", 10, TEXT_WHITE, 5)
    add_bullet(c2, "2. produce() as Admin:", "3,291 msg/s (32.3x overhead): Buys idempotency ledger, advisory locks, monotonic gap-free offsets, schema validation, audit triggers & NOTIFY.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "3. produce() as App (+RLS):", "2,454 msg/s (43.3x overhead): RLS policy checks add ~34% overhead over the admin path.", 10, TEXT_WHITE, 7)
    add_bullet(c2, "The Defense Conclusion:", "A bare insert is 32x faster, but Conduit buys SQS/Kafka-grade transactional correctness and multi-tenant isolation on commodity PostgreSQL.", 10, TEXT_WHITE, 0)

    add_notes(s15,
        "Here are our empirical defense numbers.\n"
        "We can achieve over 2,500 produces/sec and over 3,300 consumes/sec.\n"
        "We also provide an honest evaluation of the 'price of guarantees': transactional idempotency, audit triggers, and RLS cost 32x compared to a bare raw insert, but provide complete enterprise correctness."
    )

    # ==========================================
    # SLIDE 16: SYSTEM DEMONSTRATION & VERIFICATION
    # ==========================================
    s16 = prs.slides.add_slide(blank_layout)
    apply_background(s16)
    add_header(s16, "Verification & Tooling", "Live Dashboard & Automated Scenario Verification", "Self-asserting test suites and real-time operational user interface")

    c1 = add_card(s16, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "9-Page Operational Dashboard (Port 8000)", ACCENT_CYAN)
    add_bullet(c1, "Overview:", "Real-time stat cards, throughput charts, consumer group lag table, and maintenance buttons.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "Message Browser:", "Live event-driven message inspector updating dynamically via SSE.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "Playground:", "End-to-end interactive demo: send message -> view location chip -> consume -> ack/nack.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "Topics & Groups:", "Topic creation with JSON schema contracts and group subscription management.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "Audit & DLQ:", "Filterable immutable audit trail and DLQ requeue management.", 10, TEXT_WHITE, 6)
    add_bullet(c1, "SQL Console:", "Built-in read-only query analyzer with statement_timeout safety.", 10, TEXT_WHITE, 0)

    c2 = add_card(s16, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "8 Self-Asserting Demo Scripts", ACCENT_GREEN)
    add_bullet(c2, "01_basic_flow.py:", "Send -> stored -> read -> ack complete lifecycle.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "02_concurrency_race.py:", "3 racing consumers; verifies zero duplicate deliveries.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "03_idempotency.py:", "Retry storm: duplicate sequence returns original location with 1 row on disk.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "04_poison_dlq.py:", "Poison message failing 3x moves to DLQ; successfully requeued.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "05_crash_recovery.py:", "Simulated worker crash; reaper restores message visibility.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "06_security.py:", "RLS/ACL denial verification and persisted audit records.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "07_exactly_once.py:", "Atomic multi-table ack + committed offset verification.", 10, TEXT_WHITE, 6)
    add_bullet(c2, "08_wal_recovery.ps1:", "Database SIGKILL hard crash and WAL recovery replay.", 10, TEXT_WHITE, 0)

    add_notes(s16,
        "We have built complete verification tools for this review.\n"
        "First, our offline-capable web dashboard on localhost:8000 provides full visual inspection.\n"
        "Second, we have 8 self-asserting Python demo scripts in demos/ that prove concurrency, idempotency, DLQ, and crash recovery with zero manual setup."
    )

    # ==========================================
    # SLIDE 17: RUBRIC SATURATION & CONCLUSION
    # ==========================================
    s17 = prs.slides.add_slide(blank_layout)
    apply_background(s17)
    add_header(s17, "Conclusion & Evaluation Rubric", "Second Review (Implementation Review) Rubric Saturation: 10/10 Marks", "Complete mapping of project deliverables against every evaluation criteria")

    # Table of Rubric Mapping
    table_shape = s17.shapes.add_table(5, 3, Inches(0.8), Inches(1.6), Inches(11.733), Inches(4.5))
    table = table_shape.table
    table.columns[0].width = Inches(3.2)
    table.columns[1].width = Inches(5.8)
    table.columns[2].width = Inches(2.733)

    headers = ["Evaluation Criteria (10 Marks)", "Conduit Implementation Details", "Artifact / Verification"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = CARD_BORDER
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = ACCENT_CYAN

    data = [
        ("1. Database Implementation\n(Tables, Constraints, Validation)", 
         "15 tables in 3NF/BCNF, 157 constraints (composite PKs, FK CASCADE/RESTRICT, domain CHECKs), monthly range partitioning, JSONB schema validation.",
         "00_schema.sql\nsmoke_m2.sql\npg_constraint count: 157"),
        
        ("2. Data Insertion & Management\n(Ingestion, Housekeeping, DLQ)", 
         "Idempotent 5-step produce transaction, 2,000-message production seed, per-topic purge_retention(), global partition drop, DLQ and reaper procedures.",
         "10_functions.sql\n50_seed.sql\ndemos/03_idempotency.py"),

        ("3. Database Operations\n(Queries, Filtering, Joins, Aggregation)", 
         "Non-blocking SELECT ... FOR UPDATE SKIP LOCKED query, 4-table joins for consumer lag, single-pass FILTER aggregations, window functions for throughput.",
         "40_views.sql\nv_consumer_lag\nv_throughput_by_minute"),

        ("4. Advanced Database Features\n(Procedures, Triggers, RLS, Indexing)", 
         "PL/pgSQL broker procedures, 15 active database triggers, native Row-Level Security (RLS) with conduit_app role, partial & BRIN indexes, materialized views, WAL recovery.",
         "20_triggers.sql\n30_rls.sql\nbenchmarks/explain_at_scale")
    ]

    for row_idx, row_data in enumerate(data, start=1):
        for col_idx, text in enumerate(row_data):
            cell = table.cell(row_idx, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG
            p = cell.text_frame.paragraphs[0]
            p.text = text
            p.font.name = "Arial"
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_WHITE

    # Bottom sign-off text
    sign_off = s17.shapes.add_textbox(Inches(0.8), Inches(6.3), Inches(11.733), Inches(0.6))
    p_so = sign_off.text_frame.paragraphs[0]
    p_so.text = "Team 17  ·  G Anirudh (24BDS0335)  ·  Tanay Mohta (24BDS0294)  ·  Dhyey Dhumasia (24BCE0529)  ·  Thank you! Questions Welcome."
    p_so.font.name = "Arial"
    p_so.font.size = Pt(11)
    p_so.font.bold = True
    p_so.font.color.rgb = ACCENT_GREEN
    p_so.alignment = PP_ALIGN.CENTER

    add_notes(s17,
        "In conclusion, Conduit completely saturates every single line of the Review 2 rubric.\n"
        "We have demonstrated robust schema design, 157 constraints, transactional data ingestion, complex relational joins and window aggregations, and advanced DBMS features including stored procedures, 15 triggers, RLS, partial/BRIN indexing, and WAL recovery.\n"
        "Thank you, and we are now ready to demonstrate the live system and answer your questions."
    )

    prs.save(output_path)
    print(f"Presentation saved successfully to {output_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "Conduit_DBMS_Review_2.pptx"
    create_presentation(out_file)
