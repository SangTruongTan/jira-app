#!/usr/bin/python3
import os
import json
import datetime
from datetime import datetime, timezone, timedelta
from InquirerPy import inquirer
from InquirerPy import prompt
from InquirerPy.validator import EmptyInputValidator
from colorama import Fore, Style
from jira import JIRA
from jira import JIRAError
from rich.table import Table
from rich.console import Console
import pytz
import urllib3

# Constant
ACTION_DICT = {
    "create_issue": "1. Create a new (sub-)issue in the project",
    "search_issue": "2. Search for an issue by key or filter",
    "list_issues": "3. List all the issues in the current project",
    "transition": "4. Transition an issue from one state to another",
    "comment": "5. Add a comment to an issue",
    "get_comment": "6. Get comments on an issue",
    "log_work": "7. Log time spent on an issue",
    "get_time": "8. Get time tracking on an issue",
    "update_labels": "9. Update labels",
    "get_childs": "10. Retrieve child tasks from an Epic or Task",
    "exit": "11. Exit the application",
}


# Connect to Jira
def connect_to_jira(server_url, username, api_token, jira_type, ssl_cert=True):
    if ssl_cert == False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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
        {
            "type": "input",
            "name": "priorities",
            "message": "Enter the priory types for the project (separated by comma):",
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
            "default": True,
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
            {
                "type": "input",
                "name": "resolve",
                "message": "Resolve labels (separated by comma):",
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

    configuration.update({"assignees": assignees})

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
def create_task(
    jira, project_key, summary, description, custom_fields, issue_type="Story", **fields
):
    try:
        issue_data = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
        issue_data.update(fields)
        if custom_fields:
            issue_data.update(custom_fields)
        task = jira.create_issue(fields=issue_data)
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
        return sub_task
    except Exception as e:
        print(f"Failed to create sub-task: {e}")
        return None


# Search for current assigned issues
def search_for_issues(jira_client, project_key, user_filter, assignee=None):
    if assignee:
        user = assignee
    else:
        user = "currentUser()"
    filter = f"project={project_key} AND assignee={user} "
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


def display_recent_comments(console, jira_client, issue_key, num):

    comments = get_recent_comments(jira_client, issue_key, num)

    if comments:
        display_comments_helper(console, issue_key, comments)
    else:
        print(f"There is {Fore.YELLOW}no comment to be displayed{Style.RESET_ALL}")


def get_recent_comments(jira_client, issue_key, max_results=5):
    """Retrieves recent comments from a Jira issue.

    Args:
        jira_client: A Jira client instance.
        issue_key: The key of the Jira issue (e.g., "PROJECT-123").
        max_results: The maximum number of comments to retrieve.

    Returns:
        A list of comment objects, or None if there's an error.
    """
    try:
        issue = jira_client.issue(issue_key)
        comments = issue.fields.comment.comments

        # Sort comments by creation date (newest first)
        comments.sort(key=lambda c: c.created, reverse=True)

        return comments[:max_results]  # Return the most recent comments
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


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
def display_table(console, issues, parent_issue=None):
    if parent_issue:
        title = f"Child issues of {parent_issue}"
    else:
        title = "Issue details"

    table = Table(title=title)
    table.add_column("Key", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Status", style="magenta")
    table.add_column("Summary", style="green")
    for issue in issues:
        table.add_row(
            issue.key,
            issue.fields.issuetype.name,
            issue.fields.status.name,
            issue.fields.summary,
        )
    console.print(table)


def display_comments_helper(console, issue_key, comments):
    table = Table(title=f"Comments for {issue_key}")
    table.add_column("Author", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Body", style="blue")
    for comment in comments:
        table.add_row(comment.author.displayName, comment.created, comment.body)
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
def get_date_plus_30_days_formatted(tz_str, date_format="%Y-%m-%d"):
    """Gets the current time + 30 days in the specified timezone and format.

    Args:
        tz_str: A string representing the timezone (e.g., "America/New_York").
        date_format: A string representing the desired date format (default: "%Y-%m-%d").

    Returns:
        A formatted date string, or None if the timezone is invalid.
    """
    try:
        tz = pytz.timezone(tz_str)
        now_tz = datetime.now(tz)
        future_tz = now_tz + timedelta(days=30)
        formatted_date = future_tz.strftime(date_format)
        return formatted_date
    except pytz.exceptions.UnknownTimeZoneError:
        print(f"Invalid timezone: {tz_str}")
        return None


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


def update_jira_labels(
    jira_client,
    issue_key,
    labels_to_add=None,
):
    """Updates the labels of a Jira issue.

    Args:
        jira_client: A Jira client instance.
        issue_key: The key of the Jira issue (e.g., "PROJECT-123").
        labels_to_add: A list of labels to add.

    Returns:
        True if the labels were updated successfully, False otherwise.
        Prints informative messages about the update process or any errors.
    """
    try:
        issue = jira_client.issue(issue_key)
        current_labels = (
            issue.fields.labels or []
        )  # Handle cases where there are no existing labels

        updates = []

        if labels_to_add:
            for label in labels_to_add:
                if label not in current_labels:
                    updates.append(label)
                    print(f"Adding label: {label}")
                else:
                    print(f"Label '{label}' already exists. Skipping.")
        if updates:  # Only update if there are changes
            updates += current_labels
            print(f"New labels:{updates}")
            issue.update(fields={"labels": updates})
            return True
        else:
            print(f"No labels to add or remove for issue {issue_key}")
            return True  # Return true because there was no error.

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False


# Helper
def get_action_list():
    return list(ACTION_DICT.values())


def get_action_description(search_key, isReverse=True):
    action_dict = ACTION_DICT
    if isReverse:
        return next(key for key, value in action_dict.items() if search_key == value)
    else:
        return action_dict[search_key]


def get_time_tracking_info(jira_client, issue_key):
    """Retrieves time tracking information from a Jira issue.

    Args:
        jira_client: A Jira client instance.
        issue_key: The key of the Jira issue (e.g., "PROJECT-123").

    Returns:
        A dictionary containing originalEstimate, remainingEstimate, and timeSpent in seconds, or None if there's an error or no time tracking data.
    """
    try:
        issue = jira_client.issue(issue_key)
        timetracking = issue.fields.timetracking.__dict__

        if timetracking:

            remaining = (
                timetracking["remainingEstimateSeconds"]
                if "remainingEstimateSeconds" in timetracking
                else 0
            )

            timeSpent = (
                timetracking["timeSpentSeconds"]
                if "timeSpentSeconds" in timetracking
                else 0
            )

            original = (
                timetracking["originalEstimateSeconds"]
                if "originalEstimateSeconds" in timetracking
                else remaining + timeSpent
            )
            return {
                "remainingEstimate": remaining,
                "timeSpent": timeSpent,
                "originalEstimate": original,
            }
        else:
            print(f"No time tracking information found for {issue_key}")
            return None
    except JIRAError as e:
        print(f"Jira error: {e.text}")
        return None
    except AttributeError:
        print(
            f"AttributeError: Time tracking might not be enabled for this issue or project."
        )
        return None


def get_child_tasks(jira_instance, parent_issue_key):
    """
    Retrieve child tasks (subtasks or linked issues) for a Jira Epic or Story.

    Args:
        jira_instance (JIRA): An authenticated JIRA instance.
        parent_issue_key (str): The key of the Epic or Story (e.g., "PROJECT-123").

    Returns:
        list: A list of child tasks with their keys, summaries, and statuses.
    """
    try:
        # Fetch the parent issue
        parent_issue = jira_instance.issue(parent_issue_key)

        child_tasks = []

        # Retrieve subtasks if they exist
        if parent_issue.fields.subtasks:
            child_tasks = [subtask for subtask in parent_issue.fields.subtasks]

        # Retrieve issues under and Epic (e.g., issues in an Epic)
        if child_tasks == []:
            filter = f'"Epic Link" = {issue_key}'
            issues = jira_client.search_issues(jql_str=filter, maxResults=50)
            child_tasks = [issue for issue in issues]

        return child_tasks

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def format_working_time(seconds):
    """
    Formats seconds into a human-readable string based on business working days and weeks.
    - 1 business day = 8 hours (28800 seconds)
    - 1 workweek = 5 business days (144000 seconds)

    Args:
        seconds (int): Number of seconds to convert.

    Returns:
        str: A human-readable string in terms of weeks, days, hours, and minutes.
    """
    if seconds is None or seconds <= 0:
        return "0m"

    # Constants for business working time
    SECONDS_IN_MINUTE = 60
    SECONDS_IN_HOUR = 60 * SECONDS_IN_MINUTE
    SECONDS_IN_WORKDAY = 8 * SECONDS_IN_HOUR
    SECONDS_IN_WORKWEEK = 5 * SECONDS_IN_WORKDAY

    # Calculate business time components
    weeks, remaining_seconds = divmod(seconds, SECONDS_IN_WORKWEEK)
    days, remaining_seconds = divmod(remaining_seconds, SECONDS_IN_WORKDAY)
    hours, remaining_seconds = divmod(remaining_seconds, SECONDS_IN_HOUR)
    minutes, _ = divmod(remaining_seconds, SECONDS_IN_MINUTE)

    # Build the output string
    parts = []
    if weeks:
        parts.append(f"{weeks}w")
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append("0m")

    return " ".join(parts)


def display_time_bar(time_info):
    """Displays the time tracking information as a text-based bar."""
    if not time_info:
        return

    total = time_info["originalEstimate"]
    spent = time_info["timeSpent"]
    remaining = time_info["remainingEstimate"]

    if total == 0:
        print("No original estimate set.")
        return

    TIME_WIDTH = 12  # Adjust this to fti the longest possible time string

    spent_percent = int((spent / total) * 20)  # Adjust bar length (20 characters here)
    remaining_percent = int((remaining / total) * 20)

    spent_bar = "[" + "=" * spent_percent + " " * (20 - spent_percent) + "]"
    remaining_bar = "[" + " " * remaining_percent + "-" * (20 - remaining_percent) + "]"

    print(
        f"Time Spent: {format_working_time(spent).ljust(TIME_WIDTH)} {spent_bar} {int(spent/total*100)}%"
    )
    print(
        f"Remaining:  {format_working_time(remaining).ljust(TIME_WIDTH)} {remaining_bar} {int(remaining/total*100)}%"
    )
    print(f"Total:      {format_working_time(total).ljust(TIME_WIDTH)}")


def prompt_key(project_key):
    if not hasattr(prompt_key, "memory"):
        prompt_key.memory = ""
    user_prompt = inquirer.text(
        message="Enter the issue key (ex. SPF-101 or 101):",
        validate=EmptyInputValidator(),
        default=prompt_key.memory,
    ).execute()
    if user_prompt.isdigit():
        key = project_key + "-" + user_prompt
    else:
        key = user_prompt
    prompt_key.memory = key
    return key


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


def prompt_estimated_time():
    return inquirer.text(
        message="> Enter the estimated time (e.g., 3h, 2d):",
        validate=EmptyInputValidator("Estimated time cannot be empty"),
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
        multiline=True,
    ).execute()


def prompt_priority(priorities):
    return inquirer.select(
        message="> Select the task priority:",
        choices=priorities,
    ).execute()


def prompt_story_points():
    return inquirer.text(
        message="> Enter the story points (decimal value):",
    ).execute()


def prompt_labels(origin_labels, type_labels, project_labels):
    # Allow the user to select multiple labels
    labels_origin = (
        inquirer.checkbox(
            message="Select ORIGIN labels for the task:",
            choices=origin_labels,
            instruction="(Use space to select, Enter to confirm)",
        ).execute()
        if origin_labels != [""]
        else []
    )

    labels_type = (
        inquirer.checkbox(
            message="Select TYPE labels for the task:",
            choices=type_labels,
            instruction="(Use space to select, Enter to confirm)",
        ).execute()
        if type_labels != [""]
        else []
    )

    labels_project = (
        inquirer.checkbox(
            message="Select PROJECT labels for the task:",
            choices=project_labels,
            instruction="(Use space to select, Enter to confirm)",
        ).execute()
        if project_labels != [""]
        else []
    )

    return labels_origin + labels_type + labels_project


def prompt_assignee(assignees):
    return inquirer.select(
        message="> Select the assignee:",
        choices=assignees,
    ).execute()


def prompt_watchers():
    return inquirer.text(
        message="> Enter the watchers (comma-separated emails):",
    ).execute()


def prompt_due_date():
    due_date = inquirer.text(
        message="> Enter the due date (YYYY-MM-DD) (Default: 30d):",
    ).execute()
    if due_date == "":
        return get_date_plus_30_days_formatted("UTC")
    else:
        return due_date


def prompt_parent(console, project_key, issue_type="Sub-task"):
    use_list_parent = (
        inquirer.confirm(
            message="Would you like to use predefined parent issue?",
            default=True,
        ).execute()
        if issue_type != "Sub-task"
        else None
    )

    list_parent = get_epic_list(jira_client, project_key) if use_list_parent else None
    if list_parent:
        display_table(console, list_parent)
        user_prompt = inquirer.select(
            message="Select the parent issue key:",
            choices=[issue.key for issue in list_parent],
        ).execute()
        return user_prompt
    else:
        user_prompt = inquirer.text(
            message="Enter the parent issue key (ex. SPF-101 or 101):",
        ).execute()
        if user_prompt.isdigit():
            return project_key + "-" + user_prompt
        else:
            return user_prompt


def prompt_issue_type():
    return inquirer.select(
        message="> Select the issue type:",
        choices=["Story", "Sub-task"],
        default="Story",
    ).execute()


def prompt_number_of_comment():
    return inquirer.text(
        message="> Enter number of comments to be revealed (default: 3):",
        validate=lambda result: (result.strip().isdigit() and int(result) > 0),
        invalid_message="Must be a positive number",
        default="3",
    ).execute()


def prompt_update_labels(labels):
    if labels != [""]:
        return inquirer.select(
            message="Select labels to be updated:",
            choices=labels,
        ).execute()
    else:
        return inquirer.text(
            message="Type your label here:", validate=EmptyInputValidator()
        ).execute()


def get_account(jira_client, jira_type, assignee):
    account = (
        {"name": assignee}
        if jira_type == "server"
        else get_account_id_by_email(jira_client, assignee)
    )
    return account


def get_account_id_by_email(jira_client, email):
    """Retrieves a user's account ID by their email address."""
    try:
        users = jira_client.search_users(query=email, maxResults=1)
        if users:
            return {"accountId": users[0].accountId}
        else:
            print(f"User with email '{email}' not found.")
            return None
    except Exception as e:
        print(f"Jira error: {e.text}")
        return None


def get_user_input(
    jira_type,
    labels_conf,
    default_watchers,
    assignees,
    priorities,
    project_key,
    console,
):
    # Get input for required fields
    summary = prompt_summary()
    description = prompt_desc()

    # Get the issue type
    issue_type = prompt_issue_type()

    # Get the priority
    priorities_list = [p.strip() for p in priorities.split(",")]
    priority = prompt_priority(priorities_list)

    # Get the parent task
    parent_issue_key = prompt_parent(console, project_key, issue_type)

    # Additional fields
    labels = []
    if labels_conf["is_enable"]:
        conf = labels_conf["labels"]
        labels = prompt_labels(
            origin_labels=[l.strip() for l in conf["origin"].split(",")],
            type_labels=[l.strip() for l in conf["type"].split(",")],
            project_labels=[l.strip() for l in conf["project"].split(",")],
        )

    print(f"\nSelected labels: {labels if labels else 'None'}\n")

    # Additional: Story points
    story_points = (
        prompt_story_points()
        if jira_type == "server" and issue_type != "Sub-task"
        else 0
    )

    # Estimated time
    estimated_time = prompt_estimated_time()

    # Additional: Watchers: Pre-select default watchers and allow custom input
    watchers_field = []
    if jira_type == "server":
        watchers = [w.strip() for w in default_watchers.split(",")]
        additional_watchers = prompt_watchers()

        # Combine default and additional watchers
        if additional_watchers.strip():
            watchers.extend([w.strip() for w in additional_watchers.split(",")])

        # Convert to correct format for Jira
        watchers_field = [{"name": watcher} for watcher in watchers]

        print(f"\nWatchers:: {watchers}\n")

    # Assignee selection
    assignee_list = [a.strip() for a in assignees.split(",")]
    assignee = prompt_assignee(assignee_list)

    # Due date
    due_date = prompt_due_date()

    return {
        "summary": summary,
        "description": description,
        "issue_type": issue_type,
        "parent": {"key": parent_issue_key} if parent_issue_key else None,
        "priority": {"name": priority},
        "labels": labels,
        "story_points": float(story_points),
        "estimated_time": estimated_time,
        "watchers": watchers_field,
        "assignee": assignee,
        "duedate": due_date,
    }


def get_subtask_input(assignees):
    # Get input for required fields
    summary = prompt_summary()
    description = prompt_desc()

    # Estimated time
    estimated_time = prompt_estimated_time()

    # Assignee selection
    assignee_list = [a.strip() for a in assignees.split(",")]
    assignee = prompt_assignee(assignee_list)

    return {
        "summary": summary,
        "description": description,
        "estimated_time": estimated_time,
        "assignee": assignee,
    }


def get_epic_list(jira_client, project_key, jira_type="server"):
    if jira_type != "server":
        return None
    if not hasattr(get_epic_list, "memory"):
        get_epic_list.memory = []
        filter = "issuetype = Epic AND Resolution = Unresolved"
        epics = search_for_issues(jira_client, project_key, filter)
        get_epic_list.memory = epics
        return epics
    else:
        return get_epic_list.memory


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

    project_key = secrets["project_key"]
    url = f"{secrets['server_url']}browse/"
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
        print("\n------------------------")
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

            assignee_list = [a.strip() for a in secrets["assignees"].split(",")]
            assignee = prompt_assignee(assignee_list)

            issues = search_for_issues(
                jira_client, secrets["project_key"], filter, assignee
            )
            if issues:
                display_table(console, issues)
        elif get_action_description(action) == "search_issue":
            # Prompt the user for the issue key
            key = prompt_key(project_key)

            filter = f"key = {key}"

            issues = search_for_issues(jira_client, secrets["project_key"], filter)
            if issues:
                display_table(console, issues)
        elif get_action_description(action) == "transition":
            # Prompt the user for the issue key to be transitioned
            key = prompt_key(project_key)
            transition_in_loop(jira_client, key)
        elif get_action_description(action) == "comment":
            key = prompt_key(project_key)
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
        elif get_action_description(action) == "get_comment":
            issue_key = prompt_key(project_key)
            num = int(prompt_number_of_comment())
            display_recent_comments(console, jira_client, issue_key, num)
        elif get_action_description(action) == "log_work":
            # Key and comment
            key = prompt_key(project_key)
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
            task_details = get_user_input(
                secrets["jira_type"],
                secrets["labels_conf"],
                secrets["watchers"],
                secrets["assignees"],
                secrets["priorities"],
                project_key,
                console=console,
            )

            # Custom fields
            custom_fields = None
            if secrets["jira_type"] == "server":
                custom_fields = {
                    "customfield_44300": task_details["watchers"],
                }
                if task_details["parent"]:
                    if task_details["issue_type"] != "Sub-task":
                        custom_fields.update(
                            {
                                "customfield_10434": task_details["parent"]["key"],
                            }
                        )
                    else:
                        custom_fields.update(
                            {
                                "parent": {"key": task_details["parent"]["key"]},
                            }
                        )
                if task_details["issue_type"] != "Sub-task":
                    custom_fields.update(
                        {
                            "customfield_10002": task_details["story_points"],
                        }
                    )
            else:
                if task_details["parent"]:
                    custom_fields = {
                        "parent": task_details["parent"],
                    }
            # Create the task
            account = get_account(
                jira_client, secrets["jira_type"], task_details["assignee"]
            )

            task = create_task(
                jira_client,
                project_key=secrets["project_key"],
                summary=task_details["summary"],
                description=task_details["description"],
                issue_type=task_details["issue_type"],
                priority=task_details["priority"],
                labels=task_details["labels"],
                timetracking={"originalEstimate": task_details["estimated_time"]},
                assignee=account,
                duedate=task_details["duedate"],
                custom_fields=custom_fields,
            )
            if task:
                print(f"\nTask created successfully: {url}{task.key}\n")

                transition_in_loop(jira_client, task.key)

                create_subtask = (
                    inquirer.confirm(
                        message="Do you want to create a subtask for this task?",
                    ).execute()
                    if task_details["issue_type"] != "Sub-task"
                    else False
                )
                if create_subtask:
                    # Custom fields
                    custom_fields = None
                    if secrets["jira_type"] == "server":
                        custom_fields = {
                            "customfield_44300": task_details["watchers"],
                        }
                    subtask_details = get_subtask_input(secrets["assignees"])
                    account = get_account(
                        jira_client, secrets["jira_type"], subtask_details["assignee"]
                    )
                    subtask = create_task(
                        jira_client,
                        project_key=secrets["project_key"],
                        summary=subtask_details["summary"],
                        description=subtask_details["description"],
                        issue_type="Sub-task",
                        priority=task_details["priority"],
                        parent={"key": task.key},
                        labels=task_details["labels"],
                        timetracking={
                            "originalEstimate": task_details["estimated_time"]
                        },
                        assignee=account,
                        duedate=task_details["duedate"],
                        custom_fields=custom_fields,
                    )
                    if subtask:
                        print(f"\nSubtask created successfully: {url}{subtask.key}\n")
                        transition_in_loop(jira_client, subtask.key)
        elif get_action_description(action) == "get_time":
            issue_key = prompt_key(project_key)
            time_info = get_time_tracking_info(jira_client, issue_key)
            display_time_bar(time_info)
        elif get_action_description(action) == "update_labels":
            if secrets["labels_conf"]["is_enable"]:
                temp = secrets["labels_conf"]["labels"]["resolve"].split(",")
                conf = [c.strip() for c in temp]
            else:
                conf = [""]
            label = prompt_update_labels(conf)
            issue_key = prompt_key(project_key)
            if update_jira_labels(jira_client, issue_key, [label]):
                print(f"Labels updated successfully for issue {url}{issue_key}")
        elif get_action_description(action) == "get_childs":
            issue_key = prompt_key(project_key)
            child_tasks = get_child_tasks(jira_client, issue_key)
            if child_tasks:
                display_table(console, child_tasks)
        else:
            exit()
