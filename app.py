"""VA Site Walk Intelligence Dashboard — Streamlit Cloud Edition

Reads from bundled SQLite database (no external DB required).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="VA Site Walk Intelligence",
    page_icon="\U0001f3d7\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
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

@st.cache_data(ttl=300)
def load_sites():
    return query("""
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


@st.cache_data(ttl=300)
def load_projects():
    return query("""
        SELECT p.id, p.project_number, p.project_title, p.program, p.status,
               p.station_number, vs.station_name AS site_name,
               vs.city AS site_city, vs.state AS site_state, vs.visn,
               t.solicitation_count, t.solicitation_numbers,
               t.latest_status, t.total_sheets, t.total_attendees_extracted,
               t.site_visit_dates, ap.unique_attendees,
               p.first_seen_date, p.last_seen_date
        FROM projects p
        LEFT JOIN va_sites vs ON vs.station_number = p.station_number
        LEFT JOIN (
            SELECT project_id, COUNT(*) solicitation_count,
                   GROUP_CONCAT(solicitation_number, ', ') solicitation_numbers,
                   MAX(status) latest_status,
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
    return query("""
        SELECT kc.id, kc.canonical_name, kc.primary_category, kc.times_seen,
               kc.email_domains, kc.website, kc.sam_uei, kc.sam_cage,
               kc.primary_naics, kc.certifications, kc.last_seen,
               COALESCE(kc.is_sdvosb_va_prime, 0) AS sdvosb_prime,
               kc.va_prime_total_obligated, kc.va_prime_award_count,
               (SELECT COUNT(*) FROM known_attendees WHERE company_id = kc.id) AS attendee_count,
               cs.sites_count, cs.sites_list
        FROM known_companies kc
        LEFT JOIN (
            SELECT ka.company_id,
                   COUNT(DISTINCT ats.station_number) AS sites_count,
                   GROUP_CONCAT(DISTINCT vs.station_name || ' (' || vs.city || ')') AS sites_list
            FROM known_attendees ka
            JOIN attendee_sites ats ON ats.attendee_id = ka.id
            JOIN va_sites vs ON vs.station_number = ats.station_number
            WHERE ka.company_id IS NOT NULL
            GROUP BY ka.company_id
        ) cs ON cs.company_id = kc.id
        ORDER BY kc.times_seen DESC
    """)


@st.cache_data(ttl=300)
def load_pipeline_stats():
    return query("SELECT * FROM pipeline_runs ORDER BY id DESC")


@st.cache_data(ttl=300)
def load_summary():
    return {
        "va_sites": scalar("SELECT COUNT(*) FROM va_sites"),
        "projects": scalar("SELECT COUNT(*) FROM projects"),
        "project_tracker": scalar("SELECT COUNT(*) FROM project_tracker"),
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
st.sidebar.title("VA Site Walk Intel")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Sites",
    "Projects",
    "Attendees",
    "Companies",
    "Joint Ventures",
    "Pipeline Runs",
])


# ------------------------------------------------------------------ #
#  Overview
# ------------------------------------------------------------------ #
if page == "Overview":
    st.title("VA Site Walk Intelligence Dashboard")
    s = load_summary()

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

    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Projects by State")
        projects = load_projects()
        if not projects.empty and "site_state" in projects.columns:
            state_counts = projects.dropna(subset=["site_state"]).groupby("site_state").size().reset_index(name="count")
            fig = px.choropleth(
                state_counts, locations="site_state", locationmode="USA-states",
                color="count", scope="usa", color_continuous_scale="Blues",
                labels={"count": "Projects", "site_state": "State"},
            )
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Top Companies by Appearances")
        companies = load_companies()
        if not companies.empty:
            top = companies.head(15)[["canonical_name", "times_seen", "primary_category"]]
            fig = px.bar(top, x="times_seen", y="canonical_name", orientation="h",
                         color="primary_category", labels={"times_seen": "Times Seen"},
                         height=350)
            fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Category Breakdown")
    if not companies.empty:
        cat_counts = companies.groupby("primary_category").size().reset_index(name="count")
        cat_counts = cat_counts.sort_values("count", ascending=False)
        fig = px.bar(cat_counts, x="count", y="primary_category", orientation="h", height=500,
                     color="primary_category", labels={"count": "Companies"})
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False,
                          margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------ #
#  Sites
# ------------------------------------------------------------------ #
elif page == "Sites":
    st.title("VA Sites Directory")
    df = load_sites()

    col1, col2, col3 = st.columns(3)
    with col1:
        visn_filter = st.multiselect("Filter by VISN", sorted(df["visn"].dropna().unique()))
    with col2:
        state_filter = st.multiselect("Filter by State", sorted(df["state"].dropna().unique()))
    with col3:
        show_with_projects = st.checkbox("Only sites with projects", value=False)

    if visn_filter:
        df = df[df["visn"].isin(visn_filter)]
    if state_filter:
        df = df[df["state"].isin(state_filter)]
    if show_with_projects:
        df = df[df["project_count"] > 0]

    st.metric("Showing", f"{len(df)} sites")

    map_df = df.dropna(subset=["latitude", "longitude"])
    map_df = map_df[(map_df["latitude"] != 0) & (map_df["longitude"] != 0)]
    if not map_df.empty:
        fig = px.scatter_geo(
            map_df, lat="latitude", lon="longitude",
            hover_name="station_name",
            hover_data=["station_number", "city", "state", "visn", "project_count", "attendee_count"],
            size=map_df["project_count"].clip(lower=1) * 3,
            color="project_count", color_continuous_scale="YlOrRd",
            scope="usa", height=450,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df[["station_number", "station_name", "city", "state", "visn",
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

    search = st.text_input("Search (name, email, org)")

    if search:
        mask = df.apply(lambda r: search.lower() in str(r).lower(), axis=1)
        df = df[mask]

    c1, c2 = st.columns(2)
    c1.metric("Attendees", len(df))
    c2.metric("Multi-site (2+)", int((df["sites_visited"].fillna(0) >= 2).sum()))

    df["company_display"] = df["company"].fillna(df["organization"])
    st.dataframe(
        df[["name", "email", "company_display", "times_seen",
            "sites_visited", "stations_visited", "last_seen"]],
        use_container_width=True, height=600,
        column_config={
            "company_display": st.column_config.TextColumn("Company"),
            "times_seen": st.column_config.NumberColumn("Seen", format="%d"),
            "sites_visited": st.column_config.NumberColumn("Sites", format="%d"),
            "stations_visited": st.column_config.TextColumn("Sites Visited", width="large"),
        },
    )

    st.subheader("Top Multi-Site Attendees")
    multi = df[df["sites_visited"].fillna(0) >= 2].sort_values("sites_visited", ascending=False).head(20)
    if not multi.empty:
        fig = px.bar(multi, x="sites_visited", y="name", orientation="h",
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

    st.dataframe(
        df[["canonical_name", "primary_category", "times_seen", "attendee_count",
            "sites_count", "sites_list", "sdvosb_prime", "website", "sam_uei",
            "certifications", "email_domains", "last_seen"]],
        use_container_width=True, height=600,
        column_config={
            "canonical_name": st.column_config.TextColumn("Company", width="large"),
            "times_seen": st.column_config.NumberColumn("Seen", format="%d"),
            "attendee_count": st.column_config.NumberColumn("Reps", format="%d"),
            "sites_count": st.column_config.NumberColumn("Sites", format="%d"),
            "sites_list": st.column_config.TextColumn("Sites Visited", width="large"),
            "sdvosb_prime": st.column_config.CheckboxColumn("SDVOSB"),
            "website": st.column_config.LinkColumn("Website",
                display_text=r"https?://(?:www\.)?([^/]+).*"),
        },
    )

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
        companies["canonical_name"].str.contains("JV|Joint Venture|J\.V\.", case=False, na=False)
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
#  Pipeline Runs
# ------------------------------------------------------------------ #
elif page == "Pipeline Runs":
    st.title("Pipeline Run History")
    df = load_pipeline_stats()

    if df.empty:
        st.info("No pipeline runs recorded.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Runs", len(df))
        c2.metric("Total Files", int(df["files_processed"].sum()))
        c3.metric("Total Attendees", int(df["total_attendees"].sum()))

        st.dataframe(df, use_container_width=True, height=400)

        if len(df) > 1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df["id"], y=df["total_attendees"], name="Attendees"))
            fig.add_trace(go.Bar(x=df["id"], y=df["validated_count"], name="Validated"))
            fig.add_trace(go.Bar(x=df["id"], y=df["needs_review_count"], name="Needs Review"))
            fig.update_layout(barmode="group", xaxis_title="Run ID", yaxis_title="Count",
                              height=350, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
