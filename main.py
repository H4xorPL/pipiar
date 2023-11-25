import requests
import fnmatch
import json
from dotenv import load_dotenv
import os


# Load environment variables from .env file
load_dotenv()

class Repo_Settings:
    def __init__(self, owner, repo, authors, paths):
        self.owner = owner
        self.repo = repo
        self.authors = authors
        self.paths = paths

class Pull_Request:
    def __init__(self, number, title):
        self.number = number
        self.title = title
        self.state = "UNKNOWN"
        self.mergeable = None
        self.number_of_commits = None
        self.created_at = None
        self.reviews_by_author = {}

    def __str__(self):
        return f'pr: {self.title} number: {self.number} is in state {self.state}, has reviews: {self.reviews_by_author}\nmergeable: {self.mergeable} and created at: {self.created_at}'

def get_github_token():
    return os.getenv("GITHUB_PERSONAL_TOKEN")

def load_data_from_file(data_file_path):
    try:
        with open(data_file_path, "r") as file:
            json_data = json.load(file)
        return json_data
    except FileNotFoundError:
        print(f"JSON data file not found at: {data_file_path}")
        exit(1)
    except json.decoder.JSONDecodeError as e:
        print(f"Error loading JSON data: {e}")
        exit(1)


def unmarshal_to_repo_settings(json_data):
    repo_settings_list = []
    for item in json_data:
        repo_settings = Repo_Settings(
            owner=item['owner'],
            repo=item['repo'],
            authors=item['authors'],
            paths=item['paths']
        )
        repo_settings_list.append(repo_settings)
    return repo_settings_list

def get_open_pull_requests(owner, repo, authors, paths):
    token = get_github_token()

    pull_requests_total = {}
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    params = {'state': 'open', 'sort': 'created'}
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f'Error getting open pull requests: {response.status_code}')
        return None

    pull_requests = response.json()

    for pull_request in pull_requests:
        pr = Pull_Request(pull_request["number"], pull_request['title'])

        if not (author_tracked(pull_request, authors) or path_matched(owner, repo, pr, paths)):
            print(f'author {pull_request["user"]["login"]} not tracked and no matched path. Skipping PR number: {pull_request["number"]}.')
            continue

        check_pull_request_details(owner, repo, pr, token)
        check_pull_request_reviews(owner, repo, pr, token)
        determine_pull_request_state(pull_request=pr)

        pull_requests_total.setdefault(repo, []).append(pr)
    
    return pull_requests_total

def check_pull_request_details(owner, repo, pull_request, token):
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pull_request.number}'
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f'Error getting pull request number {pull_request.number} details: {response.status_code}')
        return None

    details = response.json()

    pull_request.number_of_commits = details["commits"]
    pull_request.mergeable = details['mergeable']
    pull_request.created_at = details['created_at']

    return pull_request

def check_pull_request_reviews(owner, repo, pull_request, token):
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pull_request.number}/reviews'
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f'Error getting pull request number {pull_request.number} reviews: {response.status_code}')
        return None

    reviews_by_author = {}

    details = response.json()
    for review in details:
        author_login = review['user']['login']
        if author_login in reviews_by_author and reviews_by_author[author_login] == "CHANGES_REQUESTED" and review["state"] != "APPROVED":
            continue
        reviews_by_author[author_login] = review['state']

    pull_request.reviews_by_author = reviews_by_author

    return pull_request

def determine_pull_request_state(pull_request):
    state = "AWAITING_REVIEWS"

    for review in pull_request.reviews_by_author.values():
        if review == "CHANGES_REQUESTED":
            state = "CHANGES_REQUESTED"
        elif review == "APPROVED" and state != "CHANGES_REQUESTED":
            state = "APPROVED"
        elif review == "COMMENTED" and state not in ["CHANGES_REQUESTED", "APPROVED"]:
            state = "COMMENTED"

    pull_request.state = state
    return pull_request

def author_tracked(pull_request, authors):
    return pull_request['user']['login'].lower() in authors

def path_matched(owner, repo, pull_request: Pull_Request, paths):
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pull_request.number}/files'
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f'Error getting pull request number {pull_request.number} details: {response.status_code}')
        return False

    details = response.json()
    for file in details:
        for path in paths:
            if fnmatch.fnmatch(file["filename"], path):
                print(f'{file["filename"]}')
                return True

    return False

# Load your JSON data from a file
json_data_file_path = "settings_data.json"
json_data = load_data_from_file(json_data_file_path)

# Unmarshal JSON data to a list of Repo_Settings objects
repo_settings_list = unmarshal_to_repo_settings(json_data)

# Now, repo_settings_list contains a list of Repo_Settings objects that you can use in your program
for repo_settings in repo_settings_list:
    print(f"Owner: {repo_settings.owner}, Repo: {repo_settings.repo}, Authors: {repo_settings.authors}, Paths: {repo_settings.paths}")

    pull_requests_total = get_open_pull_requests(repo_settings.owner, repo_settings.repo, repo_settings.authors, repo_settings.paths)

    for pr in pull_requests_total.get(repo_settings.repo, []):
        print(f'{pr}')
