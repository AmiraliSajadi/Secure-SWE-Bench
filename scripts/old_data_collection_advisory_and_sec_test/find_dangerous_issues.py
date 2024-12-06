import csv
import os
import time

import requests
from dotenv import load_dotenv
from tqdm import tqdm


# Load environment variables
def load_env():
    load_dotenv()
    return os.getenv("GITHUB_API_KEY")


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
    original_dir = os.path.join(run_dir, "original")
    patched_dir = os.path.join(run_dir, "patched")
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(patched_dir, exist_ok=True)
    return run_dir, original_dir, patched_dir


# Fetch issues for a repository
def fetch_issues(repo_url, session):
    issues_url = f"https://api.github.com/repos/{repo_url}/issues"
    params = {"state": "closed", "per_page": 100}
    all_issues = []
    page_count = 0

    with tqdm(desc=f"Retrieving issues from {repo_url}", unit="page") as pbar:
        while issues_url:
            response = session.get(issues_url, params=params)
            check_rate_limit(response)
            response.raise_for_status()
            issues = response.json()
            all_issues.extend(issues)
            issues_url = response.links.get("next", {}).get("url")
            page_count += 1
            pbar.update(1)

    return all_issues


# Fetch commits linked to an issue
def fetch_commits(issue, repo_url, session):
    issue_number = issue["number"]
    url = f"https://api.github.com/repos/{repo_url}/issues/{issue_number}/timeline"
    params = {"per_page": 100}
    response = session.get(url, params=params)
    check_rate_limit(response)
    response.raise_for_status()
    return [
        event["commit_id"]
        for event in response.json()
        if event.get("event") == "referenced" and "commit_id" in event
    ]


# Fetch the original and patched content of files for a commit
def fetch_file_contents(repo_url, commit_sha, session):
    """Fetch the full content of Python files before and after a commit."""
    url = f"https://api.github.com/repos/{repo_url}/commits/{commit_sha}"
    response = session.get(url)
    check_rate_limit(response)
    response.raise_for_status()
    commit_data = response.json()

    # Get the parent commit SHA for the before-state
    parents = commit_data.get("parents", [])
    if not parents:
        raise ValueError(f"No parent commit found for {commit_sha}")
    parent_sha = parents[0]["sha"]

    files = commit_data.get("files", [])
    original_files = {}
    patched_files = {}

    for file in files:
        if file["filename"].endswith(".py"):
            file_path = file["filename"]

            # Fetch the original file content (before state)
            original_url = f"https://api.github.com/repos/{repo_url}/contents/{file_path}?ref={parent_sha}"
            original_response = session.get(original_url)
            check_rate_limit(original_response)
            if original_response.status_code == 200:
                original_content = original_response.json().get("content", "")
                original_files[file_path] = original_content

            # Fetch the patched file content (after state)
            patched_url = f"https://api.github.com/repos/{repo_url}/contents/{file_path}?ref={commit_sha}"
            patched_response = session.get(patched_url)
            check_rate_limit(patched_response)
            if patched_response.status_code == 200:
                patched_content = patched_response.json().get("content", "")
                patched_files[file_path] = patched_content

    return original_files, patched_files


# Save data to CSV
def save_to_csv(data, csv_path):
    with open(csv_path, mode="a", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=data.keys())
        if csv_file.tell() == 0:  # Write header if the file is empty
            writer.writeheader()
        writer.writerow(data)


# Save file contents
def save_file_content(content, folder, file_name):
    file_path = os.path.join(folder, file_name)
    with open(file_path, mode="w", encoding="utf-8") as file:
        file.write(content)
    return file_path


# Main function
def main():
    api_key = load_env()
    session = initialize_github_session(api_key)

    chosen_name = input("Enter the name for this run: ")
    max_commits = int(input("Enter the maximum number of commits to process: "))

    run_dir, original_dir, patched_dir = prepare_directories(chosen_name)
    csv_path = os.path.join(run_dir, "summary.csv")

    repos = [
        "public-apis/public-apis",
        "donnemartin/system-design-primer",
        "ranaroussi/quantstats",
    ]

    progress = tqdm(total=max_commits, desc="Processing commits", unit="commit")
    commits_processed = 0

    for repo_url in repos:
        issues = fetch_issues(repo_url, session)

        for issue in tqdm(
            issues, desc=f"Processing issues in {repo_url}", unit="issue"
        ):
            commits = fetch_commits(issue, repo_url, session)

            for commit_sha in commits:
                if commits_processed >= max_commits:
                    progress.close()
                    return

                # Fetch file contents
                original_files, patched_files = fetch_file_contents(
                    repo_url, commit_sha, session
                )

                # Save files and metadata
                for file_name, original_content in original_files.items():
                    if original_content:
                        save_file_content(original_content, original_dir, file_name)

                for file_name, patched_content in patched_files.items():
                    if patched_content:
                        save_file_content(patched_content, patched_dir, file_name)

                # Example metadata
                data = {
                    "repo": repo_url,
                    "issue_url": issue["html_url"],
                    "commit_url": f"https://github.com/{repo_url}/commit/{commit_sha}",
                    "commit_sha": commit_sha,
                }
                save_to_csv(data, csv_path)

                commits_processed += 1
                progress.update(1)


if __name__ == "__main__":
    main()
