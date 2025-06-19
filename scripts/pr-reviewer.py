import os
import sys
import openai
import requests
import json
from pathlib import Path

# Load GitHub username (passed from GitHub Actions as env)
github_user = os.getenv("PR_USERNAME")
openai.api_key = os.getenv("OPENAI_API_KEY")
pr_number = os.getenv("PR_NUMBER")
repo = os.getenv("GITHUB_REPOSITORY")
github_token = os.getenv("GITHUB_TOKEN")

script_dir = Path(__file__).resolve().parent
email_file = script_dir / "user_email_map.json"

# Load email mapping
with open(email_file, "r") as f:
    email_map = json.load(f)

recipient_email = email_map.get(github_user)

if not recipient_email:
    print(f"No email found for GitHub user '{github_user}'. Skipping email.")
    sys.exit(0)

file_paths = sys.argv[1:]

headers = {
    "Authorization": f"Bearer {github_token}",
    "Accept": "application/vnd.github+json"
}

summary_output = []

for path in file_paths:
    print(f"Reviewing: {path}")
    filename = os.path.basename(path)

    try:
        with open(path.strip(), 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ Could not read {filename}: {e}")
        continue

    try:    # get review from LLM
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You're a senior software engineer optimizing code for readability and performance."},
                {"role": "user", "content": f"Review the following code and suggest improvements:\n\n{content}\n\n "}
            ]
        )

        if response.choices and response.choices[0].message:
            suggestions = response.choices[0].message.content
        else:
            raise ValueError("No suggestions returned from OpenAI.")

    except Exception as e:        
        print(f"❌ Failed to get LLM response for {filename}: {e}")
        continue

    summary_output.append(f"## Suggestions for `{filename}`\n\n{suggestions}\n")

    
if summary_output:
    full_body = (
        f"## 🤖 LLM Code Review Summary for PR #{pr_number} by @{github_user}\n\n"
        + "\n---\n".join(summary_output)
    )

    comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    res = requests.post(comment_url, headers=headers, json={"body": full_body})

    if res.status_code == 201:
        print("✅ Posted consolidated LLM review comment.")
    else:
        print(f"❌ Failed to post consolidated comment. Status: {res.status_code}, Body: {res.text}")
else:
    print("ℹ️ No suggestions to post.")