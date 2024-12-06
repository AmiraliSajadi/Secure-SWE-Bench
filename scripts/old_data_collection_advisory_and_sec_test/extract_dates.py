import ast  # To parse string representations of lists
import json
import os
from datetime import datetime

import pandas as pd
import urllib3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {ACCESS_TOKEN}",
}

http = urllib3.PoolManager()


def make_request(url, params=None):
    """
    Generic function to make an API request to GitHub
    """
    print(f"Fetching URL: {url} with params: {params}")
    response = http.request("GET", url, headers=headers, fields=params)
    print(f"Received response with status: {response.status}")
    if response.status == 200:
        return json.loads(response.data.decode("utf-8"))
    else:
        raise Exception(f"Failed to fetch data: Status {response.status}")


def extract_commit_date(commit_url):
    """
    Fetch the commit date for a specific commit URL
    """
    try:
        parts = commit_url.split("/")
        owner, repo, sha = parts[3], parts[4], parts[6]

        # API endpoint for commit
        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
        commit_data = make_request(api_url)

        # Extract and format the commit date
        commit_date = commit_data["commit"]["committer"]["date"]
        formatted_date = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%Y-%m-%d %H:%M:%S +0000"
        )
        return sha, formatted_date

    except Exception as e:
        print(f"Error fetching date for {commit_url}: {e}")
        return None, None


def fetch_commit_dates(commit_urls):
    """
    Fetch and return commit dates and hashes for a list of commit URLs
    """
    commit_data_list = []
    for commit_url in commit_urls:
        sha, commit_date = extract_commit_date(commit_url)
        if sha and commit_date:
            commit_data_list.append(
                {
                    "Commit URL": commit_url,
                    "Commit Hash": sha,
                    "Commit Date": commit_date,
                }
            )
    return commit_data_list


def read_commit_links_from_xlsx(file_path):
    """
    Read a .xlsx file containing commit links in a column and extract the links
    """
    try:
        df = pd.read_csv(file_path)
        commit_links = []

        for links_str in df["Commit Links"]:
            if isinstance(links_str, str):
                # Parse the string representation of the list
                links = ast.literal_eval(links_str)
                commit_links.extend(links)

        return commit_links

    except Exception as e:
        print(f"Error reading commit links from file: {e}")
        return []


def save_commit_dates_to_csv(commit_data_list, output_file):
    """
    Save fetched commit dates and hashes to a CSV file
    """
    try:
        df = pd.DataFrame(commit_data_list)
        df.to_csv(output_file, index=False)
        print(f"Commit data saved to {output_file}")
    except Exception as e:
        print(f"Error saving commit data to file: {e}")


if __name__ == "__main__":
    # Input and output file paths
    input_file = "django_security_advisories.csv"  # Update with the path to your input .xlsx file
    output_file = "django_commit_data.csv"

    # Step 1: Read commit links from the input file
    commit_links = read_commit_links_from_xlsx(input_file)

    if not commit_links:
        print("No commit links found in the input file.")
    else:
        print(f"Found {len(commit_links)} commit links.")

        # Step 2: Fetch commit dates and hashes
        commit_data_list = fetch_commit_dates(commit_links)

        # Step 3: Save commit data to a CSV file
        save_commit_dates_to_csv(commit_data_list, output_file)
