import json

import pandas as pd


def generate_json_from_csv(csv_file, output_json_file):
    """
    Generate a JSON file from a CSV containing commit data.
    """
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file)

        # Prepare the JSON data structure
        json_data = {}

        for _, row in df.iterrows():
            commit_hash = row["Commit Hash"]
            commit_date = row["Commit Date"]

            # Populate the structure for each commit
            json_data[commit_hash] = {
                "creationdate": commit_date,
                "resolutiondate": commit_date,
                "hash": commit_hash,
                "commitdate": commit_date,
            }

        # Save the JSON data to a file
        with open(output_json_file, "w") as json_file:
            json.dump(json_data, json_file, indent=4)

        print(f"JSON file successfully created at {output_json_file}")

    except Exception as e:
        print(f"Error generating JSON file: {e}")


if __name__ == "__main__":
    # Input CSV and output JSON file paths
    input_csv_file = (
        "django_commit_data.csv"  # Update with the path to your input CSV file
    )
    output_json_file = "django_commit_data.json"

    # Generate the JSON file
    generate_json_from_csv(input_csv_file, output_json_file)
