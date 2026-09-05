import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 752, "ROULETTE-KAKI  |  TECHNICAL IMPLEMENTATION PLAN")
            self.setFont("Helvetica", 8)
            self.drawRightString(558, 752, "Policy Intelligence & Parliamentary Platform")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.75)
            self.line(54, 744, 558, 744)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(54, 42, 558, 42)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(54, 30, "CONFIDENTIAL & PROPRIETARY  —  Singapore Policy & Hansard Analytics Engine")
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 30, page_text)
        self.restoreState()


def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=3
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        leftIndent=10,
        spaceAfter=3
    )

    code_pill_style = ParagraphStyle(
        'CodePill',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0284C7")
    )

    callout_text = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#1E293B")
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#FFFFFF")
    )

    table_body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("Interactive News Website UI with Embedded Policy Query Agent", title_style))
    story.append(Paragraph("<b>Technical Architecture &amp; Implementation Specification</b> &bull; SingGov PolicyWire &bull; System Integration", subtitle_style))
    
    # Metadata Pill Box
    meta_data = [
        [
            Paragraph("<b>Target Framework:</b> React 19 + Vite + Tailwind CSS", table_body_style),
            Paragraph("<b>Backend:</b> FastAPI / Bedrock Nova Lite", table_body_style),
            Paragraph("<b>Version:</b> 2.4.0 (Unified Release)", table_body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[175, 175, 154])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))

    # Goal Description
    story.append(Paragraph("1. Goal Description", h1_style))
    story.append(Paragraph(
        "Build a modern, highly polished news-portal styled user interface for Singapore public policies. "
        "On the frontpage, users browse recent policy announcements organized like an authoritative editorial news publication "
        "(newspaper masthead, breaking ticker, lead story hero, category desks, trending policy updates). "
        "When a user clicks on any policy article, the central article reading body is dynamically replaced by a dedicated, "
        "interactive <b>Policy Query Agent chatbot</b> stream with an auto-generated executive briefing, instant suggested inquiry pills, "
        "and real-time grounded conversational Q&amp;A powered by official Singapore Government gazettes and circulars.",
        body_style
    ))
    story.append(Spacer(1, 4))

    # Callout: User Review Required
    story.append(Paragraph("2. Critical Architecture Decisions (User Review)", h1_style))
    
    callout_content = [
        [
            Paragraph("<b>CRITICAL ARCHITECTURAL HIGHLIGHTS &amp; GUARDRAILS</b>", ParagraphStyle('H', parent=callout_text, fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#0369A1"))),
        ],
        [
            Paragraph("&bull; <b>Editorial Theme &amp; Branding:</b> Styled as <i>'The Singapore Policy Herald / PolicyWire SG'</i>, combining the authority of top broadsheets (Straits Times, FT, Reuters, CNA) with sleek dark/light mode responsive tokens.", callout_text)
        ],
        [
            Paragraph("&bull; <b>Ground-Truth Policy Registry:</b> Built a comprehensive, type-safe policy dataset covering key 2024–2026 national frameworks: BTO Plus/Prime Housing Framework, CPF SA Closure &amp; ERS Adjustments, MediShield Life Claim Revisions, SkillsFuture Level-Up, Shared Parental Leave 2026, and the Majulah Package.", callout_text)
        ],
        [
            Paragraph("&bull; <b>Seamless Query Agent Priming:</b> Opening any policy article primes the embedded Query Agent with the policy's structured context and official government sources, generating an immediate context briefing and interactive question-answering session.", callout_text)
        ],
        [
            Paragraph("&bull; <b>No-Embedding &amp; Direct Citation Policy:</b> In strict compliance with system architecture rules, queries avoid vector databases, relying on live multi-source web scraping and document context feeding directly to Amazon Bedrock Nova Lite.", callout_text)
        ]
    ]
    callout_table = Table(callout_content, colWidths=[504])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0284C7")),
        ('LINEBELOW', (0,0), (-1,0), 0.75, colors.HexColor("#BAE6FD")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,0), 4),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 6))

    # Proposed Changes & Component Architecture
    story.append(Paragraph("3. Proposed Changes &amp; File Breakdown", h1_style))
    story.append(Paragraph("The platform is structured into modular components within the frontend application and interconnected backend endpoints:", body_style))
    
    # Table of Files & Components
    file_table_data = [
        [
            Paragraph("Type", table_header_style),
            Paragraph("File Path", table_header_style),
            Paragraph("Functional Responsibility", table_header_style)
        ],
        [
            Paragraph("<b>NEW</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#059669"))),
            Paragraph("<code>src/data/policies.ts</code>", code_pill_style),
            Paragraph("Central policy registry with metadata, official .gov.sg sources, key metrics (income ceilings, payout caps), and preset briefing templates.", table_body_style)
        ],
        [
            Paragraph("<b>NEW</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#059669"))),
            Paragraph("<code>src/components/NewsHeader.tsx</code>", code_pill_style),
            Paragraph("Newspaper masthead with live date stamp, breaking ticker, navigation tabs, and Parliamentary Debates portal link.", table_body_style)
        ],
        [
            Paragraph("<b>NEW</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#059669"))),
            Paragraph("<code>src/components/PolicyHeroCard.tsx</code>", code_pill_style),
            Paragraph("Frontpage editorial lead story card with ministry badges, publication timestamp, lead abstract, and 'Read &amp; Consult AI' trigger.", table_body_style)
        ],
        [
            Paragraph("<b>NEW</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#059669"))),
            Paragraph("<code>src/components/PolicyNewsCard.tsx</code>", code_pill_style),
            Paragraph("Responsive multi-column news card with category indicator, headline, summary snippet, and interactive hover states.", table_body_style)
        ],
        [
            Paragraph("<b>NEW</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#059669"))),
            Paragraph("<code>src/pages/PolicyArticlePage.tsx</code>", code_pill_style),
            Paragraph("Interactive article view replacing static text with the embedded Query Agent chat stream, official sources sidebar, and key fact pills.", table_body_style)
        ],
        [
            Paragraph("<b>NEW</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#059669"))),
            Paragraph("<code>src/pages/PolicyNewsFeed.tsx</code>", code_pill_style),
            Paragraph("Editorial frontpage feed displaying breaking alerts, hero banner, category desks (Housing, CPF, Health), and trending queries.", table_body_style)
        ],
        [
            Paragraph("<b>MOD</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#D97706"))),
            Paragraph("<code>src/App.tsx</code>", code_pill_style),
            Paragraph("Unified top-level routing container coordinating header navigation, global state, and embedded policy assistant views.", table_body_style)
        ],
        [
            Paragraph("<b>MOD</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#D97706"))),
            Paragraph("<code>src/main.tsx</code>", code_pill_style),
            Paragraph("React Router DOM configuration for <code>/</code>, <code>/policy/:id</code>, <code>/debates</code>, and <code>/query</code>.", table_body_style)
        ],
        [
            Paragraph("<b>MOD</b>", ParagraphStyle('T', parent=table_body_style, textColor=colors.HexColor("#D97706"))),
            Paragraph("<code>src/index.css</code>", code_pill_style),
            Paragraph("Refined typographic hierarchy (Merriweather / Outfit / Inter), newspaper border rules, and animated chat response bubbles.", table_body_style)
        ]
    ]

    file_table = Table(file_table_data, colWidths=[36, 154, 314])
    file_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('PADDING', (0,0), (-1,-1), 3.5),
    ]))
    story.append(file_table)
    story.append(Spacer(1, 6))

    # Key Fact Ingestion & Income Ceilings
    story.append(Paragraph("4. Policy Ground-Truth &amp; Parameter Enforcement", h1_style))
    story.append(Paragraph(
        "To eliminate LLM hallucinations on critical statutory limits, exact statutory thresholds were encoded into the agent's baseline knowledge repository:",
        body_style
    ))

    policy_matrix = [
        [
            Paragraph("Policy Scheme", table_header_style),
            Paragraph("Category", table_header_style),
            Paragraph("Enforced Statutory Parameters &amp; Thresholds", table_header_style),
            Paragraph("Primary Official Source", table_header_style)
        ],
        [
            Paragraph("<b>BTO Plus/Prime Framework</b>", table_body_style),
            Paragraph("Housing (HDB)", table_body_style),
            Paragraph("<b>Singles:</b> &#36;8,000/mo income ceiling<br/><b>Couples/Families:</b> &#36;16,000/mo income ceiling<br/><b>MOP:</b> 10 years; Subsidy Clawback applies", table_body_style),
            Paragraph("HDB Gazetted Guidelines (Oct 2024)", table_body_style)
        ],
        [
            Paragraph("<b>CPF SA Closure &amp; ERS</b>", table_body_style),
            Paragraph("CPF &amp; Retirement", table_body_style),
            Paragraph("<b>Closure:</b> Age 55 SA balances transferred to RA up to FRS, excess to OA.<br/><b>ERS:</b> 4x BRS (&#36;426,000 in 2025)", table_body_style),
            Paragraph("CPF Board Circular (Budget 2024)", table_body_style)
        ],
        [
            Paragraph("<b>Shared Parental Leave</b>", table_body_style),
            Paragraph("Family &amp; Grants", table_body_style),
            Paragraph("<b>Total:</b> 10 weeks shared leave by 1 Apr 2026 (6 weeks from 1 Apr 2025). Paid by Govt up to &#36;2,500/week.", table_body_style),
            Paragraph("MSF &amp; MOM Joint Release", table_body_style)
        ],
        [
            Paragraph("<b>SkillsFuture Level-Up</b>", table_body_style),
            Paragraph("Manpower (MOM)", table_body_style),
            Paragraph("<b>Top-up:</b> &#36;4,000 for Singaporeans aged 40+.<br/><b>Training Allowance:</b> Up to &#36;3,000/month for up to 24 months.", table_body_style),
            Paragraph("SkillsFuture Singapore (SSG)", table_body_style)
        ]
    ]
    matrix_table = Table(policy_matrix, colWidths=[110, 80, 200, 114])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('PADDING', (0,0), (-1,-1), 3.5),
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 6))

    # Verification Plan
    story.append(Paragraph("5. Verification &amp; Validation Plan", h1_style))
    
    verif_items = [
        "<b>Frontend Build &amp; Typecheck:</b> Executed <code>npm run build</code> in <code>query_agent/frontend</code> with zero TypeScript or JSX bundling errors.",
        "<b>Navigation &amp; Routing Verification:</b> Verified routes <code>/</code>, <code>/policy/:id</code>, <code>/debates</code>, and <code>/query</code> resolve smoothly with correct breadcrumbs and page titles.",
        "<b>Embedded Query Agent Interaction:</b> Validated that clicking a policy loads the executive brief and quick-ask chips, and queries to <code>POST /query</code> return structured, cited responses.",
        "<b>Accuracy &amp; Hallucination Testing:</b> Conducted live queries against HDB income ceilings, CPF retirement sums, and maternity leave rules to ensure strict adherence to official figures.",
        "<b>Backend Integration &amp; Proxying:</b> Verified that Vite proxy routes <code>/api/debates/*</code> and <code>/debates/*</code> to the BlogPost service (port 8001) while <code>/query</code> routes to the QueryAgent service (port 8000)."
    ]
    for item in verif_items:
        story.append(Paragraph(f"&bull; {item}", bullet_style))

    story.append(Spacer(1, 8))

    # Signoff Block
    signoff_data = [
        [
            Paragraph("<b>Architecture Status:</b> <font color='#059669'>APPROVED &amp; IMPLEMENTED</font>", table_body_style),
            Paragraph("<b>Audit Date:</b> September 2026", table_body_style),
            Paragraph("<b>Target Environment:</b> Production / Staging", table_body_style)
        ]
    ]
    signoff_table = Table(signoff_data, colWidths=[175, 160, 169])
    signoff_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(signoff_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == '__main__':
    output_path = sys.argv[1] if len(sys.argv) > 1 else "implementation_plan.pdf"
    build_pdf(output_path)
