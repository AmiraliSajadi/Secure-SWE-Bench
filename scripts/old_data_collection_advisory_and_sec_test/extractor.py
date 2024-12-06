import argparse
import csv
import os
import re
import time

import requests
from dotenv import load_dotenv
from tqdm import tqdm


# Load environment variables
def load_env():
    load_dotenv()
    api_key = os.getenv("GITHUB_API_KEY")
    if not api_key:
        raise ValueError("GITHUB_API_KEY is missing. Please set it in the .env file.")
    return api_key


# Initialize GitHub session
def initialize_github_session(api_key):
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    return session


# Check and handle rate limits
def check_rate_limit(response):
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))

    if remaining == 0:
        reset_in = max(0, reset_time - int(time.time()))
        print(f"Rate limit reached. Pausing for {reset_in} seconds...")
        time.sleep(reset_in + 1)


# Prepare directories for the run
def prepare_directories(chosen_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_dir = os.path.join(base_dir, "../data", chosen_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


# Fetch pull requests for a repository
def fetch_pull_requests(repo_url, session, max_prs):
    prs_url = f"https://api.github.com/repos/{repo_url}/pulls"
    params = {"state": "closed", "per_page": 100}
    all_prs = []
    while prs_url and len(all_prs) < max_prs:
        response = session.get(prs_url, params=params)
        check_rate_limit(response)
        if response.status_code == 401:
            raise ValueError(
                f"Unauthorized access to {prs_url}. Check your GitHub API key."
            )
        response.raise_for_status()
        prs = response.json()
        all_prs.extend(prs)
        prs_url = response.links.get("next", {}).get("url")
        if len(all_prs) >= max_prs:
            break

    return all_prs[:max_prs]


# Check if a PR links to an issue and return its URL if found
def pr_links_to_issue(pr):
    patterns = [
        r"(fixes|closes|resolves)\s+#(\d+)",
        r"(fixes|closes|resolves)\s+(https://github.com/.+/issues/\d+)",
    ]
    # Ensure title and body are strings
    text = str(pr.get("title", "")) + " " + str(pr.get("body", ""))
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if "http" in match.group(0):
                return True, match.group(2)  # URL-based issue reference
            else:
                # Construct issue URL for local issue reference
                repo_url = pr["html_url"].split("/pull/")[0]
                issue_number = match.group(2)
                issue_url = f"{repo_url}/issues/{issue_number}"
                return True, issue_url
    return False, None


# Fetch list of changed files for a PR
def fetch_changed_files(pr, session):
    files_url = pr["url"] + "/files"
    response = session.get(files_url)
    check_rate_limit(response)
    response.raise_for_status()
    files = response.json()
    return [file["filename"] for file in files]


# Save data to CSV
def save_to_csv(data, csv_path):
    with open(csv_path, mode="a", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=data.keys())
        if csv_file.tell() == 0:  # Write header if the file is empty
            writer.writeheader()
        writer.writerow(data)


# Main function
def main():
    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="GitHub PR Data Extractor")
    parser.add_argument(
        "--chosen-name", required=True, help="Name for the output directory"
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        required=True,
        help="Maximum number of PRs per repository",
    )
    args = parser.parse_args()

    # Load API key and initialize session
    api_key = load_env()
    session = initialize_github_session(api_key)

    # Prepare directories
    run_dir = prepare_directories(args.chosen_name)
    csv_path = os.path.join(run_dir, "summary.csv")

    # Repositories to process
    repos = [
        # "public-apis/public-apis",
        # "donnemartin/system-design-primer",
        # "ranaroussi/quantstats",
        "django/django",
    ]

    for repo_url in repos:
        print(f"Processing repository: {repo_url}")
        prs = fetch_pull_requests(repo_url, session, args.max_prs)

        for pr in tqdm(prs, desc=f"Processing PRs in {repo_url}", unit="PR"):
            linked, issue_url = pr_links_to_issue(pr)

            # Fetch list of changed files
            changed_files = fetch_changed_files(pr, session)
            patched_files = ", ".join(changed_files)

            # Metadata
            data = {
                "repo": repo_url,
                "pr_title": pr["title"],
                "pr_url": pr["html_url"],
                "pr_body": pr.get("body", ""),
                "linked_issue_found": linked,
                "linked_issue_url": issue_url if linked else "",
                "patched_files": patched_files,
            }
            save_to_csv(data, csv_path)


if __name__ == "__main__":
    main()
