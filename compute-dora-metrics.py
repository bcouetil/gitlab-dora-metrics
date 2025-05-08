"""
GitLab Dora Metrics Calculator for a project or all projects in a group

This script is designed to calculate key DORA (DevOps Research and Assessment) metrics for GitLab projects and groups.

The metrics and their computation include:
- DORA Deployment Frequency:
    - Measures how often code is deployed to production
    - Computed by counting the number of deployments of features (except hotfixes) to the production environment in a specified time period.
- DORA Lead Time for Changes:
    - Measures the time it takes for code changes to go from commit to deployment
    - Computed as the average time between feature commits (excluding merge commits and hotfixes) and their subsequent deployments.
- Deployments Needing Hotfix:
    - Measures the percentage of deployments that require additional hotfixes.
    - Computed by comparing the number of deployments that required a later hotfix to the total number of deployments of features.
- Time to Last Hotfix:
    - Measures how long it takes to hotfix the service after a deployment.
    - Computed as the average time between hotfix deployments and their associated feature deployments.

Prerequisites:
- pip install requests ansicolors
- An access to all the projects in the group
- Hotfixes are performed by branches whose name starts with 'hotfix', and merges are performed with a merge commit.
- Deployments are performed using the environment feature, and the production environments are distinguished by a common regex.

Usage:
python compute-dora-metrics.py --token <token> --days <nb_days> --group-id <group_id>
python compute-dora-metrics.py --token <token> --days <nb_days> --project-ids <project_id1>,<project_id2>,...

Arguments:
  --token          Your GitLab personal access token.
  --gitlab-host    Your GitLab host (default: gitlab.com).
  --group-id       The ID of the GitLab group to analyze.
  --project-ids    Comma-separated list of GitLab project IDs to analyze.
  --days           The duration of analysis in days (default: 90).
  --branch         The main branch (default: main).
  --env            The environment name for production deployments (default: 'prod*', in a subfolder or not).
  --debug          Whether to print more logs (default: false)

Author: Benoit COUETIL
"""

import requests
import argparse
import re
from datetime import datetime, timedelta
from colors import * # COLORS = ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
from statistics import median

parser = argparse.ArgumentParser(description='Calculate DORA Metrics for a GitLab group and its projects.')
parser.add_argument('--token', required=True, help='Your GitLab personal access token')
parser.add_argument('--gitlab-host', default='gitlab.com', help='Your GitLab host')
parser.add_argument('--group-id', help='The ID of the GitLab group to analyze')
parser.add_argument('--project-ids', help='Comma-separated list of GitLab project IDs to analyze')
parser.add_argument('--branch', default='main|master', help='The main branch')
parser.add_argument('--env', default='(|.*\/)prod.*', help='The prod environment name pattern to match (not search) (default: (|.*\/)prod.*)')
parser.add_argument('--days', type=int, default=90, help='The duration of analysis in days (default 90)')
parser.add_argument("--debug", action=argparse.BooleanOptionalAction, help='Whether to print details of commits (default false)')
args = parser.parse_args()
headers = {'Private-Token': args.token}

def get_available_environments_names(project_id):

    environments_names = []

    params = {
        'per_page': 100,
        'states': 'available',
    }

    any_environment_response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}/environments', headers=headers, params=params)
    if any_environment_response.status_code == 200:
        environments = any_environment_response.json()
        if environments:
            for environment in environments:
                environments_names.append(environment['name'])

    return environments_names

# Function to get the last 10 deployments of environment "prod" for a project
def get_last_successful_deployments(project_id, env_name):

    params = {
        'environment': env_name,
        'per_page': 100,
        'order_by': 'updated_at',
        'sort': 'desc',  # Sort in descending order (oldest first)
        'status': 'success',
        'updated_after': updated_after,
    }
    response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}/deployments', headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        if args.debug: print(red(response.json()))
        return []

