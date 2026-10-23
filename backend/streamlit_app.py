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
        if not path.strip() or not diff.strip():
            st.warning("Enter a changed file path and a diff before reviewing.")
        else:
            try:
                with st.spinner("Reviewing your change with the AI model… The first local review can take several minutes."):
                    r = requests.post(
                        API + "/review",
                        json={"changed_paths": [path.strip()], "diff": diff},
                        timeout=(10, 600),
                    )
                    r.raise_for_status()
                    data = r.json()
                st.success("Review complete")
                st.markdown(data["review"])
                with st.expander("Mapped rules and tests"):
                    st.json(data["evidence"])
            except requests.Timeout:
                st.error("The review timed out while waiting for the model. Check the backend and Ollama logs, or try a smaller model.")
            except requests.ConnectionError:
                st.error("Cannot connect to the review API. Check that the backend container is running and healthy.")
            except requests.HTTPError as e:
                try:
                    detail = e.response.json().get("detail", "The review API returned an error.")
                except (ValueError, AttributeError):
                    detail = "The review API returned an error. Check the backend logs."
                st.error(detail)
            except requests.RequestException as e:
                st.error(f"The review request failed: {e}. Check the backend and Ollama logs for details.")
with tab2:
    if st.button("Load rule mapping"):
        try:
            r=requests.get(API+"/rules",timeout=15);r.raise_for_status()
            st.json(r.json())
        except requests.RequestException as e: st.error(str(e))
