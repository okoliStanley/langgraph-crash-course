import os
import sys
import openai
import smtplib
import requests
import json
from email.message import EmailMessage
from pathlib import Path

# Load GitHub username (passed from GitHub Actions as env)
github_user = os.getenv("PR_USERNAME")
openai.api_key = os.getenv("OPENAI_API_KEY")
print(f"api key is {openai.api_key}")
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
                {"role": "user", "content": f"Review the following code and suggest improvements:\n\n{content}"}
            ]
        )
        suggestions = response['choices'][0]['message']['content']
    except Exception as e:
        print(response.status_code)
        print(f"❌ Failed to get LLM response for {filename}: {e}")
        continue

    summary_output.append(f"## Suggestions for `{filename}`\n\n{suggestions}\n")

    # post a seprate comment per file
    body = f"### LLM Review for `{filename}`\n\n{suggestions}"
    comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    res = requests.post(comment_url, headers=headers, json={"body": body})

    if res.status_code == 201:
        print(f"✅ Posted comment for {filename}")
    else:
        print(f"❌ Failed to post comment for {filename}. Status: {res.status_code}, Body: {res.text}")


# Combine and format as email
full_review = "\n\n".join(summary_output)

# Send email
def send_email(to_email, subject, body, sender="llm-bot@yourdomain.com"):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    with smtplib.SMTP("smtp.yourprovider.com", 587) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)

try:
    send_email(
        to_email=recipient_email,
        subject=f"LLM Code Review for PR by {github_user}",
        body=full_review
    )
    print(f"✅ Email sent to {recipient_email}")
except Exception as e:
    print(f"❌ Failed to send email: {e}")