# Function to iterate over deployments and commits
def process_deployments(project_id, env_name, deployments, branch):
    if args.debug: print(f"Processing environment '{magenta(env_name)}'")
    last_commit_date_of_previous_deployment = None
    all_time_differences = []
    deployment_dates = set()  # Collect deployment dates for the project
    last_deployment_was_a_hotfix = False
    is_first_deployment = True
    nb_standard_deployments = 0  # Total number of deployments analyzed ; for the last one, we do not know
    nb_standard_deployments_without_hotfix = 0  # Initialize the count for deployments without hotfix

    for deployment in reversed(deployments):
        ref = deployment['ref']
        created_at = deployment['created_at']
        launched_at = deployment['updated_at']
        deployment_commit_message = deployment['deployable']['commit']['message']

        if deployment_commit_message.startswith("Merge branch 'hotfix"):
            print(black(f"Deployment ref={ref} launched_at={launched_at} {red('hotfix')}"))

            if is_first_deployment == True:
                nb_standard_deployments += 1 # A unknown deployment had a hotfix

            last_deployment_was_a_hotfix = True
        else:
            print(black(f"Deployment ref={ref} launched_at={launched_at}"))

            nb_standard_deployments += 1

            if not is_first_deployment == True and not last_deployment_was_a_hotfix:
                nb_standard_deployments_without_hotfix +=1

            if last_commit_date_of_previous_deployment:
                params = {
                    'since': last_commit_date_of_previous_deployment,
                    'until': launched_at,
                    'ref_name': branch,
                    'per_page': 100,
                }
                commits = get_commits(project_id, params)
                if args.debug: print("=> New Commits Since Previous Deployment:")
                if commits:
                    for commit in commits:
                        if not is_merge_commit(commit):
                            time_diff = get_time_delta(launched_at, commit['created_at'])
                            if args.debug: print(f"Commit: {commit['id']}, Commit Date: {commit['created_at']}, Commit Age Until Deploy: {format_time_difference(time_diff)}")
                            all_time_differences.append(time_diff)

            last_deployment_was_a_hotfix = False

            deployment_dates.add(launched_at.split('T')[0])  # Collect the date part, even for the first reference deployment

        last_commit_date_of_previous_deployment = created_at # there is nothing already deployed between created_at and effective_deployment_date
        is_first_deployment = False

    if len(deployments) > 0 and last_deployment_was_a_hotfix == False: # last deployment is considered clean if no hotfix after
        nb_standard_deployments_without_hotfix +=1

    print(green(f"=> {nb_standard_deployments - nb_standard_deployments_without_hotfix} deployments of features needed a later hotfix among {nb_standard_deployments} deployments of features for {project_id} on env"), magenta(env_name))

    if all_time_differences:
        median_time_difference = calculate_median_delta(all_time_differences)
        print(green(f"=> Median commit age before '{env_name}' deployment for {project_id}/{env_name}: {format_time_difference(median_time_difference)}"))

        return all_time_differences, deployment_dates, nb_standard_deployments_without_hotfix, nb_standard_deployments
    else:
        return None, set(), nb_standard_deployments_without_hotfix, nb_standard_deployments  # Return None if no deployments

# Function to check if a commit is a merge commit
def is_merge_commit(commit):
    parent_ids = commit.get('parent_ids', [])

    commit_message = commit.get('title', '')  # Get the commit message

    # Check if the commit message indicates a merge from a hotfix branch
    if commit_message.startswith("Merge branch 'hotfix"):
        if args.debug: print(f"This is a merge commit from a hotfix branch: {commit['id']}")

    if len(parent_ids) > 1: return True
    else: return False

# Function to calculate the average duration in seconds
def calculate_median_delta(time_deltas):
    delta_seconds = [time_delta.total_seconds() for time_delta in time_deltas]
    return timedelta(seconds=median(delta_seconds))

# Function to format a time difference as a human-readable string
def format_time_difference(time_diff):
    total_seconds = int(time_diff.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{days} days, {hours} hours, {minutes} minutes"
    elif hours > 0:
        return f"{hours} hours, {minutes} minutes"
    elif minutes > 0:
        return f"{minutes} minutes"
    else:
        return f"{seconds} seconds"

# Function to format a time difference as a human-readable string
def format_time_days(time_delta):
    return '{0:.2f}'.format(time_delta.total_seconds() / (24 * 60 * 60))

def get_average_pipeline_duration(project_id, updated_after):
    """
    gets the latest pipelines for the project
    ignore pipelines with status failed
    calculate the average duration
    """

    durations = []
    queued_duration: []
    coverage: []
    page = 1
    params = {
        'per_page': 100,
        'updated_after': updated_after,
        'status': "success",
        'source': "merge_request_event",
        'page': page
    }
    # get latest pipeline id list for given project_id
    while True:
        response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}/pipelines', headers=headers, params=params)

        if response.status_code == 200:
            page_pipelines = response.json()
            # print(red(response.json()))
            if not page_pipelines:
                break  # No more pages, exit the loop
            for pipeline in page_pipelines:
                pipeline_response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}/pipelines/{pipeline["id"]}', headers=headers)
                pipeline_detail = pipeline_response.json()
                # print(red(pipeline_response.json()))
                durations.append(timedelta(seconds=pipeline_detail["duration"]))
            page += 1
            params['page'] = page
        else:
            print(f"Error: {response.status_code} {response.reason}")
            break

    print(green(f"=> Pipeline duration '{durations}'"))
    if durations:
        median_duration = calculate_median_delta(durations)
        print(green(f"=> Median commit age before '{env_name}' deployment for {project_id}/{env_name}: {format_time_difference(median_duration)}"))

        return median_duration
    else:
        return None

