#!/usr/bin/python3
import os
import json
import getpass
import inquirer
from jira import JIRA


# Connect to Jira
def connect_to_jira(server_url, username, api_token, jira_type):
    try:
        if jira_type == "cloud":
            jira = JIRA(server=server_url, basic_auth=(username, api_token))
        else:
            jira = JIRA(server=server_url, token_auth=api_token)
        return jira
    except Exception as e:
        print(f"Error connecting to Jira: {e}")
        return None


# Function to prompt for the secret information
def prompt_for_secrets():
    questions = [
        inquirer.Text("server_url", message="Enter your Jira server URL"),
        inquirer.Text(
            "project_key",
            message="Enter the project key for the project you want to work on",
        ),
        inquirer.Text("api_token", message="Enter your API Token"),
        inquirer.Text("username", message="Enter your Username"),
        inquirer.List(
            "jira_type",
            message="Enter your jira server type (cloud or server)",
            choices=["cloud", "server"],
        ),
    ]

    answers = inquirer.prompt(questions)

    # Securely store the data
    store_secrets(answers)


# Function to store the secret information securely in a file
def store_secrets(secrets):
    secret_file = "secret_config.json"

    with open(secret_file, "w") as f:
        json.dump(secrets, f, indent=4)
    print(f"Secrets have been saved to {secret_file}")


# Check if the secret file already exists
def check_for_existing_secrets():
    if os.path.exists("secret_config.json"):
        with open("secret_config.json", "r") as f:
            return json.load(f)
    else:
        prompt_for_secrets()
        return None


# Search for current assigned issues
def search_for_issues(jira_client, project_key):
    issues = jira_client.search_issues(
        f"project={project_key} AND assignee=currentUser() AND status != Done",
        maxResults=50,
    )
    if len(issues) == 0:
        print("No issues found.")
        return None

    # Display issue details
    print(f"Issues assigned to you:")
    for issue in issues:
        print(
            f"{issue.key}: {issue.fields.summary} (Status: {issue.fields.status.name})"
        )
    return issues


# Main entry point
if __name__ == "__main__":
    secrets = check_for_existing_secrets()
    if secrets:
        print("Secrets loaded successfully!")
    else:
        print("No secrets found. A new secret file has been created.")
        exit()
    # Use the secrets to access the JIRA API
    jira_client = connect_to_jira(
        secrets["server_url"],
        secrets["username"],
        secrets["api_token"],
        jira_type=secrets["jira_type"],
    )
    if jira_client:
        print("Connected to Jira successfully!")
    else:
        print("Failed to connect to Jira. Please check your secrets and try again.")
        exit()
    while True:
        # Prompt the user for the action they want to perform
        question = [
            inquirer.List(
                "action",
                message="What do you want to do?",
                choices=[
                    {"name": "Create a new issue", "value": "create_issue"},
                    {"name": "Search for an issue", "value": "search_issue"},
                    {"name": "List current issues", "value": "list_issues"},
                    {"name": "Exit", "value": "exit"},
                ],
                default="exit",
            )
        ]

        # Get the user's choice
        answers = inquirer.prompt(question)

        # Access the selected value
        action = answers["action"]

        # Perform the selected action
        if action["value"] == "list_issues":
            search_for_issues(jira_client, secrets["project_key"])
