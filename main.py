#!/usr/bin/python3
import os
import json
from datetime import datetime, timezone
from InquirerPy import inquirer
from InquirerPy import prompt
from InquirerPy.validator import EmptyInputValidator
from colorama import Fore, Style
from jira import JIRA
from rich.table import Table
from rich.console import Console

# Constant
ACTION_DICT = {
    "create_issue": "1. Create a new issue in the project",
    "search_issue": "2. Search for an issue by key or filter",
    "list_issues": "3. List all the issues in the current project",
    "transition": "4. Transition an issue from one state to another",
    "comment": "5. Add a comment to an issue",
    "log_work": "6. Log time spent on an issue",
    "exit": "7. Exit the application",
}


# Connect to Jira
def connect_to_jira(server_url, username, api_token, jira_type, ssl_cert=True):
    try:
        if jira_type == "cloud":
            jira = JIRA(
                server=server_url,
                basic_auth=(username, api_token),
                options={"verify": ssl_cert},
            )
        else:
            jira = JIRA(server=server_url, token_auth=api_token)
        return jira
    except Exception as e:
        print(f"Error connecting to Jira: {e}")
        return None


# Function to prompt for the secret information
def prompt_for_secrets():
    questions = [
        {
            "type": "input",
            "name": "server_url",
            "message": "Enter your Jira server URL:",
        },
        {
            "type": "input",
            "name": "project_key",
            "message": "Enter the project key for the project you want to work on:",
        },
        {"type": "input", "name": "api_token", "message": "Enter your API Token:"},
        {"type": "input", "name": "username", "message": "Enter your Username:"},
        {
            "type": "list",
            "name": "jira_type",
            "message": "Enter your jira server type (cloud or server):",
            "choices": ["cloud", "server"],
        },
        {
            "type": "confirm",
            "name": "ssl_cert",
            "message": "Will verify the SSL certification?",
        },
    ]
    answers = prompt(questions)

    # Prompt for additional configuration
    use_predefined_labels = inquirer.confirm(
        message="Will you use pre-defined labels?",
        default=True,
    ).execute()

    if use_predefined_labels:
        questions = [
            {
                "type": "input",
                "name": "origin",
                "message": "Origin labels (separated by comma):",
            },
            {
                "type": "input",
                "name": "type",
                "message": "Type labels (separated by comma):",
            },
            {
                "type": "input",
                "name": "project",
                "message": "Project labels (separated by comma):",
            },
        ]

        labels_answers = prompt(questions)
        labels = {"is_enable": use_predefined_labels, "labels": labels_answers}
    else:
        labels = {"is_enable": use_predefined_labels}

    configuration = dict(answers)
    configuration.update({"labels_conf": labels})

    # Watchers
    default_watchers = inquirer.text(
        message="Enter your default watchers lists (separated by comma):",
    ).execute()

    configuration.update({"watchers": default_watchers})

    # Assignees
    assignees = inquirer.text(
        message="Enter assignee lists (separated by comma):",
        validate=EmptyInputValidator("Assignee list cannot be empty"),
    ).execute()

    configuration.update({"assignee": assignees})

    # Store the data
    store_secrets(configuration)


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


# Create a task
def create_task(jira, project_key, summary, description, issue_type="Story", **fields):
    try:
        issue_data = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
        issue_data.update(fields)
        task = jira.create_issue(fields=issue_data)
        url = fields["server_url"] + "browse/"
        print(f"Task created: {url}{task.key}")
        return task
    except Exception as e:
        print(f"Failed to create task: {e}")
        return None