# Function to get commits within a specified time range
def get_commits(project_id, params):
    if args.debug: print(f"Searching for commits with parameters {params}")
    commits = []

    # Initialize the page number to 1
    page = 1
    params['page'] = page

    while True:
        response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}/repository/commits', headers=headers, params=params)

        if response.status_code == 200:
            page_commits = response.json()
            if not page_commits:
                break  # No more pages, exit the loop
            commits.extend(page_commits)
            page += 1
            params['page'] = page
        else:
            print(red(response.json()))
            break  # Handle errors or stop on non-200 response

    return commits

# Function to calculate time difference in seconds
def get_time_delta(end_time_str, start_time_str):
    end_time = datetime.fromisoformat(end_time_str)
    start_time = datetime.fromisoformat(start_time_str)
    time_delta = end_time - start_time
    return time_delta

# Function to retrieve project IDs for a group and its subgroups recursively
def get_project_ids_with_available_environments_for_group(group_id, full_path):
    nb_projects_found = 0
    project_ids_with_envs = []

    def get_projects_in_group(group_id, full_path, nb_projects_found):
        params = {
            'per_page': 100,
            'archived': False
        }
        response = requests.get(f'https://{args.gitlab_host}/api/v4/groups/{group_id}/subgroups', headers=headers, params=params)
        if response.status_code == 200:
            subgroups = response.json()
            for subgroup in subgroups:
                print(f"📁 found subgroup {cyan(subgroup['full_path'])} in {cyan(full_path)}")
                nb_projects_found = get_projects_in_group(subgroup['id'], subgroup['full_path'], nb_projects_found)
        else:
            print(red(response.json()))

        response = requests.get(f'https://{args.gitlab_host}/api/v4/groups/{group_id}/projects', headers=headers, params=params)
        if response.status_code == 200:
            projects = response.json()
            for project in projects:
                if full_path in project['path_with_namespace']:
                    nb_projects_found += 1
                    print(f" 🗒️ found project {cyan(project['path_with_namespace'])} in {cyan(full_path)}", end="")
                    environments_names = get_available_environments_names(project['id'])
                    if environments_names:
                        print(f", environments: {magenta(environments_names)}")
                        project_ids_with_envs.append(project['id'])
                    else:
                        print("")
                # weird bug: the API return projects not in the group O_o
        else:
            print(red(response.json()))

        return nb_projects_found

    nb_projects_found = get_projects_in_group(group_id, full_path, nb_projects_found)
    return nb_projects_found, project_ids_with_envs

def calculate_time_to_last_hotfix(project_id, deployments):
    ttlh_values = []
    last_hotfix_date = None

    for deployment in deployments:
        commit_message = deployment['deployable']['commit']['message']

        if commit_message.startswith("Merge branch 'hotfix"):
            last_hotfix_date = deployment['updated_at']
        else:
            if last_hotfix_date:
                time_delta = get_time_delta(last_hotfix_date, deployment['updated_at'])
                ttlh_values.append(time_delta)

    if ttlh_values:
        average_ttlh = calculate_median_delta(ttlh_values)
        print(green(f"=> Median Time To Last Hotfix for project {project_id}: {format_time_difference(average_ttlh)}"))
        return average_ttlh
    else:
        return None

def does_branch_exist(project_id, branch_name):
    params = {
        'per_page': 100,
    }
    response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}/repository/branches', headers=headers, params=params)
    if response.status_code == 200:
        branches = response.json()
        return any(branch['name'] == branch_name for branch in branches)
    else:
        print(red(response.json()))
        return False

