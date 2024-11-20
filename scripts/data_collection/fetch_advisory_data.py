import json
import os
from datetime import datetime

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv
from openpyxl.workbook import Workbook

load_dotenv()

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {ACCESS_TOKEN}",
}

GITHUB_API_BASE_URL = "https://api.github.com"

EXTENSION_TO_LANGUAGE = {
    "py": "Python",
    "pyx": "Cython",
    "c": "C",
    "h": "C",
    "js": "JavaScript",
    "html": "HTML",
    "htm": "HTML",
    "sh": "Shell",
    "meson": "Meson",
    "tpl": "Smarty",
    "css": "CSS",
    "dockerfile": "Dockerfile",
    "xslt": "XSLT",
}

http = urllib3.PoolManager()


def make_request(url, params=None):
    print(f"Fetching URL: {url} with params: {params}")
    response = http.request("GET", url, headers=headers, fields=params)
    print(f"Received response with status: {response.status}")
    if response.status == 200:
        return response, json.loads(response.data.decode("utf-8"))
    else:
        raise Exception(f"Failed to fetch data: Status {response.status}")


def get_repo_info(owner, repo):
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}"
    _, data = make_request(url)
    print(f"Response: {data}")
    return {
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "watchers": data.get("watchers_count"),
    }


def get_total_contributors(owner, repo):
    url = (
        f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contributors?per_page=1&anon=true"
    )
    response, data = make_request(url)
    if "Link" in response.headers:
        last_page_url = (
            response.headers["Link"].split(",")[1].split(";")[0].strip()[1:-1]
        )
        return int(last_page_url.split("=")[-1])
    else:
        return len(data)


def get_contributors_commits(owner, repo):
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contributors?per_page=100&anon=true"
    contributors = []
    while url:
        response, data = make_request(url)
        contributors.extend(data)
        url = response.headers.get("next", None)
    return contributors


def identify_core_developers(contributors):
    valid_contributors = [
        contrib for contrib in contributors if isinstance(contrib, dict)
    ]

    contributors_filtered = [
        contrib
        for contrib in valid_contributors
        if contrib.get("type") != "Anonymous" and "contributions" in contrib
    ]

    contributors_sorted = sorted(
        contributors_filtered, key=lambda x: x["contributions"], reverse=True
    )

    total_commits = sum(contrib["contributions"] for contrib in contributors_sorted)
    core_devs = []
    commits_accumulated = 0

    for contrib in contributors_sorted:
        login = (
            contrib.get("login")
            or contrib.get("name")
            or contrib.get("email", "Unknown")
        )
        core_devs.append({"login": login, "commits": contrib["contributions"]})
        commits_accumulated += contrib["contributions"]
        if commits_accumulated / total_commits >= 0.8:
            break

    return core_devs


def get_language_stats(owner, repo):
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/languages"
    _, languages = make_request(url)

    files_per_language = {lang: 0 for lang in languages.keys()}

    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/git/trees/main?recursive=1"
    _, files = make_request(url)
    files = files.get("tree", [])

    for file in files:
        if file["type"] == "blob":
            extension = file["path"].split(".")[-1].lower()
            language = EXTENSION_TO_LANGUAGE.get(extension)

            if language and language in files_per_language:
                files_per_language[language] += 1

    return languages, files_per_language


def get_security_advisories(advisories_url, params, headers, owner, repo):
    final_advisories = []
    target_repo_url = f"https://github.com/{owner}/{repo}".lower()

    try:
        while advisories_url:
            response = requests.get(advisories_url, headers=headers, params=params)
            response.raise_for_status()
            advisories = response.json()
            for adv in advisories:
                # check if the fetched repo is the targeted repo
                source_code_location = adv.get("source_code_location", "").lower()
                if target_repo_url in source_code_location:

                    final_advisories.append(adv)

            # check for pagination in 'Link' header
            link_header = response.headers.get("Link")
            if link_header and 'rel="next"' in link_header:
                links = link_header.split(", ")
                next_link = None
                for link in links:
                    if 'rel="next"' in link:
                        next_link = link.split(";")[0].strip("<>")
                        break
                advisories_url = next_link  # update URL for the next request
            else:
                advisories_url = None  # no more pages

        return final_advisories

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch security advisories: {e}")


