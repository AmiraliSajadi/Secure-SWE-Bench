import json
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


def initialize_graphql_session(api_key):
    """Initialize a session for GitHub GraphQL API requests."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.github.v4+json",
        }
    )
    return session


def execute_graphql_query(query, variables, session):
    """Execute a GraphQL query."""
    url = "https://api.github.com/graphql"
    response = session.post(url, json={"query": query, "variables": variables})
    response.raise_for_status()
    data = response.json()

    # Check rate limits
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
    if remaining == 0:
        reset_in = max(0, reset_time - int(time.time()))
        print(f"Rate limit reached. Pausing for {reset_in} seconds...")
        time.sleep(reset_in + 1)

    return data


def get_repositories():
    """Retrieve a predefined list of repositories."""
    return ["astropy/astropy"]


def get_issues_and_commits(repository, session):
    """Retrieve issues and associated commit details using GraphQL."""
    owner, name = repository.split("/")
    query = """
    query($repoOwner: String!, $repoName: String!, $issueCursor: String) {
      repository(owner: $repoOwner, name: $repoName) {
        issues(first: 100, after: $issueCursor, states: CLOSED) {
          pageInfo {
            endCursor
            hasNextPage
          }
          nodes {
            number
            title
            body
            url
            timelineItems(first: 10, itemTypes: REFERENCED_EVENT) {
              nodes {
                ... on ReferencedEvent {
                  commit {
                    oid
                    message
                    additions
                    deletions
                    files(first: 10) {
                      nodes {
                        path
                        additions
                        deletions
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    variables = {"repoOwner": owner, "repoName": name, "issueCursor": None}
    all_issues = []

    with tqdm(desc=f"Retrieving issues from {repository}", unit="batch") as pbar:
        while True:
            data = execute_graphql_query(query, variables, session)

            # Debugging: Print the raw data response
            if "data" not in data:
                print(f"Raw response: {json.dumps(data, indent=2)}")
                raise KeyError("GraphQL response missing 'data' key.")

            repository_data = data["data"]["repository"]["issues"]
            all_issues.extend(repository_data["nodes"])
            if not repository_data["pageInfo"]["hasNextPage"]:
                break
            variables["issueCursor"] = repository_data["pageInfo"]["endCursor"]
            pbar.update(1)

    return all_issues


def filter_commits(issues):
    """Filter commits based on file modification criteria."""
    filtered_commits = []
    keywords = ["cve", "cwe", "cvss", "vulnerability", "security"]

    for issue in issues:
        for timeline_item in issue.get("timelineItems", {}).get("nodes", []):
            commit = timeline_item.get("commit")
            if not commit:
                continue

            test_file_modified = False
            python_file_modified = False
            for file_change in commit.get("fileChanges", {}).get("nodes", []):
                filename = file_change["path"]
                if "test" in filename.lower() and any(
                    keyword in commit["message"].lower() for keyword in keywords
                ):
                    test_file_modified = True
                elif filename.endswith(".py"):
                    python_file_modified = True

            if test_file_modified and python_file_modified:
                filtered_commits.append(
                    {
                        "issue": {
                            "title": issue["title"],
                            "body": issue["body"],
                            "url": issue["url"],
                        },
                        "commit": {
                            "sha": commit["oid"],
                            "message": commit["message"],
                            "modified_files": ", ".join(
                                file["path"]
                                for file in commit.get("fileChanges", {}).get(
                                    "nodes", []
                                )
                            ),
                        },
                    }
                )

    return filtered_commits


def generate_report(filtered_commits):
    """Generate data for the report."""
    report_data = []
    for item in filtered_commits:
        commit = item["commit"]
        issue = item["issue"]
        report_data.append(
            {
                "SHA": commit["sha"],
                "Message": commit["message"],
                "Modified Files": commit["modified_files"],
                "Issue Title": issue["title"],
                "Issue Body": issue["body"],
                "Issue URL": issue["url"],
            }
        )
    return report_data


def write_excel(data, filename):
    """Write the filtered commit and issue data to an Excel file."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Filtered Commits and Issues"
    headers = [
        "SHA",
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
    session = initialize_graphql_session(api_key)
    repositories = get_repositories()
    all_filtered_commits = []

    for repository in repositories:
        print(f"Processing repository: {repository}")
        issues = get_issues_and_commits(repository, session)
        filtered_commits = filter_commits(issues)
        all_filtered_commits.extend(filtered_commits)

    report_data = generate_report(all_filtered_commits)
    write_excel(report_data, "filtered_commits_and_issues.xlsx")
    print("Report generated: filtered_commits_and_issues.xlsx")


if __name__ == "__main__":
    main()
