# Sru & Aaku Expenses

A shared expense tracker for UPI swipes and credit card spends, built with Streamlit.

- Add an expense with a date, item, amount, tag, who spent it and how it was paid (UPI or credit card).
- Amounts accept sums, for example `650 + 1300`.
- Tags: Food, Food - Swiggy, Food - Restaurant, Grocery, Snacks, Other, plus any tag you add with **+ New tag**.
- Rows are colour coded: green for Sru, blue for Aaku.
- "Total as of today", a total for each person, a total for each tag, and a month filter.
- Edit or delete entries from the "Edit or delete entries" panel.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | The Streamlit screen |
| `ledger.py` | Amount parsing, totals, formatting (no Streamlit) |
| `storage.py` | SQLite and Postgres storage (no Streamlit) |
| `tests/test_ledger.py` | Unit tests for the two modules above |
| `requirements.txt` | Python packages |
| `.streamlit/config.toml` | Theme and Streamlit options |
| `.streamlit/secrets.toml.example` | Template for the secrets described below |

## Run it on your computer

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Without any settings it stores data in a local file, `expenses.db`.

Run the tests with `python -m unittest discover -s tests`.

## Deploy on streamlit.io (Community Cloud)

### 1. Put the files on GitHub

```bash
git init
git add .
git commit -m "Expense tracker"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

Keep `app.py` at the top level of the repository, next to `requirements.txt`.

### 2. Create a free hosted database

Streamlit Community Cloud wipes local files whenever an app restarts or is redeployed, so a SQLite file would lose your expenses. Use a hosted Postgres database instead. Both of these have free plans:

- **Supabase**: create a project, then open the project's **Connect** dialog and copy the connection string. Pick the *Session pooler* string, because Streamlit Cloud connects over IPv4 and Supabase's direct connection may be IPv6 only.
- **Neon**: create a project and copy the connection string from the dashboard.

The string looks like `postgresql://user:password@host:5432/dbname`. Replace the `[YOUR-PASSWORD]` placeholder with your real database password.

The app creates its own tables the first time it runs.

### 3. Deploy

1. Sign in to Streamlit Community Cloud with GitHub and choose **Create app**.
2. Pick your repository, the `main` branch and `app.py` as the main file.
3. Open **Advanced settings** and paste into **Secrets**:

   ```toml
   database_url = "postgresql://USER:PASSWORD@HOST:5432/postgres"
   app_password = "choose-something-long"
   ```

4. Click **Deploy**.

### Keep your finances private

A deployed app is reachable by anyone who has its URL. Do one of these:

- Set `app_password` in the secrets, as above. The app then asks for it before showing anything.
- Or restrict the app's viewers to specific email addresses in its sharing settings on Streamlit Cloud.

Never commit `.streamlit/secrets.toml` (it is already in `.gitignore`).

## Settings

Set these in Streamlit secrets or as environment variables (upper case, for example `DATABASE_URL`).

| Setting | Default | Meaning |
| --- | --- | --- |
| `database_url` | none | Postgres connection string. Without it the app uses SQLite. |
| `app_password` | none | Ask for this password before showing the ledger. |
| `timezone` | `Asia/Kolkata` | Used for today's date and "Total as of". |
| `seed_sample_data` | `true` | On a brand-new empty database, load the nine UPI entries from the original spreadsheet once. |

Environment variable `LEDGER_DB` changes the SQLite file path (default `expenses.db`).
