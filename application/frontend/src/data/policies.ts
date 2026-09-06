import type { Policy, PolicyCategory } from "../types";

export const CATEGORIES: { id: PolicyCategory | "All"; label: string }[] = [
  { id: "All", label: "All Policy Desks" },
  { id: "Housing", label: "Housing & BTO" },
  { id: "CPF & Finance", label: "CPF & Retirement" },
  { id: "Healthcare", label: "Healthcare & MediShield" },
  { id: "Jobs & Skills", label: "Manpower & Skills" },
  { id: "Grants & Families", label: "Family & Subsidies" },
  { id: "Parliament & Hansard", label: "Parliament & Hansard" },
];

export const POLICIES: Policy[] = [
  {
    id: "singles-bto-framework",
    title: "New BTO Classification: Singles Granted Islandwide Access to 2-Room Flats",
    headline: "MND Overhauls Housing Model: Singles Allowed to Buy 2-Room Flats in Standard, Plus, and Prime Projects",
    category: "Housing",
    ministry: "Ministry of National Development (MND) & HDB",
    publishedAt: "Recent Gazette",
    effectiveDate: "October 2024 BTO Launch onwards",
    status: "Active",
    badge: "Lead Policy",
    summary:
      "Eligible first-timer singles aged 35 and above can now apply for 2-room Flexi BTO flats across all project classifications (Standard, Plus, and Prime) islandwide.",
    leadParagraph:
      "Under the revised public housing classification framework, the longstanding restriction confining singles to non-mature estates has been eliminated. First-timer singles aged 35 and older can now apply for new 2-room Flexi flats in any location across Singapore, subject to stricter Minimum Occupation Periods (MOP) and subsidy clawbacks for Plus and Prime locations.",
    readTime: "3 min read / AI Consult",
    keyFacts: [
      { label: "Eligible Age", value: "35 years & above (Singles)", note: "First-timer Singapore Citizens" },
      { label: "Flat Types Eligible", value: "2-room Flexi only", note: "Across Standard, Plus & Prime" },
      { label: "Income Ceiling", value: "$8,000 / month", note: "Gross monthly household income (raised from $7,000)" },
      { label: "Plus/Prime MOP", value: "10 Years", note: "5 years for Standard flats" },
      { label: "Subsidy Recovery", value: "6% - 9% upon resale", note: "Applies to first sale of Plus/Prime" },
    ],
    officialSources: [
      {
        title: "HDB Classification Framework for New BTO Flats",
        url: "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles",
        authority: "Housing & Development Board (HDB)",
      },
      {
        title: "MND Press Release on Housing Support for Singles",
        url: "https://www.mnd.gov.sg",
        authority: "Ministry of National Development",
      },
    ],
    suggestedQuestions: [
      "What is the exact income ceiling for singles buying a BTO flat?",
      "Can singles buy a 3-room BTO flat in Plus or Prime areas?",
      "How does the subsidy clawback work when selling a Plus or Prime flat?",
      "Can I rent out my whole flat after the 10-year MOP?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: Singles BTO Classification Framework

**Issuing Authority:** Ministry of National Development (MND) & HDB  
**Status:** In Effect (From Oct 2024 BTO Exercise)

#### 🔑 Key Policy Changes:
1. **Islandwide 2-Room Access:** First-timer Singaporean singles aged 35+ are no longer confined to non-mature estates. You can now apply for new 2-room Flexi BTO flats across **Standard, Plus, and Prime** locations islandwide.
2. **Eligibility & Income Ceiling:** Monthly gross income ceiling is **$8,000** for single citizens purchasing a 2-room flat.
3. **Minimum Occupation Period (MOP):**
   - **Standard flats:** 5-year MOP.
   - **Plus & Prime flats:** Strict **10-year MOP** before you can sell or invest in private property.
4. **Resale & Rental Conditions:**
   - For Plus/Prime: Whole-flat rental is strictly prohibited even after the 10-year MOP (room rental permitted).
   - Subsidy clawback (percentage of resale price) applies upon the flat's first resale.

---
💡 *Ask me any question below regarding your eligibility, grants, flat restrictions, or resale rules!*`,
    relatedPolicyIds: ["cpf-sa-closure-ers", "shared-parental-leave-2026"],
  },
  {
    id: "cpf-sa-closure-ers",
    title: "CPF Special Account Closure for Members Aged 55+ and Enhanced Retirement Sum Expansion",
    headline: "CPF Restructuring: SA to Close at Age 55 with ERS Raised to 4x Basic Retirement Sum",
    category: "CPF & Finance",
    ministry: "Ministry of Manpower (MOM) & CPF Board",
    publishedAt: "Budget Announcement",
    effectiveDate: "From Early 2025",
    status: "Active",
    badge: "Retirement Reform",
    summary:
      "CPF Special Accounts will close for members when they turn 55. Savings transfer to RA up to the Full Retirement Sum, while the Enhanced Retirement Sum ceiling is raised to 4x BRS.",
    leadParagraph:
      "To streamline retirement tiers and prevent non-withdrawable shielding advantages, the CPF Special Account (SA) is automatically closed for members at age 55. SA savings are transferred to the Retirement Account (RA) up to the Full Retirement Sum (FRS), with the remaining balance moved to the Ordinary Account (OA). Meanwhile, the Enhanced Retirement Sum (ERS) is raised to 4 times the Basic Retirement Sum.",
    readTime: "4 min read / AI Consult",
    keyFacts: [
      { label: "SA Closure Age", value: "Age 55", note: "Occurs when RA is created" },
      { label: "Enhanced Retirement Sum (ERS)", value: "4x BRS ($426,000 in 2025)", note: "Up from 3x BRS" },
      { label: "OA Interest Rate", value: "2.5% p.a.", note: "Excess SA funds move to OA if RA is full" },
      { label: "RA Interest Rate", value: "4.0% p.a. + extra interest", note: "Compounded long-term for CPF LIFE" },
    ],
    officialSources: [
      {
        title: "CPF Board - Closure of Special Account for Members Aged 55 and Above",
        url: "https://www.cpf.gov.sg",
        authority: "Central Provident Fund Board",
      },
      {
        title: "Ministry of Manpower - CPF Retirement Changes",
        url: "https://www.mom.gov.sg",
        authority: "Ministry of Manpower (MOM)",
      },
    ],
    suggestedQuestions: [
      "Where does my CPF money go when the Special Account closes at 55?",
      "Can I voluntarily transfer my Ordinary Account funds into the Retirement Account to get the 4% interest?",
      "What is the maximum CPF LIFE monthly payout under the new ERS ceiling?",
      "How can I withdraw my CPF funds after age 55?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: CPF Special Account (SA) Closure & ERS Raised

**Issuing Authority:** Ministry of Manpower (MOM) & CPF Board  
**Status:** Effective 2025

#### 🔑 Key Policy Changes:
1. **Closure of Special Account at Age 55:**
   - Upon reaching 55, your **Retirement Account (RA)** is created.
   - SA savings are first transferred to the RA to meet the Full Retirement Sum (FRS).
   - Any remaining SA balances are automatically transferred to your **Ordinary Account (OA)** (yielding 2.5% p.a.), where they remain withdrawable anytime.
2. **Enhanced Retirement Sum (ERS) Multiplier:**
   - The ERS maximum ceiling has been raised from 3x to **4x the Basic Retirement Sum (BRS)** (approx. $426,000 for 2025).
   - Members can voluntarily top up their RA to the new ERS cap to earn 4.0% p.a. interest and receive significantly higher lifelong monthly payouts under CPF LIFE (approx. $3,300/mo).

---
💡 *Ask me any question below about your CPF calculations, topping up, or withdrawal rights!*`,
    relatedPolicyIds: ["majulah-package", "singles-bto-framework"],
  },
  {
    id: "medishield-life-2026",
    title: "MediShield Life 2025/2026 Review: Expanded Claim Limits & Outpatient Coverage",
    headline: "MOH Expands MediShield Life: Substantially Higher Inpatient Caps & New Outpatient Coverage",
    category: "Healthcare",
    ministry: "Ministry of Health (MOH)",
    publishedAt: "MOH Gazette",
    effectiveDate: "Phased implementation from April 2025",
    status: "Upcoming Revision",
    badge: "Healthcare Update",
    summary:
      "MediShield Life claim limits are being increased to cover a larger portion of large hospital bills, alongside premium adjustments and enhanced government subsidies.",
    leadParagraph:
      "The Ministry of Health has accepted the recommendations of the MediShield Life Council. The changes increase daily inpatient claim limits, raise the policy year claim limit from $150,000 to $200,000, and expand protection for high-cost outpatient treatments such as Cell, Tissue and Gene Therapy Products (CTGTP).",
    readTime: "3 min read / AI Consult",
    keyFacts: [
      { label: "Policy Year Claim Cap", value: "$200,000 / year", note: "Increased from $150,000" },
      { label: "ICU Daily Limit", value: "Up to $5,140 / day", note: "Substantially increased from $2,200" },
      { label: "Standard Ward Daily Cap", value: "Up to $1,630 / day", note: "First 2 days of normal ward stay" },
      { label: "Government Premium Subsidies", value: "Up to 50% for lower-to-middle income", note: "Supported by Medisave top-ups" },
    ],
    officialSources: [
      {
        title: "MOH MediShield Life Review Committee Recommendations",
        url: "https://www.moh.gov.sg",
        authority: "Ministry of Health (MOH)",
      },
    ],
    suggestedQuestions: [
      "What is the new annual claim limit under MediShield Life?",
      "How will the premium adjustments affect seniors and low-income families?",
      "Does MediShield Life cover private hospital bills completely?",
      "Are outpatient cancer treatments and gene therapies covered?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: MediShield Life Enhancements

**Issuing Authority:** Ministry of Health (MOH)  
**Status:** Rolling out from April 2025

#### 🔑 Key Highlights:
1. **Higher Inpatient & ICU Claim Limits:**
   - Daily ICU claim limit rises from $2,200 up to **$5,140**.
   - Standard inpatient daily limit rises from $1,000 up to **$1,630** for the first 2 days.
2. **Raised Annual Claim Limit:**
   - Increased from $150,000 to **$200,000 per policy year**.
3. **Outpatient & Emerging Treatments:**
   - Broadened coverage for expensive outpatient treatments and Cell, Tissue and Gene Therapy Products (CTGTP).
4. **Premium Support & Government Subsidies:**
   - Premium subsidies of up to **50%** for lower- and middle-income Singaporeans, with extra MediSave top-ups to offset premium increases.

---
💡 *Ask me any question below about claim caps, deductible rules, or Integrated Shield Plan overlaps!*`,
    relatedPolicyIds: ["majulah-package"],
  },
  {
    id: "skillsfuture-levelup",
    title: "SkillsFuture Level-Up Programme: $4,000 Credit & $3,000 Monthly Training Allowance",
    headline: "Mid-Career Reskilling Boost: $4,000 Targeted Top-up and Up to $3,000/Month Training Allowance",
    category: "Jobs & Skills",
    ministry: "Ministry of Education (MOE) & SkillsFuture Singapore (SSG)",
    publishedAt: "Budget Measure",
    effectiveDate: "From May 2024 & Training Allowance from 2025",
    status: "Active",
    badge: "Workforce",
    summary:
      "Singaporeans aged 40 and above receive a $4,000 SkillsFuture Credit (Mid-Career) top-up and monthly training allowances up to $3,000 for full-time diploma and degree reskilling.",
    leadParagraph:
      "To support mid-career Singaporeans through structural industry shifts, the government launched the SkillsFuture Level-Up Programme. Singapore citizens aged 40 and above receive a targeted $4,000 credit top-up for selected career-transition courses and up to 24 months of monthly training allowances capped at $3,000/month for full-time long-form programmes.",
    readTime: "3 min read / AI Consult",
    keyFacts: [
      { label: "Eligibility Age", value: "40 years & above", note: "Singapore Citizens" },
      { label: "Credit Top-up", value: "$4,000 (No expiry)", note: "Targeted at courses with high employability" },
      { label: "Training Allowance", value: "50% of last drawn salary (up to $3,000/mo)", note: "Max 24 months lifetime" },
      { label: "Subsidised Diploma/Degree", value: "Mid-Career Enhanced Subsidy", note: "Available at ITE, Polytechnics & Universities" },
    ],
    officialSources: [
      {
        title: "SkillsFuture Level-Up Programme Guidelines",
        url: "https://www.skillsfuture.gov.sg",
        authority: "SkillsFuture Singapore (SSG)",
      },
    ],
    suggestedQuestions: [
      "Who is eligible for the $4,000 SkillsFuture Credit top-up?",
      "Can I use the $4,000 credit for any hobby or recreational course?",
      "How do I qualify for the $3,000 monthly training allowance?",
      "What happens if I already used my previous SkillsFuture credit?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: SkillsFuture Level-Up Programme

**Issuing Authority:** SkillsFuture Singapore (SSG) / Ministry of Education  
**Status:** Active

#### 🔑 Key Programme Pillars:
1. **$4,000 SkillsFuture Credit (Mid-Career):**
   - Disbursed to all Singapore Citizens turning 40 in that calendar year and above.
   - Dedicated strictly to courses that generate clear employability outcomes (e.g. diplomas, post-diplomas, WSQ Specialist Diplomas). Does not expire.
2. **SkillsFuture Mid-Career Training Allowance:**
   - Up to **50% of last drawn average monthly income**, capped at **$3,000 per month**.
   - Granted for full-time, long-form courses up to a lifetime total of 24 months.
3. **Subsidised Full-Time Diplomas:**
   - Singaporeans aged 40+ can pursue another subsidised full-time diploma at Polytechnics or ITE even if they already hold a higher qualification.

---
💡 *Ask me any question below about course eligibility, application criteria, or training payouts!*`,
    relatedPolicyIds: ["jobseeker-support-scheme", "majulah-package"],
  },
  {
    id: "shared-parental-leave-2026",
    title: "Enhanced Shared Parental Leave: Up to 10 Weeks of Government-Paid Leave by April 2026",
    headline: "Major Family Support Reform: Government Increases Shared Parental Leave to 10 Weeks",
    category: "Grants & Families",
    ministry: "Ministry of Social and Family Development (MSF) & MOM",
    publishedAt: "National Day Rally Announcement",
    effectiveDate: "Phased from 1 April 2025 to 1 April 2026",
    status: "Active",
    badge: "Family & Childcare",
    summary:
      "Parents of Singaporean babies will gain an additional 10 weeks of shared parental leave fully paid by the Government, bringing total paid leave to 30 weeks by April 2026.",
    leadParagraph:
      "In a major push to support young working families and encourage shared caregiving responsibilities, the Singapore Government is introducing a new Shared Parental Leave scheme. Implemented in two phases, working fathers and mothers can share 6 weeks of leave from April 2025, expanding to 10 weeks from April 2026, 100% paid by the government capped at $2,500/week.",
    readTime: "3 min read / AI Consult",
    keyFacts: [
      { label: "Total Leave by 2026", value: "10 weeks (Shared)", note: "Plus 16w maternity & 4w paternity" },
      { label: "Total Parental Leave Available", value: "30 Weeks Total", note: "Combined parental entitlement by 2026" },
      { label: "Government Funding", value: "100% funded by Govt", note: "Capped at $2,500/week (approx. $10,000/mo)" },
      { label: "Phased Rollout", value: "6 weeks (Apr 2025) → 10 weeks (Apr 2026)", note: "For children born on/after 1 Apr" },
    ],
    officialSources: [
      {
        title: "Made For Families - Enhancements to Parental Leave Schemes",
        url: "https://www.madeforfamilies.gov.sg",
        authority: "Prime Minister's Office & MSF",
      },
      {
        title: "MOM Guidelines on Government-Paid Leave",
        url: "https://www.mom.gov.sg",
        authority: "Ministry of Manpower (MOM)",
      },
    ],
    suggestedQuestions: [
      "How is the 10 weeks of shared parental leave split between mother and father?",
      "When does the full 10-week entitlement take effect?",
      "What is the government wage reimbursement cap per week?",
      "Are self-employed parents eligible for this shared leave?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: Shared Parental Leave (SPL) Scheme

**Issuing Authority:** MSF & Ministry of Manpower (MOM)  
**Status:** In effect from 1 April 2025 (Phased to 10 weeks by 1 April 2026)

#### 🔑 Key Features:
1. **Phased Implementation:**
   - **Phase 1 (1 April 2025):** 6 weeks of shared leave.
   - **Phase 2 (1 April 2026):** **10 weeks** of shared leave.
2. **Total Combined Parental Leave (by 2026):**
   - Mother: 16 weeks Maternity Leave.
   - Father: 4 weeks Paternity Leave.
   - Shared Leave: 10 weeks (can be split between parents in any proportion).
   - **Total:** **30 weeks** of paid leave for a newborn child!
3. **100% Government Funded:**
   - All shared parental leave weeks are fully paid by the Government, capped at **$2,500 per week** (equivalent to roughly $10,000/month).

---
💡 *Ask me any question below regarding notice periods, employer requirements, or self-employed claims!*`,
    relatedPolicyIds: ["singles-bto-framework"],
  },
  {
    id: "jobseeker-support-scheme",
    title: "SkillsFuture Jobseeker Support Scheme: Up to $6,000 Over 6 Months for Involuntarily Jobless",
    headline: "New Retrenchment & Unemployment Support: Temporary Financial Aid for Jobseekers",
    category: "Jobs & Skills",
    ministry: "Ministry of Manpower (MOM) & Workforce Singapore (WSG)",
    publishedAt: "MOM Policy Launch",
    effectiveDate: "From April 2025",
    status: "Upcoming Revision",
    badge: "Safety Net",
    summary:
      "A landmark financial support scheme providing involuntarily unemployed Singaporeans up to $6,000 over 6 months while they actively look for work or undergo reskilling.",
    leadParagraph:
      "Marking a paradigm shift in Singapore's social safety net, the SkillsFuture Jobseeker Support Scheme provides tiered monthly payouts totaling up to $6,000 over 6 months to involuntarily unemployed citizens and permanent residents who commit to active job search activities.",
    readTime: "3 min read / AI Consult",
    keyFacts: [
      { label: "Maximum Payout", value: "Up to $6,000", note: "Tiered across 6 months" },
      { label: "Monthly Tiering", value: "M1: $1,500, M2: $1,250, M3: $1,000, M4: $750, M5: $750, M6: $750", note: "Higher payouts upfront" },
      { label: "Income Eligibility", value: "Previous average monthly income ≤ $5,000", note: "Within the past 12 months" },
      { label: "Conditionality", value: "Active job search / training required", note: "Monitored via WSG / CareersFinder" },
    ],
    officialSources: [
      {
        title: "MOM SkillsFuture Jobseeker Support Details",
        url: "https://www.mom.gov.sg",
        authority: "Ministry of Manpower (MOM)",
      },
    ],
    suggestedQuestions: [
      "Who qualifies as 'involuntarily unemployed' under this scheme?",
      "Can I receive the payouts if I resigned voluntarily?",
      "What job-seeking activities are required to maintain payout eligibility?",
      "Are Permanent Residents (PRs) eligible for the Jobseeker Support Scheme?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: SkillsFuture Jobseeker Support Scheme

**Issuing Authority:** Ministry of Manpower (MOM) & Workforce Singapore (WSG)  
**Status:** Launching April 2025

#### 🔑 Key Highlights:
1. **Tiered Payout Schedule (Total $6,000 over 6 months):**
   - Month 1: **$1,500**
   - Month 2: **$1,250**
   - Month 3: **$1,000**
   - Months 4 to 6: **$750 per month**
2. **Eligibility Criteria:**
   - Singapore Citizens & Permanent Residents aged 21 and above.
   - Involuntarily unemployed due to retrenchment, company cessation, or medical unfitness.
   - Previously earned an average gross income of **≤ $5,000/month**.
   - Residing in property with Annual Value ≤ $25,000.
3. **Active Job Search Requirement:**
   - Must engage in verified job searches, applications, or training courses through WSG.

---
💡 *Ask me any question below on how this interacts with severance packages or training allowances!*`,
    relatedPolicyIds: ["skillsfuture-levelup"],
  },
  {
    id: "majulah-package",
    title: "Majulah Package: Up to $9,000 in CPF MediSave & Retirement Top-ups for Young Seniors",
    headline: "Government Delivers Majulah Package: CPF Bonuses for Singaporeans Born 1973 or Earlier",
    category: "Grants & Families",
    ministry: "Ministry of Finance (MOF) & CPF Board",
    publishedAt: "Budget Allocation",
    effectiveDate: "Disbursed December 2024 onwards",
    status: "Implemented",
    badge: "Senior Support",
    summary:
      "A $8.2 billion package providing Earn and Save Bonuses, Retirement Savings Bonuses, and MediSave top-ups for Singapore citizens aged 50 and above (born 1973 or earlier).",
    leadParagraph:
      "The Majulah Package aims to bolster the retirement and healthcare adequacy of 'young seniors' in their 50s and early 60s, as well as the Pioneer and Merdeka Generations. Benefits include annual Earn and Save Bonuses up to $1,000, a one-off Retirement Savings Bonus up to $1,500, and a one-off MediSave Bonus up to $1,500.",
    readTime: "3 min read / AI Consult",
    keyFacts: [
      { label: "Target Cohort", value: "Born in 1973 or earlier (Aged 50+ in 2023)", note: "Singapore Citizens" },
      { label: "Earn and Save Bonus", value: "Up to $1,000 / year", note: "For working seniors earning up to $6,000/mo" },
      { label: "Retirement Savings Bonus", value: "One-off $1,000 to $1,500", note: "If CPF balances are below Basic Retirement Sum" },
      { label: "MediSave Bonus", value: "One-off $750 to $1,500", note: "Credited automatically to MediSave" },
    ],
    officialSources: [
      {
        title: "Ministry of Finance - Majulah Package Information",
        url: "https://www.mof.gov.sg",
        authority: "Ministry of Finance (MOF)",
      },
    ],
    suggestedQuestions: [
      "Do I need to apply for the Majulah Package or is it automatic?",
      "Can I receive the Earn and Save bonus if I work part-time?",
      "Are Merdeka and Pioneer Generations eligible for the MediSave top-up?",
    ],
    initialBriefing: `### 📋 Executive Policy Briefing: The Majulah Package

**Issuing Authority:** Ministry of Finance (MOF) & CPF Board  
**Status:** Implemented / Active

#### 🔑 Key Bonuses Breakdown:
1. **Earn and Save Bonus (Annual):**
   - **$400 to $1,000 credited yearly** to CPF for seniors working with monthly income between $500 and $6,000.
2. **Retirement Savings Bonus (One-Off):**
   - **$1,000 to $1,500** for citizens whose CPF balances are below the Basic Retirement Sum.
3. **MediSave Bonus (One-Off):**
   - **$750 to $1,500** credited directly into your MediSave account.
4. **Automatic Disbursement:**
   - No application is required. Eligibility is computed automatically based on CPF and IRAS records.

---
💡 *Ask me any question below about your eligibility cohort, income assessment, or CPF crediting dates!*`,
    relatedPolicyIds: ["cpf-sa-closure-ers", "medishield-life-2026"],
  },
  {
    id: "parliament-sitting-2026-08-05",
    title: "Parliament Sitting Digest: Ministerial Statements on Housing Classifications & Public Transport",
    headline: "Parliament Hansard Dispatch: MPs Debate BTO Plus/Prime Implementation, Transport Reliability & Workforce Support",
    category: "Parliament & Hansard",
    ministry: "Parliament of Singapore (Hansard Official Records)",
    publishedAt: "Parliament Sitting Digest",
    effectiveDate: "Sitting of 5 August 2026",
    status: "Active",
    badge: "Hansard Dispatch",
    summary:
      "Full debate synthesis of the Singapore Parliament sitting on 5 August 2026, covering ministerial statements on housing supply, public transport infrastructure, and workforce reskilling.",
    leadParagraph:
      "During the sitting on 5 August 2026, Parliament debated major policy motions including the rollout of the new Standard, Plus, and Prime BTO classification, public transport reliability enhancements, and expansions to SkillsFuture training allowances. Ministers responded to oral and written questions from Members of Parliament regarding cost of living and housing grant disbursement.",
    readTime: "5 min read / AI Consult",
    keyFacts: [
      { label: "Sitting Date", value: "5 August 2026", note: "Official Hansard Record" },
      { label: "Key Motions Debated", value: "Housing, Transport & Jobs", note: "Oral & Written Ministerial Answers" },
      { label: "Participating Ministries", value: "MND, MOT, MOM, MOF", note: "Ministerial Statements Delivered" },
      { label: "Hansard Transcript", value: "Verified Open Access", note: "Available via SPRS & YouTube Records" },
    ],
    officialSources: [
      {
        title: "Singapore Parliament Hansard Official Reports (SPRS)",
        url: "https://sprs.parl.gov.sg",
        authority: "Parliament of Singapore",
      },
      {
        title: "Official Parliament Sitting Video Broadcast",
        url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        authority: "Singapore Parliament Channel",
      },
    ],
    suggestedQuestions: [
      "What ministerial statements were delivered during the 5 August 2026 Parliament sitting?",
      "What did Members of Parliament raise regarding the new BTO Plus/Prime housing framework?",
      "Were there any updates discussed on public transport reliability and rail investments?",
      "How did MOM address questions about mid-career training allowances?",
    ],
    initialBriefing: `### 🏛️ Parliament Hansard Digest: Sitting of 5 August 2026

**Authority:** Parliament of Singapore & SPRS Official Records  
**Sitting Date:** 5 August 2026

#### 🔑 Key Debate Highlights:
1. **Public Housing & Singles BTO Rollout (MND):**
   - Minister for National Development addressed parliamentary questions on the launch of the new Standard, Plus, and Prime flat classification model.
   - Reaffirmed that eligible first-timer singles aged 35+ can now apply for 2-room Flexi BTO flats across all project types islandwide.
2. **Public Transport Infrastructure & Maintenance (MOT):**
   - Debated ongoing enhancements to MRT reliability, signalling renewals, and feeder bus connectivity.
3. **Mid-Career Support & SkillsFuture Expansion (MOM / MOE):**
   - Discussed uptake of the $4,000 SkillsFuture Credit top-up and criteria for the monthly training allowance of up to $3,000.

---
💡 *Ask me any question below about speeches, parliamentary questions, or specific ministerial replies during this sitting!*`,
    relatedPolicyIds: ["singles-bto-framework", "skillsfuture-levelup", "jobseeker-support-scheme"],
  },
];
