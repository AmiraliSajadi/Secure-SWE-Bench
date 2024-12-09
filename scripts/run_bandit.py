import argparse
import json
import os
import subprocess

env = os.environ.copy()


def load_bandit_results(file_path):
    """Loads the Bandit JSON results from a file."""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None


def run_bandit_analysis(folder_path, output_file):
    """
    Run Bandit analysis on all Python files in the given folder and save the results to a JSON file.

    Args:
        folder_path (str): The path to the folder containing the files to analyze.
        output_file (str): The path where the JSON output should be saved.
    """
    try:
        # Check if folder exists
        if not os.path.exists(folder_path):
            print(f"Skipping: Folder does not exist: {folder_path}")
            return

        # Check if the folder contains Python files
        python_files = [f for f in os.listdir(folder_path) if f.endswith(".py")]
        if not python_files:
            print(f"Skipping: No Python files found in {folder_path}")
            return

        print(f"Running Bandit on: {folder_path}")

        # Run the Bandit command
        cmd = f"bandit -r {folder_path} -f json -o {output_file}"
        result = subprocess.run(
            cmd, shell=True, check=False, env=env, capture_output=True, text=True
        )

        # Check if Bandit produced the output file
        if os.path.exists(output_file):
            print(f"Bandit analysis completed: {output_file}")
            print(result.stdout)
        else:
            raise RuntimeError(
                f"Bandit analysis failed for {folder_path}: No output file created"
            )

        # Check for any errors or warnings in the stderr
        if result.stderr:
            print(f"Warnings/Errors: {result.stderr}")

        # Raise an error if Bandit exited with a non-zero code, but continue if output is generated
        if result.returncode != 0:
            print(f"Bandit returned a non-zero exit status: {result.returncode}")
            print(f"Bandit output: {result.stderr}")

    except subprocess.CalledProcessError as e:
        # Print the full error output from Bandit
        print("Error during Bandit execution:")
        raise RuntimeError(
            f"Bandit analysis failed for {folder_path}: {e.stderr}"
        ) from e
