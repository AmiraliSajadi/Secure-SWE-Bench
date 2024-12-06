"""
This script processes the train set of the SWE-Bench dataset by retrieving all patched 
Python files (excluding test files) in their original and patched states from GitHub 
repositories using the GitHub API. It organizes these files into structured directories 
for further analysis, while handling API rate limits and supporting customizable commit limits.

Functions:
- load_env: Loads environment variables for API authentication.
- initialize_github_session: Sets up a GitHub API session.
- check_rate_limit: Monitors and handles GitHub API rate limits.
- prepare_directories: Creates directories for storing output files.
- fetch_file_content: Retrieves file content from GitHub.
- write_file_content: Saves file content to disk.
- process_dataset: Main logic to process the SWE-Bench train set.
- parse_arguments: Parses command-line arguments.
- main: Entry point of the script.
"""

import argparse
import base64
import os
import time

import requests
from datasets import load_dataset
from dotenv import load_dotenv
from tqdm import tqdm


def load_env():
    """load environment variables"""
    load_dotenv()
    return os.getenv("GITHUB_API_KEY")


def initialize_github_session(api_key):
    """Initialize GitHub API session"""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    return session


def check_rate_limit(response):
    """Check GitHub API rate limit"""
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))

    if remaining == 0:
        reset_in = max(0, reset_time - int(time.time()))
        print(f"Rate limit reached. Pausing for {reset_in} seconds...")
        time.sleep(reset_in + 1)


def prepare_directories(run_id):
    """Prepare directories for storing files"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_dir = os.path.join(base_dir, "../data", run_id)
    original_dir = os.path.join(run_dir, "original")
    patched_dir = os.path.join(run_dir, "patched")
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(patched_dir, exist_ok=True)
    return original_dir, patched_dir


def fetch_file_content(session, repo, commit_sha, file_path):
    """Fetch file contents from GitHub"""
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={commit_sha}"
    response = session.get(url)
    check_rate_limit(response)
    if response.status_code == 200:
        file_data = response.json()
        if "content" in file_data and file_data["encoding"] == "base64":
            return base64.b64decode(file_data["content"]).decode("utf-8")
    return None


def write_file_content(directory, filename, content):
    """Write file content to disk"""
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)


def process_dataset(run_id, max_commits, api_key):
    """Main processing logic"""
    dataset = load_dataset("princeton-nlp/SWE-bench", split="train", streaming=True)
    session = initialize_github_session(api_key)
    original_dir, patched_dir = prepare_directories(run_id)

    commit_count = 0
    for record in tqdm(dataset, desc="Processing dataset"):
        if max_commits and commit_count >= max_commits:
            break

        repo = record["repo"]
        commit_sha = record["base_commit"]

        # Fetch commit details to retrieve parent commit SHA
        commit_url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
        response = session.get(commit_url)
        check_rate_limit(response)

        if response.status_code == 200:
            commit_data = response.json()
            parent_commits = commit_data.get("parents", [])
            if not parent_commits:
                print(f"No parent commit found for {commit_sha}. Skipping...")
                continue
            parent_commit_sha = parent_commits[0]["sha"]  # Use the first parent commit

            files_changed = commit_data.get("files", [])
            for file in files_changed:
                file_name = file["filename"]
                if file_name.endswith(".py") and "test" not in file_name.lower():
                    # Fetch original and patched content
                    original_content = fetch_file_content(
                        session, repo, parent_commit_sha, file_name
                    )
                    patched_content = fetch_file_content(
                        session, repo, commit_sha, file_name
                    )

                    # Write files to disk
                    if original_content:
                        original_file_name = f"{repo.replace('/', '_')}_{commit_sha}_original_{file_name.replace('/', '_')}"
                        write_file_content(
                            original_dir, original_file_name, original_content
                        )

                    if patched_content:
                        patched_file_name = f"{repo.replace('/', '_')}_{commit_sha}_patched_{file_name.replace('/', '_')}"
                        write_file_content(
                            patched_dir, patched_file_name, patched_content
                        )

        commit_count += 1


def parse_arguments():
    """Argument parser"""
    parser = argparse.ArgumentParser(description="Process SWE-bench dataset.")
    parser.add_argument(
        "--id", required=True, help="Run ID for organizing output files."
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=None,
        help="Maximum number of commits to process.",
    )
    return parser.parse_args()


def main():
    """Entry point"""
    args = parse_arguments()
    api_key = load_env()
    if not api_key:
        print("GITHUB_API_KEY not found in environment variables.")
        return

    process_dataset(args.id, args.commits, api_key)


if __name__ == "__main__":
    main()
