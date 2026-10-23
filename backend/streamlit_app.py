import os, requests, streamlit as st
from dotenv import load_dotenv
load_dotenv()
API = os.getenv("API_URL", "http://localhost:8000")
st.set_page_config(page_title="PaymentRuleGuard AI", page_icon="🛡️", layout="wide")
st.title("🛡️ PaymentRuleGuard AI")
st.caption("Deterministic Markdown rule mapping • LangGraph • xUnit • PR reviews")
tab1, tab2 = st.tabs(["🔍 PR Review", "📚 Rule Library"])
with tab1:
    path = st.text_input("Changed C# file", "src/Payments/PaymentService.cs")
    diff = st.text_area("Paste Git diff", "- if (amount <= 0)\n+ if (amount < 0)", height=180)
    if st.button("Review change", type="primary"):
        try:
            r = requests.post(API+"/review",json={"changed_paths":[path],"diff":diff},timeout=180)
            r.raise_for_status()
            data=r.json()
            st.markdown(data["review"])
            with st.expander("Mapped rules and tests"):
                st.json(data["evidence"])
        except requests.RequestException as e: st.error(str(e))
with tab2:
    if st.button("Load rule mapping"):
        try:
            r=requests.get(API+"/rules",timeout=15);r.raise_for_status()
            st.json(r.json())
        except requests.RequestException as e: st.error(str(e))
