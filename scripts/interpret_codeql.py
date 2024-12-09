import argparse
import json
import os
import sys

import pandas as pd


def get_all_rules(sarif_file):
    """
    Create and return a dictionary containing information about all the CodeQL
    queries i.e., vulnerability types found in CodeQL results.
    """
    rules = {}

    with open(sarif_file, "r") as f:
        sarif_data = json.load(f)

    for rule in sarif_data.get("runs", [{}])[0].get("tool").get("driver").get("rules"):
        rules[rule.get("id")] = {
            "precision": rule.get("properties").get("precision"),
            "name": rule.get("properties").get("name"),
            "kind": rule.get("properties").get("kind"),
            "shortDescription": rule.get("shortDescription").get("text"),
            "fullDescription": rule.get("fullDescription").get("text"),
            "level": rule.get("defaultConfiguration").get("level"),
            "problemSeverity": rule.get("properties").get("problem.severity"),
            "securitySeverity": rule.get("properties").get("security-severity"),
            "subSeverity": rule.get("properties").get("sub-severity"),
            "tags": rule.get("properties").get("tags"),
        }

    return rules


def get_results(sarif_file):
    """
    Create a list of all the vulnerabilities found by CodeQL. Each list item contains
    the file name, vulnerability (rule_id), and the CodeQL message.
    """
    results = []

    with open(sarif_file, "r") as f:
        sarif_data = json.load(f)

    for result in sarif_data.get("runs", [{}])[0].get("results", []):
        rule_id = result.get("ruleId", "Unknown")
        message = result.get("message", {}).get("text", "No message")
        file = (
            result.get("locations", [{}])[0]
            .get("physicalLocation", {})
            .get("artifactLocation", {})
            .get("uri", "")
        )

        results.append([file, rule_id, message])

    return results


def create_dataframe(rules, results):
    """
    Create a dataframe containing all the information about each file and
    its corresponding vulnerabilities.
    """
    data = []

    for result in results:
        file, rule_id, message = result
        repo = "_".join(file.split("_")[:2])
        repo.replace("_", "/")
        commit_id = file.split("_")[2]
        commit_link = f"https://github.com/{repo}/commit/{commit_id}"
        filename = "/".join(file.split("_")[3:])
        rule_info = rules.get(rule_id, {})
        row_data = {
            "project": repo,
            "commit_id": commit_id,
            "commit_link": commit_link,
            "file": filename,
            "rule_id": rule_id,
            "message": message,
        }
        row_data.update(rule_info)

        data.append(row_data)

    df = pd.DataFrame(data)

    return df


def get_detected_rules(vulnerabilities_summary_df):
    """
    Takes in the output of create_dataframe() and outputs a dataframe containing
    the detected rules and their information with respect to the commits.
    """
    detected_rules_df = vulnerabilities_summary_df[
        ~vulnerabilities_summary_df["rule_id"].duplicated()
    ]

    for rule_id in detected_rules_df["rule_id"].to_list():
        vulnerable_files = vulnerabilities_summary_df[
            vulnerabilities_summary_df["rule_id"] == rule_id
        ]
        commit_occurrences = len(
            vulnerable_files[~vulnerable_files["commit_id"].duplicated()]
        )
        project_occurrences = len(
            vulnerable_files[~vulnerable_files["project"].duplicated()]
        )

        detected_rules_df.loc[
            detected_rules_df["rule_id"] == rule_id, "commit_occurrences"
        ] = commit_occurrences

        detected_rules_df.loc[
            detected_rules_df["rule_id"] == rule_id, "project_occurrences"
        ] = project_occurrences

    return detected_rules_df


def parse_arguments():
    """Argument parser"""
    parser = argparse.ArgumentParser(
        description="Interpret the CodeQL analysis results."
    )
    parser.add_argument(
        "--codeql_results",
        required=True,
        help="The path to the CodeQL analysis results in .sarif format.",
    )
    return parser.parse_args()


def main():
    """
    Entry point of the script.
    Parses arguments, processes CodeQL results, and writes to an Excel file.
    """
    args = parse_arguments()

    if not os.path.isfile(args.codeql_results):
        print(f"Error: {args.codeql_results} not found!")
        sys.exit(1)

    # Process rules and results
    rules = get_all_rules(args.codeql_results)
    results = get_results(args.codeql_results)

    # Create DataFrames
    main_df = create_dataframe(rules, results)
    rules_df = get_detected_rules(main_df)

    # Write DataFrames to Excel file
    filename = ".".join(args.codeql_results.split(".")[:-1]) + ".xlsx"

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        main_df.to_excel(writer, sheet_name="main", index=False)
        rules_df.to_excel(writer, sheet_name="rules_summary", index=False)

        print(f"Results successfully written to: {filename}")


if __name__ == "__main__":
    main()
