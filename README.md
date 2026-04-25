# ⇄ Tableau Report Comparator

A professional Streamlit app to compare two Tableau Excel exports **line by line, column by column** — with colour-coded diffs and one-click export.

---

## 🚀 Deploy in 5 Minutes (Free — Streamlit Cloud)

### Step 1 — Push to GitHub
1. Create a new GitHub repo (e.g. `tableau-comparator`)
2. Upload both files:
   - `app.py`
   - `requirements.txt`

### Step 2 — Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io) — sign in with GitHub
2. Click **"New app"**
3. Select your repo → branch: `main` → Main file: `app.py`
4. Click **Deploy**

✅ You get a free public URL like:
`https://your-name-tableau-comparator.streamlit.app`

---

## 💻 Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

---

## ✨ Features

| Feature | Details |
|---|---|
| **File support** | .xlsx, .xls, .csv |
| **Multi-sheet** | All sheets compared, each in its own tab |
| **Cell-level diff** | Modified 🔴, Added 🟢, Removed 🟡, Match ⚪ |
| **Summary metrics** | Total modified / added / removed / matching |
| **Ignore case** | Toggle on/off |
| **Trim whitespace** | Toggle on/off |
| **Numeric tolerance** | 0, ±0.001, ±0.01, ±0.1, ±1.0 |
| **Diff-only view** | Hide matching rows to focus on changes |
| **Export to Excel** | Full colour-coded workbook + Summary sheet |
| **Export to CSV** | Diffs-only CSV export |

---

## 🗂️ Project Structure

```
tableau-comparator/
├── app.py            # Main Streamlit app
├── requirements.txt  # Python dependencies
└── README.md
```

---

## 🔒 Privacy

All comparison logic runs entirely on the server — no data is sent to any third party. When self-hosted, your Excel files never leave your infrastructure.
