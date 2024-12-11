import argparse
import json
import os
import sys

import pandas as pd


def load_bandit_results(file_path):
    """Loads the Bandit JSON results from a file."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def flatten_bandit_output(bandit_output):
    """
    Flattens Bandit's hierarchical output into a pandas DataFrame.
    """
    results = bandit_output.get("results", [])
    flattened_data = []

    for result in results:
        flattened_entry = {
            "file": result.get("filename", "N/A"),
            "line_number": result.get("line_number", -1),
            "line_range": result.get("line_range", []),
            "col_offset": result.get("col_offset", -1),
            "end_col_offset": result.get("end_col_offset", -1),
            "issue_severity": result.get("issue_severity", "UNKNOWN"),
            "issue_confidence": result.get("issue_confidence", "UNKNOWN"),
            "issue_cwe": result.get("issue_cwe", {}).get("id", "N/A"),
            "issue_cwe_link": result.get("issue_cwe", {}).get("link", "N/A"),
            "issue_text": result.get("issue_text", "No issue text provided"),
            "test_name": result.get("test_name", "N/A"),
            "test_id": result.get("test_id", "N/A"),
            "code": result.get("code", "").strip(),
            "more_info": result.get("more_info", "N/A"),
        }
        flattened_data.append(flattened_entry)

    return pd.DataFrame(flattened_data)


def preprocess_bandit_df(bandit_df):
    """
    Adds 'project', 'commit_id', 'commit_link' to the Bandit DataFrame
    and reformats the 'file' column.
    """
    bandit_df["file"] = bandit_df["file"].apply(lambda x: x.split("/")[-1])
    split_parts = bandit_df["file"].str.split("_", expand=True)

    bandit_df["project"] = split_parts[0] + "/" + split_parts[1]
    bandit_df["commit_id"] = split_parts[2]
    bandit_df["commit_link"] = (
        "https://github.com/"
        + bandit_df["project"]
        + "/commit/"
        + bandit_df["commit_id"]
    )

    bandit_df["file"] = split_parts.iloc[:, 3:].apply(
        lambda row: "/".join(row.dropna()), axis=1
    )

    return bandit_df


def parse_arguments():
    """Argument parser"""
    parser = argparse.ArgumentParser(
        description="Interpret the Bandit analysis results."
    )
    parser.add_argument(
        "--bandit_results",
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

    json_path = args.bandit_results
    if not os.path.isfile(json_path):
        print(f"Error: {json_path} not found!")
        sys.exit(1)

    # Create DataFrames
    basndit_json_output = load_bandit_results(json_path)
    flattened_bandit_output = flatten_bandit_output(basndit_json_output)
    df = preprocess_bandit_df(flattened_bandit_output)

    filename = ".".join(json_path.split(".")[:-1]) + ".csv"
    df.to_csv(filename, index=False)
    print(f"Results written to {filename}.")


if __name__ == "__main__":
    main()