# Create a sub-task
def create_sub_task(jira, parent_issue_key, summary, description, **fields):
    try:
        subtask_fields = {
            "project": {"key": jira.issue(parent_issue_key).fields.project.key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Sub-task"},
            "parent": {"key": parent_issue_key},
        }
        subtask_fields.update(fields)
        sub_task = jira.create_issue(fields=subtask_fields)
        print(f"Sub-task created: {JIRA_PREFIX_URL}{sub_task.key}")
        return sub_task
    except Exception as e:
        print(f"Failed to create sub-task: {e}")
        return None


# Search for current assigned issues
def search_for_issues(jira_client, project_key, user_filter):
    filter = f"project={project_key} AND assignee=currentUser() "
    custom = "AND "
    if user_filter == "Open":
        custom += " resolution = Unresolved"
    elif user_filter == "Active":
        custom += " resolution = Unresolved AND status != Backlog"
    elif user_filter == "Done":
        custom += " resolution != Unresolved"
    else:
        custom += user_filter

    # Concatenate the original filter and customized one
    filter = filter + custom

    print(filter)

    issues = jira_client.search_issues(
        filter,
        maxResults=50,
    )
    if len(issues) == 0:
        print("No issues found.")
        return None
    return issues


# Utilities
def display_issue_status(jira_client, issue_key):
    """
    Fetch and display the current status of a Jira issue with color.

    :param jira_client: JIRA client instance
    :param issue_key: Key of the Jira issue (e.g., "PROJ-123")
    """
    try:
        issue = jira_client.issue(issue_key)
        status = issue.fields.status.name

        # Choose color based on status
        if status.lower() in ["done", "resolved", "closed"]:
            color = Fore.GREEN
        elif status.lower() in ["in progress", "review"]:
            color = Fore.YELLOW
        elif status.lower() in ["to do", "open", "backlog"]:
            color = Fore.CYAN
        else:
            color = Fore.MAGENTA  # For any other statuses

        print(f"Current Status of {issue_key}: {color}{status}{Style.RESET_ALL}")
    except Exception as e:
        print(f"Failed to fetch status for issue {issue_key}: {e}")


# Transition
def get_transitions(jira_client, issue_key):
    """
    Fetch available transitions for a Jira issue.

    :param jira_client: JIRA client instance
    :param issue_key: Key of the Jira issue (e.g., "PROJ-123")
    :return: List of transitions
    """
    transitions = jira_client.transitions(issue_key)
    for transition in transitions:
        print(f"ID: {transition['id']}, Name: {transition['name']}")
    return transitions


def fetch_and_display_transitions(jira_client, issue_key):
    """
    Fetch and display available transitions for a Jira issue.

    :param jira_client: JIRA client instance
    :param issue_key: Key of the Jira issue (e.g., "PROJ-123")
    :return: List of transitions
    """
    transitions = jira_client.transitions(issue_key)
    choices = [{"name": t["name"], "id": t["id"]} for t in transitions]
    return choices


# Display issues as table
def display_table(console, issues):
    table = Table(title="Issue details")
    table.add_column("Key", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Summary", style="green")
    for issue in issues:
        table.add_row(issue.key, issue.fields.status.name, issue.fields.summary)
    console.print(table)


def transition_in_loop(jira_client, issue_key):
    """
    Allow the user to transition the issue iteratively by selecting statuses in a loop.

    :param jira_client: JIRA client instance
    :param issue_key: Key of the Jira issue (e.g., "PROJ-123")
    """
    while True:
        # Fetch available transitions
        transitions = fetch_and_display_transitions(jira_client, issue_key)

        if not transitions:
            print(f"No available transitions for issue {issue_key}.")
            break
        # Show current status
        display_issue_status(jira_client, issue_key)

        # Prompt the user to select a transition
        choices = [t["name"] for t in transitions]
        choices.append("Exit")
        next_status = inquirer.select(
            message=f"> Select the next status for issue {issue_key}:",
            choices=choices,
        ).execute()

        if next_status == "Exit":
            print("Exiting transition loop.")
            break

        # Find the selected transition's ID
        selected_transition = next(t for t in transitions if t["name"] == next_status)

        # Perform the transition
        try:
            jira_client.transition_issue(issue_key, selected_transition["id"])
            print(f"Issue {issue_key} transitioned to '{next_status}'.")
        except Exception as e:
            print(f"Failed to transition issue {issue_key} to '{next_status}': {e}")


# Post a comment to the issue
def add_comment_to_issue(jira_client, issue_key, comment):
    # Add a comment to the issue
    try:
        issue = jira_client.issue(issue_key)
        jira_client.add_comment(issue, comment)
        print(f"Comment added successfully to issue {issue_key}.")
        return True
    except Exception as e:
        print(f"Failed to add comment: {e}")
        return False


# Add worklog
def convert_to_jira_date(user_date):
    try:
        # Parse and convert to JIRA format
        date_obj = datetime.strptime(user_date, "%Y/%m/%d")

        # Attach UTC timezone info to the datetime object
        date_with_tz = date_obj.replace(tzinfo=timezone.utc)
        return date_with_tz
    except ValueError:
        raise ValueError("Invalid date format. Please use YYYY/MM/DD.")


def log_work_with_date(
    jira_client, issue_key, time_spent, work_description, jira_date=None
):
    try:
        # Log work with the converted date
        jira_client.add_worklog(
            issue=issue_key,
            timeSpent=time_spent,
            comment=work_description,
            started=jira_date,
        )
        print(f"Work logged successfully for issue {issue_key}.")
    except Exception as e:
        print(f"Failed to log work: {e}")


# Helper
def get_action_list():
    return list(ACTION_DICT.values())


def get_action_description(search_key, isReverse=True):
    action_dict = ACTION_DICT
    if isReverse:
        return next(key for key, value in action_dict.items() if search_key == value)
    else:
        return action_dict[search_key]


def prompt_key():
    return inquirer.text(
        message="Enter the issue key (ex. SPF-101):",
        validate=EmptyInputValidator(),
    ).execute()


def prompt_comment():
    return inquirer.text(
        message="Enter your comment here:",
        validate=EmptyInputValidator(),
        multiline=True,
    ).execute()


def prompt_time_spent():
    return inquirer.text(
        message="> Enter the time spent (e.g., 3h, 2d):",
        validate=EmptyInputValidator("Time spent cannot be empty"),
    ).execute()


def prompt_date():
    return inquirer.text(
        message="Started date (YYYY/MM/DD) (You can leave it empty):",
    ).execute()

def prompt_summary():
    return inquirer.text(
        message="> Enter the task summary:",
        validate=EmptyInputValidator("Summary cannot be empty"),
    ).execute()


def prompt_desc():
    return inquirer.text(
        message="> Enter the task description:",
        validate=EmptyInputValidator("Description cannot be empty"),
    ).execute()


def prompt_priority():
    return inquirer.select(
        message="> Select the task priority:",
        choices=["P2", "P1", "P0", "P3"],
    ).execute()


def prompt_labels(origin_labels, type_labels, project_labels):
    # Allow the user to select multiple labels
    labels_origin = inquirer.checkbox(
        message="Select ORIGIN labels for the task:",
        choices=origin_labels,
        instruction="(Use space to select, Enter to confirm)",
    ).execute()

    labels_type = inquirer.checkbox(
        message="Select TYPE labels for the task:",
        choices=type_labels,
        instruction="(Use space to select, Enter to confirm)",
    ).execute()

    labels_project = inquirer.checkbox(
        message="Select PROJECT labels for the task:",
        choices=project_labels,
        instruction="(Use space to select, Enter to confirm)",
    ).execute()
    return labels_origin + labels_type + labels_project


def get_user_input(labels_conf):
    # Get input for required fields
    summary = prompt_summary()
    desc = prompt_desc()
    priority = prompt_priority()

    # Additional fields
    labels = None
    if labels_conf["is_enable"]:
        conf = labels_conf["labels"]
        labels = prompt_labels(
            origin_labels=conf["origin"].split(','),
            type_labels=conf["type"].split(','),
            project_labels=conf["project"].split(','),
        )

    print(f"\nSelected labels: {labels if labels else 'None'}\n")

    # Story points
    story_points = inquirer.text(
        message="> Enter the story points (numeric value):",
        validate=lambda result: result.isdigit() or "Story points must be a number",
    ).execute()

    # Estimated time
    estimated_time = inquirer.text(
        message="> Enter the estimated time (e.g., 3h, 2d):",
        validate=EmptyInputValidator("Estimated time cannot be empty"),
    ).execute()

    # Watchers: Pre-select default watchers and allow custom input
    watchers = DEFAULT_WATCHERS.copy()

    additional_watchers = inquirer.text(
        message="> Enter additional watchers (comma-separated emails):",
    ).execute()

    # Combine default and additional watchers
    if additional_watchers.strip():
        watchers.extend([w.strip() for w in additional_watchers.split(",")])

    # Convert to correct format for Jira
    watcher_field = [{"name": watcher} for watcher in watchers]

    print(f"\nWatchers:: {watchers}\n")

    # Assignee selection
    assignee = inquirer.select(
        message="> Assign this task to:", choices=ASSIGNEE_CHOICES
    ).execute()

    return {
        "summary": summary,
        "description": description,
        "priority": {"name": priority},
        "labels": labels,
        "story_points": int(story_points),
        "estimated_time": estimated_time,
        "watchers": watcher_field,
        "assignee": {"name": assignee},
    }


def get_subtask_input():
    # Get input for required fields
    summary = inquirer.text(
        message="> Enter the task summary:",
        validate=EmptyInputValidator("Summary cannot be empty"),
    ).execute()

    description = inquirer.text(
        message="> Enter the task description:",
        validate=EmptyInputValidator("Description cannot be empty"),
    ).execute()

    # Estimated time
    estimated_time = inquirer.text(
        message="> Enter the estimated time (e.g., 3h, 2d):",
        validate=EmptyInputValidator("Estimated time cannot be empty"),
    ).execute()

    # Assignee selection
    assignee = inquirer.select(
        message="> Assign this task to:", choices=ASSIGNEE_CHOICES
    ).execute()

    return {
        "summary": summary,
        "description": description,
        "estimated_time": estimated_time,
        "assignee": {"name": assignee},
    }



# Main entry point
if __name__ == "__main__":
    # Initialization
    console = Console()

    secrets = check_for_existing_secrets()
    if secrets:
        print("Secrets loaded successfully!")
    else:
        print("No secrets found. A new secret file has been created.")
        exit()

    get_user_input(secrets["labels_conf"])

    # Use the secrets to access the JIRA API
    jira_client = connect_to_jira(
        server_url=secrets["server_url"],
        username=secrets["username"],
        api_token=secrets["api_token"],
        jira_type=secrets["jira_type"],
        ssl_cert=secrets["ssl_cert"],
    )
    if jira_client:
        print("Connected to Jira successfully!")
    else:
        print("Failed to connect to Jira. Please check your secrets and try again.")
        exit()
    while True:
        # Prompt the user for the action they want to perform
        action = inquirer.select(
            message="What do you want to do?",
            choices=get_action_list(),
            default=get_action_description("exit", False),
        ).execute()

        # Perform the selected action
        if get_action_description(action) == "list_issues":
            # Prompt the user for the type of issues to be revealed
            filter = inquirer.select(
                message="Choose the filter you want to get",
                choices=[
                    "Open",
                    "Active",
                    "Done",
                ],
                default="Active",
            ).execute()

            issues = search_for_issues(jira_client, secrets["project_key"], filter)
            if issues:
                display_table(console, issues)
        elif get_action_description(action) == "search_issue":
            # Prompt the user for the issue key
            key = inquirer.text(
                message="Type issue key:", validate=EmptyInputValidator()
            ).execute()

            filter = f"key = {key}"

            issues = search_for_issues(jira_client, secrets["project_key"], filter)
            if issues:
                display_table(console, issues)
        elif get_action_description(action) == "transition":
            # Prompt the user for the issue key to be transitioned
            key = prompt_key()
            transition_in_loop(jira_client, key)
        elif get_action_description(action) == "comment":
            key = prompt_key()
            comment = prompt_comment()
            is_okay = add_comment_to_issue(jira_client, key, comment)

            if is_okay:
                will_log_work = inquirer.select(
                    message=f"Will you log work for {key} with the same comment:",
                    choices=["Yes", "No"],
                ).execute()

                if will_log_work == "Yes":
                    # Time spent
                    time_spent = prompt_time_spent()
                    jira_date = None
                    date = prompt_date()
                    if date:
                        # Convert the date to JIRA format
                        jira_date = convert_to_jira_date(date)
                    log_work_with_date(
                        jira_client,
                        key,
                        time_spent,
                        comment,
                        jira_date,
                    )
        elif get_action_description(action) == "log_work":
            # Key and comment
            key = prompt_key()
            comment = prompt_comment()

            # Time spent
            time_spent = prompt_time_spent()
            date = prompt_date()

            jira_date = None
            if date:
                # Convert the date to JIRA format
                jira_date = convert_to_jira_date(date)
            log_work_with_date(jira_client, key, time_spent, comment, jira_date)
        elif get_action_description(action) == "create_issue":
            # Get user input for the task
            task_details = get_user_input()

            # Create the task
            task = create_task(
                jira_client,
                project_key=secrets["project_key"],
                summary=task_details["summary"],
                description=task_details["description"],
                priority=task_details["priority"],
                labels=task_details["labels"],
                customfield_10002=task_details[
                    "story_points"
                ],  # Example custom field for story points
                timetracking={"originalEstimate": task_details["estimated_time"]},
                assignee=task_details["assignee"],
                customfield_44300=task_details["watchers"],
                server_url=secrets["server_url"],
            )
        else:
            exit()
