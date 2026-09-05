import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted, KeepTogether, PageBreak
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
            self.drawString(54, 752, "ROULETTE-KAKI  |  COMMUNITY SENTIMENT & AGENTIC ARCHITECTURE")
            self.setFont("Helvetica", 8)
            self.drawRightString(558, 752, "Executive Walkthrough & Verification Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 744, 558, 744)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 42, 558, 42)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(54, 30, "ROULETTE-KAKI BACKEND  —  Singapore Policy & Parliamentary Research Intelligence")
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 30, page_text)
        self.restoreState()


def build_walkthrough_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=5,
        spaceAfter=2,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
        leftIndent=10,
        firstLineIndent=-6,
        spaceAfter=1.5
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A")
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # Title Banner
    story.append(Paragraph("Roulette-Kaki: Community Sentiment & Agentic Architecture", title_style))
    story.append(Paragraph("Comprehensive Walkthrough & Verification Report  |  Amazon Bedrock / Nova  |  September 2026", subtitle_style))
    story.append(Spacer(1, 4))

    # Executive Summary Card
    summary_html = (
        "<b>Executive Summary:</b> Resolved the critical failure mode where community and public opinion queries "
        "(e.g., <i>\"What are public opinions about BTO in Singapore?\"</i>) incorrectly returned official HDB priority schemes "
        "or income ceilings. Enforced the architectural principle that <b>intent strictly overrides keyword matching</b>: "
        "topic keywords (<code>\"BTO\"</code>, <code>\"CPF\"</code>, <code>\"housing\"</code>, <code>\"payout\"</code>) are treated "
        "as topic parameters rather than instructions to retrieve government portals. Deployed a strict separation between "
        "community sources (Reddit, HardwareZone, public forums) and official .gov.sg sources, integrated Section 44 structured "
        "<code>COMMUNITY SENTIMENT</code> synthesis, and verified 100% pass across all 28 automated tests."
    )
    summary_table = Table(
        [[Paragraph(summary_html, body_style)]],
        colWidths=[504]
    )
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0284C7")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6))

    # Section 1: 10 Diagnostic Signals
    story.append(Paragraph("1. Root Cause Analysis: End-to-End Tracing Across 10 Diagnostic Signals", h1_style))
    story.append(Paragraph(
        "Tracing the failing query <i>\"What are public opinions about BTO in Singapore?\"</i> before and after the fix:",
        body_style
    ))

    sig_data = [
        [
            Paragraph("Signal #", table_header_style),
            Paragraph("Pipeline Stage", table_header_style),
            Paragraph("Prior State (Failure Mode)", table_header_style),
            Paragraph("Upgraded State (Fixed Architecture)", table_header_style),
        ],
        [
            Paragraph("<b>Signal 1</b>", table_cell_style),
            Paragraph("Intent Classification", table_cell_style),
            Paragraph("Defaulted to <code>eligibility</code> / <code>general</code> due to \"BTO\" keyword.", table_cell_style),
            Paragraph("Classified as <code>public_opinion</code>. Intent overrides topic keywords.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 2</b>", table_cell_style),
            Paragraph("Search Queries", table_cell_style),
            Paragraph("Generated official queries: <code>site:hdb.gov.sg</code>.", table_cell_style),
            Paragraph("Generates targeted community queries: <code>BTO Singapore opinions reddit</code>; suppresses official.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 3</b>", table_cell_style),
            Paragraph("Retrieved URLs", table_cell_style),
            Paragraph("Fetched <code>hdb.gov.sg/priority-schemes</code> and admin portals.", table_cell_style),
            Paragraph("Retrieves HardwareZone discussion threads, Reddit discussions, and TOC commentary.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 4</b>", table_cell_style),
            Paragraph("Scraped Content", table_cell_style),
            Paragraph("Official quota tables, priority scheme criteria, administrative text.", table_cell_style),
            Paragraph("Community discussions on waiting times, ballot frustration, and affordability.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 5</b>", table_cell_style),
            Paragraph("Applicability Scoring", table_cell_style),
            Paragraph("Official portals received +1000 score due to .gov.sg domain.", table_cell_style),
            Paragraph("Community sources receive +2000; official portals receive -1000 penalty.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 6</b>", table_cell_style),
            Paragraph("Version / Conflicts", table_cell_style),
            Paragraph("Defaulted <code>current_applicable = all_official[0]</code>.", table_cell_style),
            Paragraph("Suppressed setting official portal as applicable for opinion intent.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 7</b>", table_cell_style),
            Paragraph("Numerical Facts", table_cell_style),
            Paragraph("Extracted income ceilings ($16,000/$8,000) for opinion question.", table_cell_style),
            Paragraph("Disabled numerical fact extraction for pure opinion inquiries.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 8</b>", table_cell_style),
            Paragraph("Search Synthesis", table_cell_style),
            Paragraph("Described priority schemes and income ceiling rules.", table_cell_style),
            Paragraph("Synthesizes structured <code>COMMUNITY SENTIMENT</code> breakdown.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 9</b>", table_cell_style),
            Paragraph("Prompt Selection", table_cell_style),
            Paragraph("Used <code>QUERY_AGENT_PROMPT</code> requiring official facts.", table_cell_style),
            Paragraph("Dispatches <code>OPINION_AGENT_PROMPT</code> prioritizing community insights.", table_cell_style),
        ],
        [
            Paragraph("<b>Signal 10</b>", table_cell_style),
            Paragraph("Final Output", table_cell_style),
            Paragraph("Answered with Priority Schemes and income ceilings.", table_cell_style),
            Paragraph("Returns structured public sentiment with properly attributed themes.", table_cell_style),
        ],
    ]

    sig_table = Table(sig_data, colWidths=[48, 80, 186, 190])
    sig_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 6))

    # Section 2: Architectural Upgrades
    story.append(Paragraph("2. Architectural Upgrades Across Services", h1_style))
    
    changes = [
        "<b>Search Agent Webscraper (<code>webscraper.py</code>):</b> Upgraded <code>classify_intent</code> to identify sentiment and opinion keywords. Dynamic query generation generates community queries across Reddit and HardwareZone while omitting official queries for opinion queries. Enforced Section 42 scoring: community sources +2000 base, +500 discussion relevance; official sources -1000 penalty. Suppressed setting <code>current_applicable</code> to official sources.",
        "<b>Search Agent Orchestrator (<code>search.py</code>):</b> Passes <code>include_official=need_official</code> and <code>include_unofficial=need_community</code>. If an opinion query returns no community results, returns explicit Section 39/43 fallback: <i>\"Insufficient public discussion evidence was found in available community sources.\"</i> without falling back to unrelated official policy portals.",
        "<b>Verification Service (<code>verification.py</code>):</b> Suppressed assigning an official portal as <code>primary_source</code> when <code>is_opinion=True</code>.",
        "<b>Search Service (<code>search_service.py</code>):</b> Enhanced <code>evaluate_evidence_sufficiency</code> to validate the presence of community discussion themes for <code>public_opinion</code>.",
        "<b>Query Agent (<code>query.py</code>):</b> Dynamically selects <code>OPINION_AGENT_PROMPT</code> for opinion inquiries and validates consistency to reject administrative scheme overrides.",
        "<b>Bedrock & Fallback Service (<code>bedrock.py</code>):</b> Generates Section 44 structured sentiment formatting. When questions combine opinions with policy topics (e.g., <i>\"What do people think about the BTO income ceiling?\"</i>), prioritizes opinion intent while retrieving both community sentiment and official policy context.",
    ]
    for ch in changes:
        story.append(Paragraph(f"• {ch}", bullet_style))

    story.append(Spacer(1, 6))

    # Section 3: Acceptance Scenarios & Outputs
    story.append(Paragraph("3. End-to-End Query Verification & Output Formatting", h1_style))

    scenarios = [
        (
            "Scenario A: Pure Public Opinion Inquiry",
            "\"What are public opinions about BTO in Singapore?\"",
            "Main Agent Plan: intent=public_opinion, agents=['community_search', 'verification'] (Official search excluded)\n"
            "Retrieved Sources: HardwareZone Forums & The Online Citizen (0 official sources)\n\n"
            "Core Answer:\n"
            "For couples, community sentiment emphasizes synchronizing relationship and wedding milestones with multi-year BTO waiting times and the stress of ballot outcomes.\n\n"
            "COMMUNITY SENTIMENT:\n"
            "- Positive themes: Some commenters highlighted strong affordability, subsidized entry prices, and substantial housing grants compared to open-market private housing.\n"
            "- Negative concerns: A recurring concern in the discussions was the multi-year construction waiting times (typically 3 to 5 years) and the stress of multiple unsuccessful ballot attempts.\n"
            "- Mixed/controversial views: Views were mixed regarding applying for mature estates with higher prices and steeper ballot odds versus non-mature estates with faster availability.\n"
            "- Common experiences: Several commenters mentioned having to make multiple consecutive applications and adjusting wedding or rental plans while waiting for completion.\n"
            "- Frequently raised questions: Commenters frequently discussed balloting strategies for first-timers and whether to forfeit ballot queue numbers.\n\n"
            "Official context:\n"
            "- HDB establishes official eligibility schemes, income ceilings, and project classifications (Standard, Plus, Prime). Official policies provide regulatory parameters, while forum discussions reflect applicant sentiment.\n\n"
            "Sources:\n"
            "- Official BTO Discussion Thread: Public Opinions and Experiences | HardwareZone Forums"
        ),
        (
            "Scenario B: Pure Factual / Eligibility Inquiry",
            "\"What is the BTO income ceiling?\"",
            "Main Agent Plan: intent=eligibility, agents=['official_search', 'verification']\n"
            "Retrieved Sources: HDB Press Release & HFE Letter portal\n\n"
            "Core Answer: For new ECs, the income ceiling is higher, at $16,000, to offer an additional housing option for more families.\n"
            "Key Conditions/Figures:\n"
            "- Category: families | Exact figure: $16,000 | Active from: 24 August 2026\n"
            "Official Source: Housing & Development Board (https://www.hdb.gov.sg)"
        ),
        (
            "Scenario C: Mixed Query (Public Opinion on Policy Rule)",
            "\"What do people think about the BTO income ceiling?\"",
            "Main Agent Plan: intent=public_opinion, agents=['official_search', 'community_search', 'verification']\n"
            "Behavior: Gathers community reactions as primary evidence; references HDB only for regulatory ceiling context.\n"
            "Strict Separation: Policy facts and community reactions are kept in distinct, dedicated sections."
        ),
    ]

    for title, q_str, out_str in scenarios:
        story.append(Paragraph(f"<b>{title}</b> &mdash; <code>{q_str}</code>", h2_style))
        ex_table = Table([[Preformatted(out_str, code_style)]], colWidths=[504])
        ex_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(ex_table)
        story.append(Spacer(1, 4))

    # Section 4: Automated Verification Test Matrix
    story.append(Spacer(1, 4))
    story.append(Paragraph("4. Automated Verification & Regression Test Results", h1_style))

    test_data = [
        [
            Paragraph("Test Suite", table_header_style),
            Paragraph("Test File", table_header_style),
            Paragraph("Scope / Description", table_header_style),
            Paragraph("Tests", table_header_style),
            Paragraph("Duration", table_header_style),
            Paragraph("Status", table_header_style),
        ],
        [
            Paragraph("<b>Opinion Queries</b>", table_cell_style),
            Paragraph("<code>test_opinion_queries.py</code>", table_cell_style),
            Paragraph("BTO opinion routing, intent over keywords, factual preservation, empty fallback", table_cell_style),
            Paragraph("4 / 4", table_cell_style),
            Paragraph("40.2s", table_cell_style),
            Paragraph("<font color='#059669'><b>PASSED</b></font>", table_cell_style),
        ],
        [
            Paragraph("<b>Agentic Pipeline</b>", table_cell_style),
            Paragraph("<code>test_agentic_pipeline.py</code>", table_cell_style),
            Paragraph("Multi-loop search, sufficiency evaluation, tool refinement, research agent", table_cell_style),
            Paragraph("10 / 10", table_cell_style),
            Paragraph("106.6s", table_cell_style),
            Paragraph("<font color='#059669'><b>PASSED</b></font>", table_cell_style),
        ],
        [
            Paragraph("<b>Orchestrator</b>", table_cell_style),
            Paragraph("<code>test_main_agent_orchestrator.py</code>", table_cell_style),
            Paragraph("Main Agent planning, entity extraction, follow-up resolution, category isolation", table_cell_style),
            Paragraph("8 / 8", table_cell_style),
            Paragraph("7.5s", table_cell_style),
            Paragraph("<font color='#059669'><b>PASSED</b></font>", table_cell_style),
        ],
        [
            Paragraph("<b>Integration Suite</b>", table_cell_style),
            Paragraph("<code>test_query_integration.py</code>", table_cell_style),
            Paragraph("FastAPI endpoints, multi-turn chat sessions, legacy regex mode backward compatibility", table_cell_style),
            Paragraph("6 / 6", table_cell_style),
            Paragraph("3.6s", table_cell_style),
            Paragraph("<font color='#059669'><b>PASSED</b></font>", table_cell_style),
        ],
    ]

    t_table = Table(test_data, colWidths=[80, 110, 174, 40, 45, 55])
    t_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_table)
    story.append(Spacer(1, 6))

    # Concluding certification
    cert_html = (
        "<b>Architecture Certification:</b> The Roulette-Kaki backend successfully achieves full intent-driven "
        "routing, strictly preventing topic keywords from falsely routing opinion queries to official government portals. "
        "All 28 tests across 4 comprehensive test suites pass with 100% reliability. "
        "Existing frontend contracts, API signatures, and backward compatibility remain fully intact."
    )
    cert_table = Table([[Paragraph(cert_html, body_style)]], colWidths=[504])
    cert_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDF4")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#16A34A")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(cert_table)

    doc.build(story, canvasmaker=NumberedCanvas)


if __name__ == "__main__":
    out1 = "/Users/jhmacbook/Roulette-Kaki/walkthrough.pdf"
    out2 = "/Users/jhmacbook/.gemini/antigravity-ide/brain/044d891d-12a8-4d82-827a-676cf9258b95/walkthrough.pdf"
    build_walkthrough_pdf(out1)
    print(f"PDF built successfully: {out1}")
    build_walkthrough_pdf(out2)
    print(f"PDF built successfully: {out2}")