def analyze_advisories(security_advisories):
    analyzed_advisories = []
    try:
        if security_advisories:
            for advisory in security_advisories:
                ghsa_id = advisory.get("ghsa_id")
                cve_id = advisory.get("cve_id")
                cwes = advisory.get("cwes", [])
                cwe_ids = [cwe.get("cwe_id") for cwe in cwes]
                severity = advisory.get("severity")
                description = advisory.get("description")
                analyzed_advisories.append(
                    {
                        "GHSA ID": ghsa_id,
                        "CVE ID": cve_id,
                        "Severity": severity,
                        "CWEs": ", ".join(cwe_ids) if cwe_ids else "N/A",
                        "Description": (
                            description[:200] + "..." if description else "N/A"
                        ),
                    }
                )
        return analyzed_advisories
    except Exception as e:
        raise Exception(f"Failed to analyze security advisories: {e}")


def extract_info(advisories_url, params, headers, owner, repo):
    repo_info = get_repo_info(owner, repo)
    total_contributors = get_total_contributors(owner, repo)
    contributors = get_contributors_commits(owner, repo)
    core_developers = identify_core_developers(contributors)
    languages, files_per_language = get_language_stats(owner, repo)

    total_loc = 0
    for language in languages:
        total_loc += int(languages[language])

    security_advisories = get_security_advisories(
        advisories_url, params, headers, owner, repo
    )
    analyzed_advisories = analyze_advisories(security_advisories)

    info = {
        **repo_info,
        "languages": languages,
        "files_per_language": files_per_language,
        "total_loc": total_loc,
        "total_contributors": total_contributors,
        "core_developers": core_developers,
        "core_developers_num": len(core_developers),
        "security_advisories": analyzed_advisories,
    }

    return info


def save_to_csv(info, owner, repo, csv_file):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetched")
    os.makedirs(output_dir, exist_ok=True)
    csv_file = os.path.join(output_dir, csv_file)

    repo_info = {
        "Owner": owner,
        "Repo": repo,
        "Stars": info["stars"],
        "Forks": info["forks"],
        "Watchers": info["watchers"],
        "Total LoC": info["total_loc"],
        "Total Contributors": info["total_contributors"],
        "Core Developers": info["core_developers_num"],
    }

    csv_exists = os.path.exists(csv_file)

    repo_df = pd.DataFrame([repo_info])

    if csv_exists:
        repo_df.to_csv(csv_file, mode="a", header=False, index=False)
    else:
        repo_df.to_csv(csv_file, mode="w", header=True, index=False)

    print(f"Basic repository information saved to {csv_file}")


def save_languages_to_csv(info, owner, repo, languages_file):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetched")
    os.makedirs(output_dir, exist_ok=True)
    languages_file = os.path.join(output_dir, languages_file)

    languages_info = [
        {
            "Owner": owner,
            "Repo": repo,
            "Language": lang,
            "LoC": loc,
            "Files": info["files_per_language"].get(lang, 0),
        }
        for lang, loc in info["languages"].items()
    ]

    languages_df = pd.DataFrame(languages_info)

    csv_exists = os.path.exists(languages_file)

    if csv_exists:
        languages_df.to_csv(languages_file, mode="a", header=False, index=False)
    else:
        languages_df.to_csv(languages_file, mode="w", header=True, index=False)

    print(f"Languages information saved to {languages_file}")


