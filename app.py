"""VA Site Walk Network Dashboard — Streamlit Cloud Edition

Reads from bundled SQLite database (no external DB required).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="VA Site Walk Network",
    page_icon="\U0001f1fa\U0001f1f8",  # US flag
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- VA / patriotic color palette ----
VA_BLUE = "#002B5C"      # VA flagship blue
VA_RED = "#C8102E"       # VA flagship red
VA_GOLD = "#FFC72C"      # Accent
USA_PALETTE = [VA_BLUE, VA_RED, VA_GOLD, "#4A7FA7", "#7A1F2B", "#F2F2F2"]

# ---- Community contribution config ----
GITHUB_ISSUES_URL = "https://github.com/tredding-wq/va-sitewalk-dashboard/issues/new"


def _suggest_fix_url(kind: str, identifier: str, payload: dict) -> str:
    """Build a pre-filled GitHub Issue URL for a row-level correction."""
    from urllib.parse import urlencode
    title = f"Fix: {kind} — {identifier}"
    lines = [f"**Record type:** {kind}", f"**Identifier:** {identifier}", ""]
    lines.append("**Current data:**")
    lines.append("```")
    for k, v in payload.items():
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        lines.append(f"{k}: {v}")
    lines.append("```")
    lines.extend([
        "",
        "**What's wrong?**",
        "<!-- e.g. wrong category, duplicate of another row, OCR misread name, missing JV partner -->",
        "",
        "**What should it be?**",
        "<!-- e.g. correct legal name, correct category, link to merge into id=XXXX -->",
        "",
        "**Source / evidence (URL or note):**",
        "<!-- e.g. company website, LinkedIn page, SAM.gov record -->",
    ])
    body = "\n".join(lines)
    qs = urlencode({"title": title, "body": body, "labels": "data-correction"})
    return f"{GITHUB_ISSUES_URL}?{qs}"

st.markdown(
    f"""
    <style>
    /* Patriotic top banner */
    .va-hero {{
        background: linear-gradient(135deg, {VA_BLUE} 0%, {VA_BLUE} 42%, {VA_RED} 58%, {VA_RED} 100%) !important;
        color: white !important;
        padding: 2rem 2.25rem !important;
        border-radius: 12px !important;
        margin-bottom: 1.25rem !important;
        box-shadow: 0 6px 18px rgba(0,0,0,0.22) !important;
        border-top: 4px solid {VA_GOLD} !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 2.5rem !important;
        flex-wrap: wrap !important;
        font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    }}
    /* Force every text node inside the hero to inherit the same font */
    .va-hero, .va-hero * {{
        font-family: inherit !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}
    /* Compound selector beats the generic stMarkdownContainer h1 rule */
    div[data-testid="stMarkdownContainer"] .va-hero h1 {{
        color: white !important;
        margin: 0 !important;
        font-size: 2.2rem !important;
        letter-spacing: 0.5px !important;
        font-weight: 800 !important;
        line-height: 1.15 !important;
    }}
    /* Inline-SVG flag — renders identically on every platform (Windows's
       Segoe UI Emoji has no flag glyphs, so the regional-indicator emoji
       falls back to plain "US" text there). */
    .va-hero h1 .flag {{
        display: inline-block;
        width: 1.55em;
        height: 1em;
        vertical-align: -0.06em;
        margin-right: 0.42em;
        border-radius: 2px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.35);
    }}
    div[data-testid="stMarkdownContainer"] .va-hero p.tagline {{
        color: #E8F0FA !important;
        margin: 0.4rem 0 0 0 !important;
        font-size: 1.08rem !important;
        line-height: 1.45 !important;
        max-width: 560px;
    }}
    .va-hero__left {{ flex: 2 1 520px; min-width: 0; }}
    .va-hero__stats {{
        display: flex; flex-wrap: wrap; gap: 0.4rem 1.2rem;
        margin-top: 1rem; font-size: 0.95rem;
        color: rgba(255,255,255,0.95) !important;
    }}
    .va-hero__stats .stat {{
        display: inline-flex; align-items: baseline; gap: 0.35rem;
    }}
    .va-hero__stats .stat b {{
        color: {VA_GOLD} !important;
        font-size: 1.15rem; font-weight: 800;
        letter-spacing: 0.3px;
    }}
    .va-hero__stats .dot {{ color: rgba(255,255,255,0.45) !important; }}

    .va-hero__cta {{
        flex: 1 1 300px; max-width: 360px;
        display: flex; flex-direction: column; align-items: stretch;
        gap: 0.7rem;
        padding: 1.15rem 1.25rem;
        background: rgba(255,255,255,0.12) !important;
        border: 1px solid rgba(255,255,255,0.28) !important;
        border-radius: 10px;
    }}
    .va-hero__cta .eyebrow {{
        color: {VA_GOLD} !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.16em !important;
        text-transform: uppercase !important;
        margin: 0 !important;
    }}
    .va-hero__cta .ask {{
        color: #FFFFFF !important;
        font-size: 0.97rem !important;
        line-height: 1.45 !important;
        margin: 0 !important;
    }}
    .va-hero__cta .ask strong {{ color: {VA_GOLD} !important; }}
    .va-hero__cta a.donate-btn {{
        display: block; text-align: center;
        background: white !important;
        color: {VA_RED} !important;
        padding: 0.75rem 1.1rem !important;
        border-radius: 7px !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        text-decoration: none !important;
        letter-spacing: 0.4px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.18);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .va-hero__cta a.donate-btn:hover {{
        transform: translateY(-1px);
        box-shadow: 0 5px 12px rgba(0,0,0,0.25);
    }}
    .va-hero__cta .fineprint {{
        color: rgba(255,255,255,0.6) !important;
        font-size: 0.7rem !important;
        line-height: 1.4 !important;
        margin: 0 !important;
    }}
    .va-stripe {{
        height: 6px !important;
        background: repeating-linear-gradient(90deg,
            {VA_RED} 0 40px, white 40px 80px, {VA_BLUE} 80px 120px) !important;
        margin: 0.5rem 0 1rem 0 !important; border-radius: 3px !important;
    }}
    /* Metric accent — multiple selector fallbacks for different Streamlit versions */
    [data-testid="stMetricValue"], [data-testid="stMetric"] > div > div:nth-child(2),
    div[data-testid="metric-container"] > div:nth-child(2) {{
        color: {VA_BLUE} !important; font-weight: 800 !important;
    }}
    [data-testid="stMetricLabel"], [data-testid="stMetric"] label,
    div[data-testid="metric-container"] label {{
        color: {VA_RED} !important; font-weight: 700 !important;
        text-transform: uppercase !important; letter-spacing: 0.08em !important; font-size: 0.78rem !important;
    }}
    /* Sidebar — make it navy */
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div,
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {VA_BLUE} 0%, #001a3a 100%) !important;
    }}
    section[data-testid="stSidebar"] *,
    [data-testid="stSidebar"] * {{ color: white !important; }}
    section[data-testid="stSidebar"] h1 {{
        color: white !important;
        border-bottom: 3px solid {VA_RED} !important;
        padding-bottom: 0.5rem !important;
    }}
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stRadio label p {{
        color: white !important; font-weight: 600 !important;
    }}
    /* H1/H2 on main area gets blue accent underline */
    div[data-testid="stMarkdownContainer"] h2 {{
        color: {VA_BLUE} !important;
        border-bottom: 2px solid {VA_RED} !important;
        padding-bottom: 0.25rem !important;
        margin-top: 1.5rem !important;
    }}
    /* Main page title */
    div[data-testid="stMarkdownContainer"] h1 {{
        color: {VA_BLUE} !important;
    }}
    /* Metric container — add subtle border */
    [data-testid="stMetric"], div[data-testid="metric-container"] {{
        background: #F7FAFD !important;
        border-left: 4px solid {VA_RED} !important;
        padding: 0.75rem 1rem !important;
        border-radius: 6px !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

DB_PATH = Path(__file__).parent / "signin_ocr.sqlite"


def get_conn():
    return sqlite3.connect(str(DB_PATH))


def query(sql: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def scalar(sql: str) -> int:
    conn = get_conn()
    cur = conn.execute(sql)
    val = cur.fetchone()[0]
    conn.close()
    return val


# ------------------------------------------------------------------ #
#  Data loaders
# ------------------------------------------------------------------ #

def _facility_type(name: str) -> str:
    if not isinstance(name, str):
        return "Other"
    n = name.lower()
    if "community living center" in n:
        return "Community Living Center"
    if "domiciliary" in n:
        return "Domiciliary"
    if "mobile vet center" in n:
        return "Mobile Vet Center"
    if "vet center" in n:
        return "Vet Center"
    if "mobile clinic" in n:
        return "Mobile Clinic"
    if "medical center" in n:
        return "Medical Center"
    if "clinic" in n:
        return "Clinic"
    return "Other"


@st.cache_data(ttl=300)
def load_sites():
    df = query("""
        SELECT vs.station_number, vs.station_name, vs.parent_station, vs.visn,
               vs.city, vs.state, vs.zip, vs.street1, vs.phone, vs.category_id,
               vs.latitude, vs.longitude,
               COALESCE(p.cnt, 0) AS project_count,
               COALESCE(a.cnt, 0) AS attendee_count
        FROM va_sites vs
        LEFT JOIN (SELECT station_number, COUNT(*) cnt FROM projects
                   WHERE station_number IS NOT NULL GROUP BY station_number) p
            ON p.station_number = vs.station_number
        LEFT JOIN (SELECT station_number, COUNT(*) cnt FROM attendee_sites
                   GROUP BY station_number) a
            ON a.station_number = vs.station_number
        ORDER BY (COALESCE(p.cnt,0) + COALESCE(a.cnt,0)) DESC, vs.station_number
    """)
    df["facility_type"] = df["station_name"].apply(_facility_type)
    return df


@st.cache_data(ttl=300)
def load_projects():
    return query("""
        SELECT p.id, p.project_number, p.project_title, p.program, p.status,
               p.station_number,
               COALESCE(vs.station_name, p.facility) AS site_name,
               COALESCE(vs.city, p.city) AS site_city,
               COALESCE(vs.state, p.state) AS site_state,
               COALESCE(vs.visn, p.visn) AS visn,
               s.solicitation_count, s.solicitation_numbers,
               t.latest_status, t.total_sheets, t.total_attendees_extracted,
               t.site_visit_dates, ap.unique_attendees,
               p.first_seen_date, p.last_seen_date
        FROM projects p
        LEFT JOIN va_sites vs ON vs.station_number = p.station_number
        LEFT JOIN (
            SELECT project_id,
                   COUNT(DISTINCT solicitation) AS solicitation_count,
                   GROUP_CONCAT(DISTINCT solicitation) AS solicitation_numbers
            FROM (
                SELECT project_id, solicitation_number AS solicitation
                  FROM project_tracker
                 WHERE project_id IS NOT NULL
                   AND COALESCE(cancelled, 0) = 0
                   AND TRIM(COALESCE(solicitation_number, '')) != ''
                UNION
                SELECT project_id, solicitation
                  FROM ehrm_solicitations
                 WHERE project_id IS NOT NULL
                   AND COALESCE(cancelled, 0) = 0
                   AND TRIM(COALESCE(solicitation, '')) != ''
            )
            GROUP BY project_id
        ) s ON s.project_id = p.id
        LEFT JOIN (
            SELECT project_id, MAX(status) latest_status,
                   SUM(sheets_found) total_sheets,
                   SUM(attendees_extracted) total_attendees_extracted,
                   GROUP_CONCAT(DISTINCT site_visit_date) site_visit_dates
            FROM project_tracker WHERE project_id IS NOT NULL GROUP BY project_id
        ) t ON t.project_id = p.id
        LEFT JOIN (
            SELECT project_id, COUNT(DISTINCT attendee_id) unique_attendees
            FROM attendee_projects GROUP BY project_id
        ) ap ON ap.project_id = p.id
        ORDER BY p.project_number
    """)


@st.cache_data(ttl=300)
def load_attendees():
    return query("""
        SELECT ka.id, ka.name, ka.email, ka.organization, ka.title, ka.phone,
               ka.times_seen, ka.site_walks_attended,
               s.sites_visited, s.stations_visited,
               pj.projects_attended, pj.project_numbers,
               ka.first_seen_site, ka.last_seen_site, ka.last_seen,
               kc.canonical_name AS company
        FROM known_attendees ka
        LEFT JOIN known_companies kc ON kc.id = ka.company_id
        LEFT JOIN (
            SELECT ats.attendee_id, COUNT(*) sites_visited,
                   GROUP_CONCAT(vs.station_name || ' (' || vs.station_number || ')',
                                '; ') stations_visited
            FROM attendee_sites ats
            JOIN va_sites vs ON vs.station_number = ats.station_number
            GROUP BY ats.attendee_id
        ) s ON s.attendee_id = ka.id
        LEFT JOIN (
            SELECT ap.attendee_id, COUNT(*) projects_attended,
                   GROUP_CONCAT(p.project_number, ', ') project_numbers
            FROM attendee_projects ap
            JOIN projects p ON p.id = ap.project_id
            GROUP BY ap.attendee_id
        ) pj ON pj.attendee_id = ka.id
        ORDER BY ka.times_seen DESC
    """)


@st.cache_data(ttl=300)
def load_companies():
    # VA Staff / USACE / Other Government attend every sitewalk by definition
    # (it's their sitewalk), so they'd dominate every list. Filter at the
    # source so they never appear on the public companies view or charts.
    #
    # JV/rep-network children (rollup_parent_id IS NOT NULL) are folded into
    # their parent's sheets_with_jvs / reps_with_jvs counts and hidden from the
    # public list to avoid double-counting -- e.g. Leviton's rep firms roll up
    # to Leviton's totals, Richard Group's JVs roll up to Richard Group LLC.
    return query("""
        SELECT kc.id, kc.canonical_name, kc.primary_category,
               COALESCE(NULLIF(kc.sheets_with_jvs, 0), kc.times_seen) AS times_seen,
               kc.email_domains, kc.website, kc.sam_uei, kc.sam_cage,
               kc.primary_naics, kc.certifications, kc.last_seen,
               COALESCE(kc.is_sdvosb_va_prime, 0) AS sdvosb_prime,
               kc.va_prime_total_obligated, kc.va_prime_award_count,
               kc.sites_visited_text AS sites_list
        FROM known_companies kc
        WHERE kc.primary_category NOT IN ('VA Staff', 'USACE', 'Other Government')
          AND kc.rollup_parent_id IS NULL
        ORDER BY COALESCE(NULLIF(kc.sheets_with_jvs, 0), kc.times_seen) DESC
    """)


@st.cache_data(ttl=300)
def load_summary():
    return {
        "va_sites": scalar("SELECT COUNT(*) FROM va_sites"),
        "projects": scalar("SELECT COUNT(*) FROM projects"),
        "project_tracker": scalar("""
            SELECT COUNT(DISTINCT solicitation) FROM (
                SELECT solicitation_number AS solicitation FROM project_tracker
                 WHERE COALESCE(cancelled,0)=0
                   AND TRIM(COALESCE(solicitation_number,''))!=''
                UNION
                SELECT solicitation FROM ehrm_solicitations
                 WHERE COALESCE(cancelled,0)=0
                   AND TRIM(COALESCE(solicitation,''))!=''
            )
        """),
        "known_attendees": scalar("SELECT COUNT(*) FROM known_attendees"),
        "known_companies": scalar("SELECT COUNT(*) FROM known_companies"),
        "attendee_sites": scalar("SELECT COUNT(*) FROM attendee_sites"),
        "attendee_projects": scalar("SELECT COUNT(*) FROM attendee_projects"),
        "sdvosb_primes": scalar("SELECT COUNT(*) FROM known_companies WHERE is_sdvosb_va_prime = 1"),
        "with_website": scalar("SELECT COUNT(*) FROM known_companies WHERE website IS NOT NULL AND website != ''"),
        "with_uei": scalar("SELECT COUNT(*) FROM known_companies WHERE sam_uei IS NOT NULL AND sam_uei != ''"),
    }


@st.cache_data(ttl=300)
def load_jv_members():
    return query("""
        SELECT jvm.jv_company_id, jvc.canonical_name AS jv_name,
               jvm.member_name, jvm.member_role, jvm.source, jvm.confidence,
               mc.canonical_name AS member_company
        FROM jv_members jvm
        JOIN known_companies jvc ON jvc.id = jvm.jv_company_id
        LEFT JOIN known_companies mc ON mc.id = jvm.member_company_id
        ORDER BY jvc.canonical_name
    """)


# ------------------------------------------------------------------ #
#  Sidebar
# ------------------------------------------------------------------ #
st.sidebar.title("VA Site Walk Network")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Sites",
    "Projects",
    "Attendees",
    "Companies",
    "Joint Ventures",
    "About",
])

st.sidebar.markdown(
    f"""
    <div style="
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255,255,255,0.15);
    ">
        <div style="
            color: rgba(255,255,255,0.6) !important;
            font-size: 0.72rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        ">Help improve this</div>
        <a href="{GITHUB_ISSUES_URL}?labels=feedback&title=Feedback%3A&body=%3C%21--%20What%20would%20you%20like%20to%20see%20fixed%2C%20added%2C%20or%20improved%3F%20--%3E"
           target="_blank" rel="noopener"
           style="
               display: block;
               color: white !important;
               text-decoration: none;
               padding: 0.5rem 0.7rem;
               font-size: 0.88rem;
               font-weight: 600;
               border-left: 3px solid {VA_GOLD};
               margin-bottom: 0.4rem;
           ">
            🛠️ Report an issue / suggest a fix &rarr;
        </a>
        <a href="https://github.com/tredding-wq/va-sitewalk-dashboard"
           target="_blank" rel="noopener"
           style="
               display: block;
               color: white !important;
               text-decoration: none;
               padding: 0.4rem 0.7rem;
               font-size: 0.82rem;
               font-weight: 500;
               border-left: 3px solid rgba(255,255,255,0.3);
               margin-bottom: 1.2rem;
           ">
            🐙 GitHub repo &rarr;
        </a>
    </div>
    <div style="
        padding-top: 0.6rem;
        border-top: 1px solid rgba(255,255,255,0.15);
    ">
        <div style="
            color: rgba(255,255,255,0.6) !important;
            font-size: 0.72rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        ">Support</div>
        <a href="https://www.woundedwarriorproject.org/donate"
           target="_blank" rel="noopener"
           style="
               display: block;
               color: white !important;
               text-decoration: none;
               padding: 0.5rem 0;
               font-size: 0.88rem;
               font-weight: 600;
               border-left: 3px solid {VA_RED};
               padding-left: 0.7rem;
           ">
            Wounded Warrior Project &rarr;
        </a>
        <div style="
            color: rgba(255,255,255,0.5) !important;
            font-size: 0.72rem;
            margin-top: 0.6rem;
            padding-left: 0.7rem;
            line-height: 1.4;
        ">
            Open source · Not affiliated with WWP or VA
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ #
#  Overview
# ------------------------------------------------------------------ #
if page == "Overview":
    s = load_summary()
    attendees = f"{s.get('known_attendees', 0):,}"
    projects_n = f"{s.get('projects', 0):,}"
    solicits = f"{s.get('project_tracker', 0):,}"
    sites_n = f"{s.get('va_sites', 0):,}"

    st.markdown(
        f"""
        <div class="va-hero">
            <div class="va-hero__left">
                <h1><svg class="flag" viewBox="0 0 39 26" xmlns="http://www.w3.org/2000/svg" aria-label="US flag" role="img"><rect width="39" height="26" fill="#B22234"/><rect y="2" width="39" height="2" fill="#fff"/><rect y="6" width="39" height="2" fill="#fff"/><rect y="10" width="39" height="2" fill="#fff"/><rect y="14" width="39" height="2" fill="#fff"/><rect y="18" width="39" height="2" fill="#fff"/><rect y="22" width="39" height="2" fill="#fff"/><rect width="16" height="14" fill="#3C3B6E"/><g fill="#fff"><circle cx="2.5" cy="2.5" r="0.6"/><circle cx="6" cy="2.5" r="0.6"/><circle cx="9.5" cy="2.5" r="0.6"/><circle cx="13" cy="2.5" r="0.6"/><circle cx="4.25" cy="5" r="0.6"/><circle cx="7.75" cy="5" r="0.6"/><circle cx="11.25" cy="5" r="0.6"/><circle cx="2.5" cy="7.5" r="0.6"/><circle cx="6" cy="7.5" r="0.6"/><circle cx="9.5" cy="7.5" r="0.6"/><circle cx="13" cy="7.5" r="0.6"/><circle cx="4.25" cy="10" r="0.6"/><circle cx="7.75" cy="10" r="0.6"/><circle cx="11.25" cy="10" r="0.6"/><circle cx="2.5" cy="12.5" r="0.6"/><circle cx="6" cy="12.5" r="0.6"/><circle cx="9.5" cy="12.5" r="0.6"/><circle cx="13" cy="12.5" r="0.6"/></g></svg>VA Site Walk Network</h1>
                <p class="tagline">Building smart spaces for those who took care of us.</p>
                <div class="va-hero__stats">
                    <span class="stat"><b>{projects_n}</b> Projects</span>
                    <span class="dot">&middot;</span>
                    <span class="stat"><b>{solicits}</b> Solicitations</span>
                    <span class="dot">&middot;</span>
                    <span class="stat"><b>{attendees}</b> Attendees</span>
                    <span class="dot">&middot;</span>
                    <span class="stat"><b>{sites_n}</b> VA Facilities</span>
                </div>
            </div>
            <div class="va-hero__cta">
                <div class="eyebrow">Open Source &middot; For Veterans</div>
                <div class="ask">
                    This dashboard is <strong>free and open</strong>.
                    If it helps your work, please give back to the veterans it serves.
                </div>
                <a class="donate-btn"
                   href="https://www.woundedwarriorproject.org/donate"
                   target="_blank" rel="noopener">
                    Donate to Wounded Warrior Project &rarr;
                </a>
                <div class="fineprint">
                    WWP is an independent 501(c)(3). Not affiliated with this
                    dashboard or the U.S. Dept. of Veterans Affairs.
                </div>
            </div>
        </div>
        <div class="va-stripe"></div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VA Sites", f"{s['va_sites']:,}")
    c2.metric("Projects", s['projects'])
    c3.metric("Attendees", f"{s['known_attendees']:,}")
    c4.metric("Companies", f"{s['known_companies']:,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Solicitations", s['project_tracker'])
    c6.metric("Site-Attendee Links", f"{s['attendee_sites']:,}")
    c7.metric("SDVOSB Primes", s['sdvosb_primes'])
    c8.metric("With UEI", s['with_uei'])

    st.markdown('<div class="va-stripe"></div>', unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Projects by State")
        projects = load_projects()
        if not projects.empty and "site_state" in projects.columns:
            state_counts = projects.dropna(subset=["site_state"]).groupby("site_state").size().reset_index(name="count")
            fig = px.choropleth(
                state_counts, locations="site_state", locationmode="USA-states",
                color="count", scope="usa",
                color_continuous_scale=[[0, "#E8F0FA"], [0.5, VA_BLUE], [1, VA_RED]],
                labels={"count": "Projects", "site_state": "State"},
            )
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350,
                              geo=dict(bgcolor="rgba(0,0,0,0)", lakecolor="white"))
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Top Companies by Sheet Appearances")
        companies = load_companies()
        if not companies.empty:
            top = companies.head(15)[["canonical_name", "times_seen", "primary_category"]]
            fig = px.bar(top, x="times_seen", y="canonical_name", orientation="h",
                         color="primary_category", color_discrete_sequence=USA_PALETTE,
                         labels={"times_seen": "Sheets", "canonical_name": ""},
                         height=350)
            fig.update_layout(yaxis=dict(autorange="reversed"),
                              margin=dict(l=0, r=0, t=0, b=0),
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                              legend=dict(orientation="h", y=-0.15, title=""))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Category Breakdown")
    if not companies.empty:
        cat_counts = companies.groupby("primary_category").size().reset_index(name="count")
        cat_counts = cat_counts.sort_values("count", ascending=False)
        fig = px.bar(cat_counts, x="count", y="primary_category", orientation="h", height=500,
                     color="count", color_continuous_scale=[[0, VA_BLUE], [1, VA_RED]],
                     labels={"count": "Companies", "primary_category": ""})
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False, coloraxis_showscale=False,
                          margin=dict(l=0, r=0, t=0, b=0),
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------ #
#  Sites
# ------------------------------------------------------------------ #
elif page == "Sites":
    st.title("VA Sites Directory")
    df = load_sites()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        visn_filter = st.multiselect("Filter by VISN", sorted(df["visn"].dropna().unique()))
    with col2:
        state_filter = st.multiselect("Filter by State", sorted(df["state"].dropna().unique()))
    with col3:
        type_filter = st.multiselect("Filter by Type", sorted(df["facility_type"].dropna().unique()))
    with col4:
        show_with_projects = st.checkbox("Only sites with projects", value=False)

    if visn_filter:
        df = df[df["visn"].isin(visn_filter)]
    if state_filter:
        df = df[df["state"].isin(state_filter)]
    if type_filter:
        df = df[df["facility_type"].isin(type_filter)]
    if show_with_projects:
        df = df[df["project_count"] > 0]

    st.metric("Showing", f"{len(df)} sites")

    map_df = df.dropna(subset=["latitude", "longitude"])
    map_df = map_df[(map_df["latitude"] != 0) & (map_df["longitude"] != 0)]
    if not map_df.empty:
        fig = px.scatter_geo(
            map_df, lat="latitude", lon="longitude",
            hover_name="station_name",
            hover_data=["station_number", "facility_type", "city", "state", "visn", "project_count", "attendee_count"],
            size=map_df["project_count"].clip(lower=1),
            size_max=10,
            color="project_count",
            color_continuous_scale=[[0, "#A9C1DC"], [1, VA_BLUE]],
            scope="usa", height=450,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                          geo=dict(bgcolor="rgba(0,0,0,0)", lakecolor="white"))
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df[["station_number", "station_name", "facility_type", "city", "state", "visn",
            "project_count", "attendee_count", "phone", "street1"]],
        use_container_width=True, height=500,
    )


# ------------------------------------------------------------------ #
#  Projects
# ------------------------------------------------------------------ #
elif page == "Projects":
    st.title("EHRM Projects Directory")
    df = load_projects()

    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("Search (project #, site, title)")
    with col2:
        status_filter = st.multiselect("Project Status", sorted(df["status"].dropna().unique()))

    if status_filter:
        df = df[df["status"].isin(status_filter)]
    if search:
        mask = df.apply(lambda r: search.lower() in str(r).lower(), axis=1)
        df = df[mask]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projects", len(df))
    c2.metric("Total Solicitations", int(df["solicitation_count"].fillna(0).sum()))
    c3.metric("Total Attendees", int(df["unique_attendees"].fillna(0).sum()))
    c4.metric("Sign-in Sheets", int(df["total_sheets"].fillna(0).sum()))

    st.dataframe(
        df[["project_number", "site_name", "site_city", "site_state", "visn",
            "program", "status", "solicitation_count", "unique_attendees",
            "total_sheets", "total_attendees_extracted", "solicitation_numbers",
            "site_visit_dates"]],
        use_container_width=True, height=600,
    )

    if not df.empty:
        st.subheader("Project Detail")
        selected = st.selectbox("Select project", df["project_number"].tolist())
        if selected:
            proj = df[df["project_number"] == selected].iloc[0]
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Project:** {proj['project_number']}")
                st.markdown(f"**Title:** {proj.get('project_title', '')}")
                st.markdown(f"**Site:** {proj.get('site_name', '')} ({proj.get('site_city', '')}, {proj.get('site_state', '')})")
                st.markdown(f"**VISN:** {proj.get('visn', '')}")
            with col_b:
                st.markdown(f"**Solicitations:** {proj.get('solicitation_numbers', '')}")
                st.markdown(f"**Site Visit Dates:** {proj.get('site_visit_dates', '')}")
                st.markdown(f"**Unique Attendees:** {int(proj.get('unique_attendees', 0) or 0)}")
                st.markdown(f"**Sheets Processed:** {int(proj.get('total_sheets', 0) or 0)}")


# ------------------------------------------------------------------ #
#  Attendees
# ------------------------------------------------------------------ #
elif page == "Attendees":
    st.title("Attendee Directory")
    df = load_attendees()

    # Compute derived columns first
    df["company_display"] = df["company"].fillna(df["organization"])
    df["sites_display"] = df["sites_visited"].fillna(0).astype(int)
    no_sites = (df["sites_display"] == 0) & (df["stations_visited"].isna() | (df["stations_visited"] == ""))
    has_first = no_sites & df["first_seen_site"].notna() & (df["first_seen_site"] != "")
    df.loc[has_first, "sites_display"] = 1
    df.loc[has_first, "stations_visited"] = df.loc[has_first, "first_seen_site"]

    search = st.text_input("Search (name, email, org)")
    if search:
        mask = df.apply(lambda r: search.lower() in str(r).lower(), axis=1)
        df = df[mask]

    c1, c2 = st.columns(2)
    c1.metric("Attendees", len(df))
    c2.metric("Multi-site (2+)", int((df["sites_display"] >= 2).sum()))

    att_event = st.dataframe(
        df[["name", "email", "company_display", "times_seen",
            "sites_display", "stations_visited", "last_seen"]],
        use_container_width=True, height=600,
        on_select="rerun",
        selection_mode="single-row",
        key="attendees_df",
        column_config={
            "company_display": st.column_config.TextColumn("Company"),
            "times_seen": st.column_config.NumberColumn("Seen", format="%d"),
            "sites_display": st.column_config.NumberColumn("Sites", format="%d"),
            "stations_visited": st.column_config.TextColumn("Sites Visited", width="large"),
        },
    )

    sel = att_event.selection.rows if att_event and att_event.selection else []
    if sel:
        row = df.iloc[sel[0]]
        with st.container(border=True):
            hl, hr = st.columns([4, 1])
            with hl:
                st.markdown(f"### {row['name']} — {row.get('company_display') or '(no company)'}")
            with hr:
                fix_url = _suggest_fix_url(
                    "Attendee",
                    row["name"],
                    {
                        "id": int(row["id"]) if "id" in row and not pd.isna(row.get("id")) else None,
                        "name": row.get("name"),
                        "email": row.get("email"),
                        "organization": row.get("organization"),
                        "company": row.get("company_display"),
                        "times_seen": int(row["times_seen"]) if not pd.isna(row.get("times_seen")) else None,
                    },
                )
                st.link_button("🛠️ Suggest a fix", fix_url, use_container_width=True)
            st.caption(
                f"Email: {row.get('email') or '—'}  ·  "
                f"Sheets seen: {int(row.get('times_seen') or 0)}  ·  "
                f"Sites: {int(row.get('sites_display') or 0)}"
            )
            stations = row.get("stations_visited") or ""
            if stations:
                st.markdown("**Sites visited:**  " + stations)

    st.subheader("Top Multi-Site Attendees")
    multi = df[df["sites_display"] >= 2].sort_values("sites_display", ascending=False).head(20)
    if not multi.empty:
        fig = px.bar(multi, x="sites_display", y="name", orientation="h",
                     color="organization", height=500,
                     labels={"sites_visited": "Sites Visited"})
        fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------ #
#  Companies
# ------------------------------------------------------------------ #
elif page == "Companies":
    st.title("Company Directory")
    df = load_companies()

    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("Search company")
    with col2:
        cat_filter = st.multiselect("Category", sorted(df["primary_category"].dropna().unique()))
    with col3:
        sdvosb_only = st.checkbox("SDVOSB VA Primes only")

    if search:
        mask = df["canonical_name"].str.contains(search, case=False, na=False)
        df = df[mask]
    if cat_filter:
        df = df[df["primary_category"].isin(cat_filter)]
    if sdvosb_only:
        df = df[df["sdvosb_prime"] == 1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies", len(df))
    c2.metric("SDVOSB Primes", int(df["sdvosb_prime"].sum()))
    c3.metric("With Website", int(df["website"].notna().sum()))
    c4.metric("With UEI", int(df["sam_uei"].notna().sum() if "sam_uei" in df else 0))

    # Derive compact sites count from semicolon-separated sites_list
    df["sites_count"] = df["sites_list"].fillna("").apply(
        lambda s: len([x for x in s.split(";") if x.strip()]) if s else 0
    )

    event = st.dataframe(
        df[["canonical_name", "primary_category", "times_seen", "sites_count",
            "sdvosb_prime", "website", "sam_uei",
            "certifications", "email_domains", "last_seen"]],
        use_container_width=True, height=600,
        on_select="rerun",
        selection_mode="single-row",
        key="companies_df",
        column_config={
            "canonical_name": st.column_config.TextColumn("Company", width="large"),
            "times_seen": st.column_config.NumberColumn(
                "Seen",
                help="VA sign-in sheets this company appears on. For manufacturers and prime GCs, includes their rep network / JV partner attendance.",
                format="%d",
            ),
            "sites_count": st.column_config.NumberColumn(
                "Sites",
                help="Distinct VA facilities visited (includes rep network / JV partners). Click a row to see the full list.",
                format="%d",
            ),
            "sdvosb_prime": st.column_config.CheckboxColumn("SDVOSB"),
            "website": st.column_config.LinkColumn(
                "Website",
                display_text=r"https?://(?:www\.)?([^/]+).*",
            ),
        },
    )

    # Detail panel: show full Sites Visited list for the selected row
    selected_rows = event.selection.rows if event and event.selection else []
    if selected_rows:
        idx = selected_rows[0]
        row = df.iloc[idx]
        with st.container(border=True):
            header_l, header_r = st.columns([4, 1])
            with header_l:
                st.markdown(f"### {row['canonical_name']}  —  Sites Visited")
            with header_r:
                fix_url = _suggest_fix_url(
                    "Company",
                    row["canonical_name"],
                    {
                        "id": int(row["id"]) if "id" in row and not pd.isna(row.get("id")) else None,
                        "canonical_name": row.get("canonical_name"),
                        "primary_category": row.get("primary_category"),
                        "times_seen": int(row["times_seen"]) if not pd.isna(row.get("times_seen")) else None,
                        "website": row.get("website"),
                        "email_domains": row.get("email_domains"),
                        "sam_uei": row.get("sam_uei"),
                    },
                )
                st.link_button("🛠️ Suggest a fix", fix_url, use_container_width=True)
            sites_txt = row.get("sites_list") or ""
            sites = sorted({s.strip() for s in sites_txt.split(";") if s.strip()})
            if not sites:
                st.caption("No sitewalk records linked to this company yet.")
            else:
                st.caption(f"{len(sites)} distinct VA facilities")
                ncols = 2 if len(sites) > 6 else 1
                cols = st.columns(ncols)
                for i, s in enumerate(sites):
                    cols[i % ncols].markdown(f"- {s}")

    if sdvosb_only and not df.empty and "va_prime_total_obligated" in df.columns:
        st.subheader("SDVOSB VA Prime Award Volume")
        top_primes = df.dropna(subset=["va_prime_total_obligated"]).sort_values(
            "va_prime_total_obligated", ascending=False).head(20)
        if not top_primes.empty:
            fig = px.bar(top_primes, x="va_prime_total_obligated", y="canonical_name",
                         orientation="h", labels={"va_prime_total_obligated": "Total Obligated ($)"},
                         height=500)
            fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------ #
#  Joint Ventures
# ------------------------------------------------------------------ #
elif page == "Joint Ventures":
    st.title("Joint Venture Relationships")
    jvs = load_jv_members()
    companies = load_companies()

    jv_companies = companies[
        companies["canonical_name"].str.contains(r"JV|Joint Venture|J\.V\.", case=False, na=False)
    ]

    st.metric("JV Entities", len(jv_companies))
    st.metric("Resolved Member Links", len(jvs))

    if not jvs.empty:
        st.subheader("Resolved JV Members")
        st.dataframe(
            jvs[["jv_name", "member_name", "member_company", "member_role", "source", "confidence"]],
            use_container_width=True, height=300,
        )

    st.subheader("All JV Entities")
    st.dataframe(
        jv_companies[["canonical_name", "primary_category", "times_seen",
                       "website", "sam_uei", "email_domains"]],
        use_container_width=True, height=400,
    )


# ------------------------------------------------------------------ #
#  About
# ------------------------------------------------------------------ #
elif page == "About":
    st.title("About VA Sitewalk")
    st.markdown(
        f"""
        <div style="
            display: inline-block;
            background: linear-gradient(135deg, {VA_BLUE} 0%, {VA_RED} 100%);
            color: white;
            padding: 0.65rem 1.2rem;
            border-radius: 8px;
            font-size: 1.05rem;
            font-weight: 600;
            line-height: 1.4;
            margin: 0.4rem 0 1.2rem 0;
            box-shadow: 0 3px 8px rgba(0,0,0,0.18);
            border-left: 4px solid {VA_GOLD};
        ">
            An open-source project to make construction projects run more smoothly &mdash; and to connect the best people in the industry.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # ---------- Mission ----------
    st.header("Our mission")
    st.markdown(
        """
Construction runs on relationships. The best superintendents, subs, reps, and
vendors are known to the people who've worked with them — and invisible to
everyone else.

**VA Sitewalk** exists to change that. It's an open-source tool that takes the
handwritten sign-in sheets from pre-bid site walks on VA construction projects
and turns them into a shared, searchable directory of the firms and
professionals who actually show up and do the work.

We believe that better information in the hands of the people building America's
veterans hospitals makes for smoother projects, fairer competition, and stronger
connections across the industry.
        """
    )

    # ---------- What you can do ----------
    st.header("What you can do here")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🔍 Discover")
        st.markdown(
            """
            Search contractors, subs, and reps by trade, region, or VA facility.
            Find the firms that consistently pursue and deliver VA healthcare
            construction work.
            """
        )

    with col2:
        st.subheader("🤝 Connect")
        st.markdown(
            """
            See who's walking the same jobs you are. Reach out to potential
            partners, subs, or GCs before bid day — not after award.
            """
        )

    with col3:
        st.subheader("📈 Contribute")
        st.markdown(
            """
            Upload site walk sheets from projects you've attended. Every
            contribution makes the directory better for the whole industry.
            """
        )

    st.divider()

    # ---------- How it works ----------
    st.header("How it works")
    st.markdown(
        """
1. **Sign-in sheets come in** as scanned PDFs — from solicitation archives,
   user uploads, or FOIA releases.
2. **OCR extracts** names, companies, trades, and contact info using Google
   Cloud Vision, tuned for handwriting.
3. **Entity resolution** cross-references each firm against SAM.gov and
   broader web sources to clean up misspellings and merge duplicates.
4. **The directory grows** — searchable by anyone, free forever.
        """
    )

    # ---------- Open source ----------
    st.header("Open source, by design")
    st.markdown(
        """
This project is open source because the construction industry deserves shared
infrastructure, not another walled garden. The code, the pipeline, and the
directory are all public.

- **Use it** to find partners, subs, or reps for your next VA project
- **Fork it** to build similar tools for other agencies or sectors
- **Improve it** by submitting site walk sheets, corrections, or pull requests

We welcome contributions from GCs, subs, manufacturers, reps, architects,
engineers, owners, and anyone else who wants construction to work better.
        """
    )

    # ---------- Scope ----------
    st.header("Current scope")
    st.markdown(
        """
- **Projects:** VA construction and EHRM infrastructure work
- **Documents:** Pre-bid and pre-construction site walk sign-in sheets
- **Geography:** Nationwide, growing as contributions come in

Other agencies and project types are on the roadmap — contributions
accelerate that timeline.
        """
    )

    # ---------- Data caveats (prominent) ----------
    st.header("⚠️ Data caveats — please read")

    st.warning(
        "VA Site Walk Network is a best-effort tool built from public sign-in "
        "sheets. Treat the directory as a starting point for research, not as a "
        "system of record. If something looks off, use the Suggest a fix link on "
        "any row."
    )

    with st.expander("📝 OCR is imperfect", expanded=True):
        st.markdown(
            """
            Sign-in sheets are handwritten — often in pen, on a clipboard, at a
            site walk in the rain. No OCR engine reads handwriting perfectly.

            - Names, companies, phone numbers, and emails may contain **transcription errors**
            - The pipeline runs multiple OCR passes and falls back through several
              engines to reduce error rate
            - When a name looks suspicious (e.g. *"Tallow Construction"* vs the real
              *"Tallon Construction"*) it gets cross-checked against public sources
              before being merged
            - **Some errors will still slip through** — when you spot one, the
              "Suggest a fix" button on any row pre-fills a GitHub issue with the
              record's data so corrections are easy
            """
        )

    with st.expander("🏷️ Categories are best-effort", expanded=True):
        st.markdown(
            """
            Each company is tagged with a primary category (General Contractor,
            Electrical, Low Voltage, Manufacturer, Manufacturer Rep, Distributor,
            etc.) based on a mix of SAM.gov NAICS codes and AI classification
            against public sources. These are **directional, not authoritative**.

            - A firm tagged "Electrical Contractor" may also do low-voltage,
              controls, or other scopes
            - NAICS codes on SAM.gov are self-reported and often broader than a
              firm's actual day-to-day work
            - Multi-trade firms appear under a single primary category — secondary
              capabilities aren't surfaced today
            - The **Manufacturer Rep** category is reserved for actual rep firms
              representing specific product lines (e.g. Leviton's rep network),
              not distributors like Anixter / WESCO / Graybar / Accu-Tech, which
              get the **Distributor** tag

            Use categories to narrow a search — then verify capabilities directly
            with the firm.
            """
        )

    with st.expander("🧮 How rollup logic works", expanded=True):
        st.markdown(
            """
            A single real-world company can show up on site walk sheets under many
            variations: *"Richard Group,"* *"Richard Group LLC,"* *"RICHARD GROUP,"*
            *"Bridger-National Richard Group JV."* The directory rolls those up so
            you see one row, with the full history attached. Here's how:

            **Match on shared identifiers (high confidence)**
            Rows that share a SAM.gov UEI, an email domain, or a website are
            collapsed into one entity.

            **Fuzzy name match with online verification (medium confidence)**
            Near-duplicate names are checked against public sources before being
            merged. The system won't merge based on name similarity alone —
            there has to be an external source confirming the match.

            **JV and rep-network rollups**
            For prime contractors (like Richard Group LLC) and manufacturers (like
            Leviton), affiliated JV partners and rep firms roll up under the
            parent so the prime gets credit for its network's site walk
            attendance — without the JV row itself disappearing from the data.

            **What this means for you:**
            - One company = one row, with all variant sign-ins folded together
            - Attendance counts use distinct sign-in sheets (no double-counting)
            - **False merges and false splits both happen** — the "Suggest a fix"
              link on any row is the fastest way to get them corrected
            """
        )

    with st.expander("📅 Coverage is uneven"):
        st.markdown(
            """
            The directory only contains what's been ingested. Coverage depends on
            which sign-in sheets we (and contributors) have been able to source.

            - Some VAMCs and regions are well-represented; others have no coverage yet
            - Absence from the directory does **not** mean a firm doesn't work on VA projects
            - Presence does **not** guarantee current activity — check the most recent
              site walk date on each record
            """
        )

    with st.expander("🔒 Privacy and contact info"):
        st.markdown(
            """
            Names, phone numbers, and emails on this dashboard came from public
            pre-bid site walk sign-in sheets that are part of federal solicitation
            records on SAM.gov.

            - Entity verification cross-checks records against publicly available
              sources (company websites, public business registries, government
              contract records). It does not scrape data behind logins.
            - Individuals can request removal at any time
            - If you believe a record violates your privacy, use the "Suggest a
              fix" link or the sidebar's "Report an issue" link and the record
              will be removed
            """
        )

    st.divider()

    # ---------- Principles ----------
    st.header("Principles")
    st.markdown(
        """
- **Accuracy over volume.** Suspect rows are cross-checked against public
  sources before being merged or reclassified — no name-only guesses.
- **Respect for the people in the data.** Contact info is published as it
  appeared on public sign-in sheets; removal requests are honored.
- **Free and open.** No paywalls, no gated features, no data resale.
- **Industry-first.** Decisions are made with working contractors and
  vendors in mind — not investors.
        """
    )

    st.divider()

    # ---------- Giving back ----------
    st.header("Giving back to those who took care of us")
    st.markdown(
        """
This project exists because of VA construction — work that ultimately builds
the smart spaces caring for the veterans who took care of us. It feels right
to give something back.

**A portion of any revenue or donations this project receives goes to the
[Wounded Warrior Project](https://www.woundedwarriorproject.org/)**, which
supports injured post-9/11 veterans and their families.

If VA Sitewalk saves you time or helps you land a project, consider donating
to Wounded Warrior Project directly. The veterans who will one day be treated
in the hospitals we build together deserve our support.
        """
    )

    st.divider()

    # ---------- Get involved ----------
    st.header("Get involved")
    st.markdown(
        """
- 📤 **Upload a sign-in sheet** you attended
- 🐙 **Star or fork the repo** on GitHub
- ✉️ **Submit corrections** on any directory entry
- 💬 **Tell a colleague** — the directory is only as strong as the community
        """
    )

    st.caption(
        "VA Sitewalk is an independent open-source project. "
        "Not affiliated with or endorsed by the U.S. Department of Veterans Affairs."
    )


