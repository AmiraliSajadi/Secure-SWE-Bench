import os
import time

import openpyxl
import requests
from dotenv import load_dotenv
from tqdm import tqdm


def load_env():
    """Load the GitHub API key from the .env file."""
    load_dotenv()
    return os.getenv("GITHUB_API_KEY")


def initialize_github_session(api_key):
    """Initialize a session for GitHub API requests."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    return session


def check_rate_limit(response):
    """Check the API rate limit and pause if necessary."""
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))

    if remaining == 0:
        reset_in = max(0, reset_time - int(time.time()))
        print(f"Rate limit reached. Pausing for {reset_in} seconds...")
        print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        print(
            f"Rate limit resets at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_time))}"
        )
        time.sleep(reset_in + 1)  # Sleep for the reset duration


def get_repositories():
    """Retrieve a predefined list of repositories or dynamically fetch them."""
    # TODO: Make it dynamic
    return ["astropy/astropy"]


def get_issues(repository, session):
    """Retrieve all resolved issues for a given repository with progress."""
    url = f"https://api.github.com/repos/{repository}/issues"
    params = {"state": "closed", "per_page": 100}
    all_issues = []
    page_count = 0

    with tqdm(desc=f"Retrieving issues from {repository}", unit="page") as pbar:
        while url:
            response = session.get(url, params=params)
            check_rate_limit(response)
            response.raise_for_status()
            issues = response.json()
            all_issues.extend(issues)
            url = response.links.get("next", {}).get("url")
            page_count += 1
            pbar.update(1)

    return all_issues


def get_commits(issue, repository, session):
    """Fetch commits linked to a specific issue."""
    issue_number = issue["number"]
    url = f"https://api.github.com/repos/{repository}/issues/{issue_number}/timeline"
    params = {"per_page": 100}
    response = session.get(url, params=params)
    check_rate_limit(response)
    response.raise_for_status()
    return [
        event["commit_id"]
        for event in response.json()
        if event.get("event") == "referenced" and "commit_id" in event
    ]


def get_commit_details(commit_sha, repository, session):
    """Retrieve details of a specific commit."""
    url = f"https://api.github.com/repos/{repository}/commits/{commit_sha}"
    try:
        response = session.get(url)
        check_rate_limit(response)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 422:
            print(f"Skipping invalid commit SHA: {commit_sha}")
            return None
        raise


def filter_commits(commits, session, repository, issue):
    """Filter commits based on file modification criteria and include issue details."""
    filtered_commits = []
    for commit_sha in commits:
        commit_details = get_commit_details(commit_sha, repository, session)
        if not commit_details:
            continue  # Skip invalid commits
        modified_files = commit_details.get("files", [])
        test_file_modified = False
        python_file_modified = False

        for file in modified_files:
            filename = file["filename"]
            patch = file.get("patch", "").lower()
            if "test" in filename and any(
                keyword in patch
                for keyword in ["cve", "cwe", "cvss", "vulnerability", "security"]
            ):
                test_file_modified = True
            elif filename.endswith(".py"):
                python_file_modified = True

        if test_file_modified and python_file_modified:
            commit_details["issue"] = {
                "title": issue.get("title", ""),
                "body": issue.get("body", ""),
                "url": issue.get("html_url", ""),
            }
            filtered_commits.append(commit_details)
    return filtered_commits


def generate_report(filtered_commits):
    """Generate data for the report, including issue details."""
    report_data = []
    for commit in filtered_commits:
        issue = commit.get("issue", {})
        commit_data = {
            "SHA": commit["sha"],
            "Author": commit["commit"]["author"]["name"],
            "Message": commit["commit"]["message"],
            "Modified Files": ", ".join(
                file["filename"] for file in commit.get("files", [])
            ),
            "Issue Title": issue.get("title", ""),
            "Issue Body": issue.get("body", ""),
            "Issue URL": issue.get("url", ""),
        }
        report_data.append(commit_data)
    return report_data


def write_excel(data, filename):
    """Write the filtered commit and issue data to an Excel file."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Filtered Commits and Issues"
    headers = [
        "SHA",
        "Author",
        "Message",
        "Modified Files",
        "Issue Title",
        "Issue Body",
        "Issue URL",
    ]
    ws.append(headers)
    for row in data:
        ws.append([row.get(header, "") for header in headers])
    wb.save(filename)


def main():
    api_key = load_env()
    session = initialize_github_session(api_key)
    repositories = get_repositories()
    all_filtered_commits = []

    for repository in repositories:
        print(f"Processing repository: {repository}")
        issues = get_issues(repository, session)

        for issue in tqdm(
            issues, desc=f"Processing issues in {repository}", unit="issue"
        ):
            commits = get_commits(issue, repository, session)
            filtered_commits = filter_commits(commits, session, repository, issue)
            all_filtered_commits.extend(filtered_commits)

    report_data = generate_report(all_filtered_commits)
    write_excel(report_data, "filtered_commits_and_issues.xlsx")
    print("Report generated: filtered_commits_and_issues.xlsx")


if __name__ == "__main__":
    main()