def save_advisories_to_csv(info, owner, repo, advisories_file):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetched")
    os.makedirs(output_dir, exist_ok=True)
    advisories_file = os.path.join(output_dir, advisories_file)

    advisories_info = [
        {
            "Owner": owner,
            "Repo": repo,
            "GHSA ID": advisory.get("GHSA ID"),
            "CVE ID": advisory.get("CVE ID"),
            "Severity": advisory.get("Severity"),
            "CWEs": advisory.get("CWEs"),
            "Description": advisory.get("Description"),
        }
        for advisory in info["security_advisories"]
    ]

    advisories_df = pd.DataFrame(advisories_info)

    csv_exists = os.path.exists(advisories_file)

    if csv_exists:
        advisories_df.to_csv(advisories_file, mode="a", header=False, index=False)
    else:
        advisories_df.to_csv(advisories_file, mode="w", header=True, index=False)

    print(f"Security advisories information saved to {advisories_file}")


def save_core_developers_to_csv(info, owner, repo, core_devs_file):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetched")
    os.makedirs(output_dir, exist_ok=True)
    core_devs_file = os.path.join(output_dir, core_devs_file)

    core_devs_info = [
        {"Owner": owner, "Repo": repo, "Login": dev["login"], "Commits": dev["commits"]}
        for dev in info["core_developers"]
    ]

    core_devs_df = pd.DataFrame(core_devs_info)

    csv_exists = os.path.exists(core_devs_file)

    if csv_exists:
        core_devs_df.to_csv(core_devs_file, mode="a", header=False, index=False)
    else:
        core_devs_df.to_csv(core_devs_file, mode="w", header=True, index=False)

    print(f"Core developers information saved to {core_devs_file}")


# def save_to_excel(info, filename):
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     output_dir = os.path.join(script_dir, "fetched_repos")
#     os.makedirs(output_dir, exist_ok=True)
#     file_path = os.path.join(output_dir, filename)

#     core_devs_data = pd.DataFrame(info["core_developers"])

#     if not core_devs_data.empty:
#         core_devs_data['login'] = core_devs_data['login'].astype(str)
#         core_devs_data['commits'] = core_devs_data['commits'].astype(int)

#     advisories_data = pd.DataFrame(info["security_advisories"])

#     repo_df = pd.DataFrame([{
#         "Stars": info["stars"],
#         "Forks": info["forks"],
#         "Watchers": info["watchers"],
#         "Total LoC": info["total_loc"],
#         "Total Contributors": info["total_contributors"],
#         "Core Developers": info["core_developers_num"]
#     }])

#     languages_df = pd.DataFrame([{
#         "Language": lang,
#         "LoC": loc,
#         "Files": info["files_per_language"].get(lang, 0)
#     } for lang, loc in info["languages"].items()])

#     with pd.ExcelWriter(file_path) as writer:
#         repo_df.to_excel(writer, sheet_name="Repository Info", index=False)
#         languages_df.to_excel(writer, sheet_name="Languages", index=False)
#         core_devs_data.to_excel(writer, sheet_name="Core Developers", index=False)
#         advisories_data.to_excel(writer, sheet_name="Security Advisories", index=False)

#     print(f"Data saved to {file_path}")


def main(advisories_url, params, headers, owner, repo):
    info = extract_info(advisories_url, params, headers, owner, repo)

    basic_info_csv = "github_repos_basic_info.csv"
    languages_csv = "github_repos_languages.csv"
    core_devs_csv = "github_repos_core_developers.csv"
    advisories_csv = "github_repos_security_advisories.csv"

    save_to_csv(info, owner, repo, basic_info_csv)
    save_languages_to_csv(info, owner, repo, languages_csv)
    save_core_developers_to_csv(info, owner, repo, core_devs_csv)
    save_advisories_to_csv(info, owner, repo, advisories_csv)


if __name__ == "__main__":
    advisories_url = "https://api.github.com/advisories"
    params = {"ecosystem": "pip", "per_page": 100}
    owner = input("Enter owner name: ").strip()
    repo = input("Enter repo name: ").strip()
    # django/django
    main(advisories_url, params, headers, owner, repo)
