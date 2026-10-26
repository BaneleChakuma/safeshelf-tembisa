"""The community dashboard: the store scoreboard and this week's problems on a web page. Issue #27.

Start it with `python -m safeshelf dashboard` (it runs `streamlit run` on this file).

The page connects as the safeshelf_community role for the whole time (db.community_connection),
so PostgreSQL refuses anything the community may not see: no truck data, no names, no report text.
"""

from datetime import date

import streamlit as st

from safeshelf import db, reports, settings

st.set_page_config(page_title="SafeShelf Tembisa", page_icon="🛒", layout="wide")


@st.cache_resource
def connection(url: str):
    """One connection per database address, kept between page refreshes."""
    return db.community_connection(url)


conn = connection(settings.database_url())
if conn.broken or conn.closed:  # the database restarted: connect again
    connection.clear()
    conn = connection(settings.database_url())

st.title("SafeShelf Tembisa")
st.markdown("Where food is checked and safe. Only findings a committee member checked are counted.")

latest = reports.latest_day(conn)
if latest is None:
    st.info("There's no data yet. Run the pipeline first: `python -m safeshelf run`.")
    st.stop()

day = st.sidebar.date_input("Show the day", value=latest, max_value=max(latest, date.today()))
st.sidebar.caption(f"The latest data is from {latest}.")

st.header("Store scoreboard")
st.markdown(f"The last {settings.SCOREBOARD_DAYS} days up to **{day}**. 100 is best.")
scoreboard = reports.store_scoreboard(conn, day)
st.dataframe(
    scoreboard,
    hide_index=True,
    column_config={
        "rank": "Rank", "store": "Store", "section": "Section", "checks_done": "Checks done",
        "shelf_problems": "Shelf problems", "verified_reports": "Verified reports",
        "near_expiry_items": "Near-expiry deliveries",
        "score": st.column_config.NumberColumn("Score", format="%d", help="Empty: nobody has checked this store yet"),
    },
)
st.caption("A store without a score hasn't been checked yet, so nobody can say it's safe. "
           "How the score works: docs/REPORTS.md.")

st.header("This week's problems")
st.markdown(f"Verified problems in the {settings.PROBLEMS_DAYS} days up to **{day}**, newest first.")
problems = reports.community_problems(conn, day)
st.dataframe(
    problems,
    hide_index=True,
    column_config={"day": "Day", "store": "Store", "section": "Section", "problem": "Problem",
                   "how_many": "How many"},
)
if not problems:
    st.success("No verified problems this week.")

st.caption("Saw a problem in a store? Tell your committee member. Reports are anonymous.")