if __name__ == '__main__':

    updated_after = (datetime.now() - timedelta(days=args.days)).isoformat(timespec='milliseconds')
    print(yellow(f"Checking all deployments after {updated_after}"))
    nb_projects_found = 0

    if args.group_id:
        response = requests.get(f'https://{args.gitlab_host}/api/v4/groups/{args.group_id}', headers=headers)
        if response.status_code == 200:
            nb_projects_found, project_ids_with_env = get_project_ids_with_available_environments_for_group(args.group_id, response.json().get('full_path'))
        else:
            print(red("Group does not exist. Did you provide a project ID ?"))
            exit(1)
        if not project_ids_with_env:
            print("No projects with environments found in the group")
    elif args.project_ids:
        project_ids_with_env = [project_id.strip() for project_id in args.project_ids.split(',')]
        nb_projects_found = len(args.project_ids.split(','))
    else:
        print(red("You must provide either --group-id or --project-ids"))
        exit(1)

    projects_without_prod_env = set()
    projects_without_enough_deployment = set()
    projects_with_analyzed_deployments = set()
    all_projects_time_differences = []
    all_projects_ttlh = []
    all_deployments_dates = set()  # Collect deployment dates across all projects
    nb_total_deployments_without_hotfix = 0
    nb_total_deployments = 0

    for project_id in project_ids_with_env:
        environments_names = []
        has_prod_env = False

        response = requests.get(f'https://{args.gitlab_host}/api/v4/projects/{project_id}', headers=headers)

        if response.status_code != 200:
            print(red(f"Project {project_id} is not reachable (HTTP code {response.status_code})"))
            if args.debug: print(red(response.json()))
            continue

        project_info = response.json()
        project_name = project_info.get('path_with_namespace', 'Unknown Project')
        title = f' Processing project {project_name} (ID {project_id}) '
        print(f"{title:-^100}")
        environments_names = get_available_environments_names(project_id)
        print(f"Environments: {magenta(environments_names)}")

        branch = args.branch.split('|')[0]
        alternative_branch = args.branch.split('|')[1] or "none"

        # Check if the main branch exists
        if len(environments_names)>0 and not does_branch_exist(project_id, branch):
            if not does_branch_exist(project_id, alternative_branch):
                print(red(f"Branch(es) '{args.branch}' does not exist in project {project_name}"))
            else:
                branch = alternative_branch

        for env_name in environments_names:

            if not re.match(args.env, env_name):
                if args.debug: print(black(f"{env_name} does not match {args.env}"))
                continue
            else:
                has_prod_env = True

            deployments = get_last_successful_deployments(project_id, env_name)
            project_time_differences, project_deployment_dates, nb_project_deployments_without_hotfix, nb_project_deployments = process_deployments(project_id, env_name, deployments, branch)

            if project_time_differences is not None:
                all_projects_time_differences += project_time_differences
                projects_with_analyzed_deployments.add(project_name)
            else: # nb_deployments_without_hotfix < 2
                projects_without_enough_deployment.add(project_name)

            all_deployments_dates.update(project_deployment_dates)
            nb_total_deployments += nb_project_deployments
            nb_total_deployments_without_hotfix += nb_project_deployments_without_hotfix

            project_ttlh = calculate_time_to_last_hotfix(project_id, deployments)
            if project_ttlh is not None:
                all_projects_ttlh.append(project_ttlh)

        if has_prod_env == False:
            projects_without_prod_env.add(project_name)

        # print(f"average MR pipeline duration: {get_average_pipeline_duration(project_id, updated_after)}")

    print("")
    print(f"{nb_projects_found} total project(s) analyzed")
    print(f"{black(len(projects_without_prod_env))} project(s) have environments but not a '{args.env}' environment: {black(projects_without_prod_env)}")
    print(f"{blue(len(projects_without_enough_deployment))} project(s) have a '{args.env}' environment but only 0/1 deployment of features in the last {args.days} days: {blue(projects_without_enough_deployment)}")
    print(f"{green(len(projects_with_analyzed_deployments))} project(s) contributed to the metrics: {green(projects_with_analyzed_deployments)}")
    print(f"Checked deployments after {updated_after} (last {args.days} days)")

    if all_deployments_dates:
        num_days_with_deployments = len(all_deployments_dates)
        deployment_frequency_days = args.days / num_days_with_deployments
        print(f"Overall, there has been {green(num_days_with_deployments)} days with at least one non-hotfix deployment for the past {args.days} days")
        deployment_frequency_human_readable = format_time_difference(timedelta(days=deployment_frequency_days))
        print("")
        print(green(f"DORA Deployment Frequency:".ljust(30) + f"{deployment_frequency_days:.2f} days".ljust(15) + f"A deployment of features every {deployment_frequency_human_readable} on average (excluding hotfixes)"))

    if all_projects_time_differences:
        overall_median_time_difference = calculate_median_delta(all_projects_time_differences)
        print(green(f"DORA Lead Time for Changes:".ljust(30) + f"{format_time_days(overall_median_time_difference)} days".ljust(15) + f"The median feature commit age is {format_time_difference(overall_median_time_difference)} when deployed to production (excluding merge commits and hotfixes)"))

    if nb_total_deployments > 0:
        deployments_with_bug_ratio = 1 - ( nb_total_deployments_without_hotfix / nb_total_deployments)
        print(green(f"Deployments Needing Hotfix:".ljust(30) + f"{deployments_with_bug_ratio:.2%}".ljust(15) + f"{nb_total_deployments - nb_total_deployments_without_hotfix} deployments of features needed a later hotfix among {nb_total_deployments} deployments of features"))

    if all_projects_ttlh:
        overall_ttlh = calculate_median_delta(all_projects_ttlh)
        print(green(f"Time to Last Hotfix:".ljust(30) + f"{format_time_days(overall_ttlh)} days".ljust(15) + f"Last hotfix median delay after the associated deployment of features is {format_time_difference(overall_ttlh)}"))

    print("")