from typing import List, Dict, Optional
import requests
import fnmatch
import json
import os
from dotenv import load_dotenv
from json.encoder import JSONEncoder

load_dotenv()

class RepoSettings:
    def __init__(self, owner: str, repo: str, authors: List[str], requested_reviewers: List[str], paths: List[str]):
        self.owner = owner
        self.repo = repo
        self.authors = authors
        self.requested_reviewers = requested_reviewers
        self.paths = paths

class PullRequest:
    def __init__(self, number: int, title: str, url: str):
        self.number = number
        self.title = title
        self.state: str = "UNKNOWN"
        self.mergeable: Optional[bool] = None
        self.number_of_commits: Optional[int] = None
        self.created_at: Optional[str] = None
        self.reviews_by_author: Dict[str, str] = {}
        self.url = url

    def __str__(self) -> str:
        return (
            f'pr: {self.title} number: {self.number} is in state {self.state}, '
            f'has reviews: {self.reviews_by_author}\nmergeable: {self.mergeable} and created at: {self.created_at}'
        )

def get_github_token() -> str:
    return os.getenv("GITHUB_PERSONAL_TOKEN")

def load_data_from_file(data_file_path: str) -> List[Dict]:
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

def unmarshal_to_repo_settings(json_data: List[Dict]) -> List[RepoSettings]:
    repo_settings_list = []
    for item in json_data:
        owner = item.get('owner', '')
        repo = item.get('repo', '')
        authors = item.get('authors', [])
        requested_reviewers = item.get('requested_reviewers', [])
        paths = item.get('paths', [])

        repo_settings = RepoSettings(
            owner=owner,
            repo=repo,
            authors=authors,
            requested_reviewers=requested_reviewers,
            paths=paths
        )

        repo_settings_list.append(repo_settings)
    return repo_settings_list

def get_open_pull_requests(owner: str, repo: str, authors: List[str], requested_reviewers: List[str], paths: List[str]) -> List[PullRequest]:
    token = get_github_token()
    pull_requests_total = []
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    params = {'state': 'open', 'sort': 'created'}
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f'Error getting open pull requests: {response.status_code}')
        return pull_requests_total

    pull_requests = response.json()

    for pull_request in pull_requests:
        pr = PullRequest(pull_request["number"], pull_request['title'], pull_request['html_url'])

        if not (author_tracked(pull_request, authors) or path_matched(owner, repo, pr, token, paths) or
                requested_reviewer_matched(owner, repo, pr, token, requested_reviewers)) and (authors or requested_reviewers or paths):
            continue

        check_pull_request_details(owner, repo, pr, token)
        check_pull_request_reviews(owner, repo, pr, token)
        determine_pull_request_state(pull_request=pr)

        pull_requests_total.append(pr)

    return pull_requests_total

def check_pull_request_details(owner: str, repo: str, pull_request: PullRequest, token:str) -> PullRequest:
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

def check_pull_request_reviews(owner: str, repo: str, pull_request: PullRequest, token:str) -> PullRequest:
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

def determine_pull_request_state(pull_request: PullRequest):
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

def author_tracked(pull_request: PullRequest, authors: List[str]) -> bool:
    return pull_request['user']['login'].lower() in authors

def path_matched(owner: str, repo: str, pull_request: PullRequest, token:str, paths: List[str]) -> bool:
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
                return True

    return False

def requested_reviewer_matched(owner: str, repo: str, pull_request: PullRequest, token:str, requested_reviewers: List[str]) -> bool:
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pull_request.number}'
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f'Error getting pull request number {pull_request.number} details: {response.status_code}')
        return None

    details = response.json()

    for req_reviewer in details['requested_reviewers']:
        for requested_reviewer in requested_reviewers:
            if requested_reviewer.lower() == req_reviewer['login'].lower():
                return True

    return False

def requested_teams_matched(owner: str, repo: str, pull_request: PullRequest, token:str, requested_teams: List[str]) -> bool:
    return False

# Load your JSON data from a file
json_data_file_path = "settings_data.json"
json_data = load_data_from_file(json_data_file_path)

# Unmarshal JSON data to a list of Repo_Settings objects
repo_settings_list = unmarshal_to_repo_settings(json_data)

class RepoPullRequests:
    def __init__(self, repoSettings: RepoSettings):
        self.repoSettings = repoSettings
        self.pullRequests = []

# Use a dictionary to store RepoPullRequests objects with repo_settings.repo as the key
all_repos_dict = {}

for repo_settings in repo_settings_list:
    print(f"Owner: {repo_settings.owner}, Repo: {repo_settings.repo}, Authors: {repo_settings.authors}, Paths: {repo_settings.paths}")

    rpr = RepoPullRequests(repo_settings)

    pull_requests_total2 = get_open_pull_requests(repo_settings.owner, repo_settings.repo, repo_settings.authors, repo_settings.requested_reviewers, repo_settings.paths)

    for pr in pull_requests_total2:
        rpr.pullRequests.append(pr)

    all_repos_dict[repo_settings.repo] = rpr

# Specify the output file path
output_file_path = "output.json"

# Write the JSON data to the file
with open(output_file_path, 'w') as output_file:
    json.dump(all_repos_dict, output_file, default=lambda o: o.__dict__, indent=2)

print(f"JSON data written to {output_file_path}")