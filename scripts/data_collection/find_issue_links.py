import csv
import json
import os
import re

import requests
from dotenv import load_dotenv
from tqdm import tqdm  # Progress bar

# GitHub token (for authentication to avoid rate limits)
load_dotenv()

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {ACCESS_TOKEN}",
}

# Keywords to check in commit messages
KEYWORDS = {"closes", "fixes", "resolves"}


# Function to fetch commit messages from GitHub
def fetch_commit_message(commit_url, cache):
    if commit_url in cache:  # Use cached message if available
        return cache[commit_url]

    response = requests.get(commit_url, headers=HEADERS)
    if response.status_code == 200:
        commit_message = response.json().get("commit", {}).get("message", "")
        cache[commit_url] = commit_message  # Cache the result
        return commit_message
    else:
        print(
            f"Failed to fetch commit: {commit_url}, Status Code: {response.status_code}"
        )
        return ""


# Function to check if a commit message contains issue references with keywords
def check_issue_reference(commit_message):
    # Remove Markdown-style comments
    commit_message = re.sub(r"<!--.*?-->", "", commit_message, flags=re.DOTALL)
    # Regex to find "word #number"
    pattern = r"\b(\w+)\s+#(\d+)"
    matches = re.findall(pattern, commit_message)
    # Check if any word before #number matches the keywords
    for word, _ in matches:
        if word.lower() in KEYWORDS:
            return True
    return False


# Main function to process the JSON file and generate a CSV
def process_json_to_csv(json_file, output_csv):
    # Load the JSON file
    with open(json_file, "r") as f:
        data = json.load(f)

    # Cache to avoid redundant API calls
    commit_cache = {}

    # Prepare CSV rows
    rows = []
    for first_hash, second_hash in tqdm(data, desc="Processing commits"):
        commit_url = f"https://api.github.com/repos/django/django/commits/{second_hash}"
        commit_message = fetch_commit_message(commit_url, commit_cache)
        contains_issue_reference = check_issue_reference(commit_message)
        rows.append([first_hash, second_hash, commit_message, contains_issue_reference])

    # Write to CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            ["First Hash", "Second Hash", "Commit Message", "Contains Issue Reference"]
        )
        writer.writerows(rows)

    print(f"CSV saved to {output_csv}")


# Example Usage
json_file = "../../../SZZUnleashed/szz/results/fix_and_introducers_pairs.json"  # Replace with your JSON file
output_csv = "output.csv"  # Replace with your desired output CSV file
process_json_to_csv(json_file, output_csv)
