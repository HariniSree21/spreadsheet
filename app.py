import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
import re
import os
import json  # Import the json module

# 🎯 Function to fetch data using LeetCode GraphQL API
def get_leetcode_stats(username):
    url = "https://leetcode.com/graphql"
    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/{username}/"
    }

    query = """
    query getUserProfile($username: String!) {
      matchedUser(username: $username) {
        submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
          }
        }
        profile {
          ranking
        }
      }
    }
    """

    payload = {
        "operationName": "getUserProfile",
        "variables": {"username": username},
        "query": query
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        try:
            user_data = data["data"]["matchedUser"]
            submissions = user_data["submitStatsGlobal"]["acSubmissionNum"]
            stats = {entry["difficulty"]: entry["count"] for entry in submissions}
            return stats
        except:
            return None
    else:
        return None

# 🔐 Google Sheets Auth
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Fetch credentials from the environment variable
json_str = st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]
json_data = json.loads(json_str)  # Parse the JSON data

creds = ServiceAccountCredentials.from_json_keyfile_dict(json_data, scope)
client = gspread.authorize(creds)

# 📝 UI
st.title("📊 LeetCode Stats Updater from Google Sheet")
st.markdown("""
### 📌 Instructions:

1. Ensure your Google Sheet contains a column with LeetCode profile links in this format:
https://leetcode.com/u/your_username/

2. Share your Google Sheet with this service account email:
spreadsheetapp-456811@spreadsheetapp-456811.iam.gserviceaccount.com

_(Click on share button to the right top of your google spreadsheet and add the above email)_

_(You must give Viewer or Editor access as per your requirements.)_

3. Paste your Google Sheet link below and follow the prompts.
""")

sheet_url = st.text_input("Enter your Google Sheet URL:")

if sheet_url:
    try:
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.sheet1
        data = worksheet.get_all_values()

        if not data:
            st.warning("Sheet is empty!")
        else:
            headers = data[0]
            rows = data[1:]

            st.success("✅ Sheet loaded successfully!")
            st.subheader("🔍 Select Column Mapping")
            gmail_col = st.selectbox("Select Gmail ID Column", headers)
            leetcode_col = st.selectbox("Select LeetCode Profile URL Column", headers)

            gmail_idx = headers.index(gmail_col)
            leetcode_idx = headers.index(leetcode_col)

            added_columns = ["Easy Solved", "Medium Solved", "Hard Solved", "Total Score"]

            # ➕ Add new headers if missing
            for col in added_columns:
                if col not in headers:
                    headers.append(col)
                    for row in rows:
                        row.append("")

            output_data = []
            for row in rows:
                gmail = row[gmail_idx].strip()
                leetcode_url = row[leetcode_idx].strip()

                # 🧠 Extract username from any valid URL
                match = re.search(r"leetcode\.com/u/([^/\s]+)/?", leetcode_url)
                leetcode_user = match.group(1) if match else ""

                if gmail and leetcode_user:
                    stats = get_leetcode_stats(leetcode_user)
                    if stats:
                        easy = stats.get("Easy", 0)
                        medium = stats.get("Medium", 0)
                        hard = stats.get("Hard", 0)
                        total_score = easy * 1 + medium * 2 + hard * 3

                        row[-4] = str(easy)
                        row[-3] = str(medium)
                        row[-2] = str(hard)
                        row[-1] = str(total_score)

                        output_data.append({
                            "Gmail": gmail,
                            "LeetCode": leetcode_user,
                            "Easy Solved": easy,
                            "Medium Solved": medium,
                            "Hard Solved": hard,
                            "Total Score": total_score
                        })

            st.subheader("📋 LeetCode Stats")
            df = pd.DataFrame(output_data)
            st.dataframe(df)

            if st.button("✅ Write Data to Google Sheet"):
                worksheet.update([headers] + rows)
                st.success("✅ Sheet updated successfully!")

    except Exception as e:
        error_message = str(e)
        if "The caller does not have permission" in error_message or "403" in error_message:
            st.error("🚫 It looks like your Google Sheet isn't shared with the service account.")
            st.markdown("""
            Please make sure you've shared the sheet with:

            **`spreadsheetapp-456811@spreadsheetapp-456811.iam.gserviceaccount.com`**

            _To do this: Open your Google Sheet → Click **Share** → Paste the email above → Click **Send**._
            """)
        else:
            st.error(f"❌ An unexpected error occurred: `{e}`")
