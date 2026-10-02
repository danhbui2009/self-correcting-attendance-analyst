# Portfolio description

**Self-Correcting Attendance Analyst — Python / LangGraph**

Built an evidence-grounded attendance analytics prototype that turns a bounded set of English and Vietnamese questions into deterministic metrics. A LangGraph workflow validates the request, reads a synthetic dataset through fixed read-only SQLite queries, calculates results in Python, and checks the supporting evidence before answering. The demo handles two-period comparisons, incomplete requests, empty periods, duplicate rows, and conflicting source records. When the evidence cannot support a reliable result, it asks for clarification or withholds the conclusion. A Streamlit interface shows the result, evidence summary, and completed workflow path. The project runs locally without production credentials or an API key; it is a portfolio prototype, not a production HR system.
