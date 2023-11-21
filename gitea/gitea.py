import json
import logging
from typing import List, Dict, Union

import requests
import urllib3
from frozendict import frozendict
from requests import Response

from .apiobject import User, Organization, Repository, Team
from .exceptions import (
    NotFoundRequestException,
    ConflictRequestException,
    UnauthorizedRequestException,
    UncaughtException,
    ApiValidationRequestException,
    AlreadyExistsRequestException,
)


class Gitea:
    """Object to establish a session with Gitea."""

    ADMIN_CREATE_USER = """/admin/users"""
    GET_USERS_ADMIN = """/admin/users"""
    ADMIN_REPO_CREATE = """/admin/users/%s/repos"""  # <ownername>
    GENERATE_REPO_WITH_TEMPLATE = """/repos/%s/%s/generate"""  # <template_owner>, <template_repo>
    GITEA_VERSION = """/version"""
    GET_USER = """/user"""
    GET_REPO = """/repos/%s/%s"""  # <username> <repo>
    CREATE_ORG = """/admin/users/%s/orgs"""  # <username>
    CREATE_TEAM = """/orgs/%s/teams"""  # <orgname>

    def __init__(
        self, gitea_url: str, token_text=None, auth=None, verify=True, log_level="INFO"
    ):
        """Initializing Gitea-instance

        Args:
            gitea_url (str): The Gitea instance URL.
            token_text (str, None): The access token, by default None.
            auth (tuple, None): The user credentials
                `(username, password)`, by default None.
            verify (bool): If True, allow insecure server connections
                when using SSL.
            log_level (str): The log level, by default `INFO`.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.headers = {
            "Content-type": "application/json",
        }
        self.url = gitea_url
        self.requests = requests.Session()

        # Manage authentification
        if not token_text and not auth:
            raise ValueError("Please provide auth or token_text, but not both")
        if token_text:
            self.headers["Authorization"] = "token " + token_text
        if auth:
            self.requests.auth = auth

        # Manage SSL certification verification
        self.requests.verify = verify
        if not verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def __get_url(self, endpoint):
        url = self.url + "/api/v1" + endpoint
        self.logger.debug("Url: %s" % url)
        return url

    def _handle_response_code(
        self, response: Response, allowed_codes: list[int] = None, data: dict = None
    ):
        if allowed_codes is None:
            allowed_codes = [200, 201]
        if response.status_code not in allowed_codes:
            message = (
                f"Received status code: "
                f"{response.status_code} ({response.url}) {response.text}"
            )
            self.logger.error(message)
            if data:
                self.logger.error(f"With info: {data} ({self.headers})")
            self.logger.error(f"Answer: {response.text}")
            if response.status_code in [404]:
                raise NotFoundRequestException(response)
            if response.status_code in [403]:
                raise UnauthorizedRequestException(response)
            if response.status_code in [409]:
                raise ConflictRequestException(response)
            if response.status_code in [422]:
                raise ApiValidationRequestException(response)
            raise UncaughtException(response)

    @staticmethod
    def parse_result(result) -> Dict:
        """Parses the result-JSON to a dict."""
        if result.text and len(result.text) > 3:
            return json.loads(result.text)
        return {}

    def requests_get(self, endpoint: str, params=frozendict(), sudo=None):
        combined_params = {}
        combined_params.update(params)
        if sudo:
            combined_params["sudo"] = sudo.username
        response = self.requests.get(
            self.__get_url(endpoint), headers=self.headers, params=combined_params
        )
        self._handle_response_code(response)
        return self.parse_result(response)

    def requests_get_paginated(
        self,
        endpoint: str,
        params=frozendict(),
        sudo=None,
        page_key: str = "page",
        page_limit: int = 0,
    ):
        page = 1
        combined_params = {}
        combined_params.update(params)
        aggregated_result = []
        while True:
            combined_params[page_key] = page
            result = self.requests_get(endpoint, combined_params, sudo)
            if not result:
                return aggregated_result
            aggregated_result.extend(result)
            page += 1
            if page_limit and page > page_limit:
                return aggregated_result

    def requests_put(self, endpoint: str, data: dict = None):
        if not data:
            data = {}
        response = self.requests.put(
            self.__get_url(endpoint), headers=self.headers, data=json.dumps(data)
        )
        self._handle_response_code(response, [200, 204])

    def requests_delete(self, endpoint: str):
        response = self.requests.delete(self.__get_url(endpoint), headers=self.headers)
        self._handle_response_code(response, [204])

    def requests_post(self, endpoint: str, data: dict):
        response = self.requests.post(
            self.__get_url(endpoint), headers=self.headers, data=json.dumps(data)
        )
        self._handle_response_code(response, [200, 201, 202])
        return self.parse_result(response)

    def requests_patch(self, endpoint: str, data: dict):
        response = self.requests.patch(
            self.__get_url(endpoint), headers=self.headers, data=json.dumps(data)
        )
        self._handle_response_code(response, [200, 201])
        return self.parse_result(response)

    def get_orgs_public_members_all(self, orgname):
        path = "/orgs/" + orgname + "/public_members"
        return self.requests_get(path)

    def get_orgs(self):
        path = "/admin/orgs"
        results = self.requests_get(path)
        return [Organization.parse_response(self, result) for result in results]

    def get_user(self):
        result = self.requests_get(Gitea.GET_USER)
        return User.parse_response(self, result)

    def get_repo(self, username, repoName):
        result = self.requests_get(Gitea.GET_REPO % (username, repoName))
        return Repository.parse_response(self, result)

    def get_version(self) -> str:
        result = self.requests_get(Gitea.GITEA_VERSION)
        return result["version"]

    def get_users(self) -> List[User]:
        results = self.requests_get(Gitea.GET_USERS_ADMIN)
        return [User.parse_response(self, result) for result in results]

    def get_user_by_email(self, email: str) -> User:
        users = self.get_users()
        for user in users:
            if user.email == email or email in user.emails:
                return user
        return None

    def get_user_by_name(self, username: str) -> User:
        users = self.get_users()
        for user in users:
            if user.username == username:
                return user
        return None

    def create_user(
        self,
        user_name: str,
        email: str,
        password: str,
        full_name: str = None,
        login_name: str = None,
        change_pw=True,
        send_notify=True,
        source_id=0,
    ):
        """Create User.
        Throws:
            AlreadyExistsException, if the User exists already
            Exception, if something else went wrong.
        """
        if not login_name:
            login_name = user_name
        if not full_name:
            full_name = user_name
        request_data = {
            "source_id": source_id,
            "login_name": login_name,
            "full_name": full_name,
            "username": user_name,
            "email": email,
            "password": password,
            "send_notify": send_notify,
            "must_change_password": change_pw,
        }

        self.logger.debug("Gitea post payload: %s", request_data)
        try:
            result = self.requests_post(Gitea.ADMIN_CREATE_USER, data=request_data)
            if "id" in result:
                self.logger.info(
                    "Successfully created User %s <%s> (id %s)",
                    result["login"],
                    result["email"],
                    result["id"],
                )
                self.logger.debug("Gitea response: %s", result)
            else:
                self.logger.error(result["message"])
                raise Exception("User not created... (gitea: %s)" % result["message"])
            user = User.parse_response(self, result)
            return user
        except ApiValidationRequestException as e:
            if "user already exists" in e.response.text:
                raise AlreadyExistsRequestException(e.response)
            raise e

    def create_repo(
        self,
        repoOwner: Union[User, Organization],
        repoName: str,
        description: str = "",
        private: bool = False,
        autoInit=True,
        gitignores: str = None,
        license: str = None,
        readme: str = "Default",
        issue_labels: str = None,
        default_branch="master",
        template=False
    ):
        """Create a Repository as the administrator

        Throws:
            AlreadyExistsException: If the Repository exists already.
            Exception: If something else went wrong.

        Note:
            Non-admin users can not use this method. Please use instead
            `gitea.User.create_repo` or `gitea.Organization.create_repo`.
        """
        # although this only says user in the api, this also works for
        # organizations
        assert isinstance(repoOwner, User) or isinstance(repoOwner, Organization)
        try:
            result = self.requests_post(
                Gitea.ADMIN_REPO_CREATE % repoOwner.username,
                data={
                    "name": repoName,
                    "description": description,
                    "private": private,
                    "auto_init": autoInit,
                    "gitignores": gitignores,
                    "license": license,
                    "issue_labels": issue_labels,
                    "readme": readme,
                    "default_branch": default_branch,
                    "template": template,
                },
            )
            if "id" in result:
                self.logger.info("Successfully created Repository %s " % result["name"])
            else:
                self.logger.error(result["message"])
                raise Exception(
                    "Repository not created... (gitea: %s)" % result["message"]
                )
            return Repository.parse_response(self, result)
        except ConflictRequestException as e:
            if "The repository with the same name already exists" in e.response.text:
                raise AlreadyExistsRequestException(e.response)
            raise e

    def create_repo_with_template(
            self,
            repo_owner: Union[User, Organization],
            repo_name: str,
            template_owner: str,
            template_repo: str,
            description: str = "",
            private: bool = False,
            default_branch: str = "master",
            avatar: bool = True,
            topics: bool = True,
            git_content: bool = True,
            git_hooks: bool = True,
            labels: bool = True,
            webhooks: bool = True
    ):
        """Create a Repository as the administrator

        Throws:
            AlreadyExistsException: If the Repository exists already.
            Exception: If something else went wrong.

        Note:
            Non-admin users can not use this method. Please use instead
            `gitea.User.create_repo` or `gitea.Organization.create_repo`.
        """
        # although this only says user in the api, this also works for
        # organizations
        assert isinstance(repo_owner, User) or isinstance(repo_owner, Organization)
        try:
            result = self.requests_post(
                Gitea.GENERATE_REPO_WITH_TEMPLATE % (template_owner, template_repo),
                data={
                    "avatar": avatar,
                    "default_branch": default_branch,
                    "description": description,
                    "git_content": git_content,
                    "git_hooks": git_hooks,
                    "labels": labels,
                    "name": repo_name,
                    "owner": repo_owner.username,
                    "private": private,
                    "topics": topics,
                    "webhooks": webhooks
                },
            )
            if "id" in result:
                self.logger.info("Successfully created Repository %s " % result["name"])
            else:
                self.logger.error(result["message"])
                raise Exception(
                    "Repository not created... (gitea: %s)" % result["message"]
                )
            return Repository.parse_response(self, result)
        except ConflictRequestException as e:
            if "The repository with the same name already exists" in e.response.text:
                raise AlreadyExistsRequestException(e.response)
            raise e

    def create_org(
        self,
        owner: User,
        orgName: str,
        description: str,
        location="",
        website="",
        full_name="",
    ):
        assert isinstance(owner, User)
        try:
            result = self.requests_post(
                Gitea.CREATE_ORG % owner.username,
                data={
                    "username": orgName,
                    "description": description,
                    "location": location,
                    "website": website,
                    "full_name": full_name,
                },
            )
            if "id" in result:
                self.logger.info(
                    "Successfully created Organization %s" % result["username"]
                )
            else:
                self.logger.error(
                    "Organization not created... (gitea: %s)" % result["message"]
                )
                self.logger.error(result["message"])
                raise Exception(
                    "Organization not created... (gitea: %s)" % result["message"]
                )
            return Organization.parse_response(self, result)
        except ApiValidationRequestException as e:
            if "user already exists" in e.response.text:
                raise AlreadyExistsRequestException(e.response)
            raise e

    def create_team(
            self,
            org: Organization,
            name: str,
            description: str = "",
            permission: str = "read",
            can_create_org_repo: bool = False,
            includes_all_repositories: bool = False,
            units=(
                "repo.code",
                "repo.issues",
                "repo.ext_issues",
                "repo.wiki",
                "repo.pulls",
                "repo.releases",
                "repo.ext_wiki",
            ),
    ):
        """Creates a Team.

        Args:
            org (Organization): Organization the Team will be part of.
            name (str): The Name of the Team to be created.
            description (str): Optional, None, short description of the new Team.
            permission (str): Optional, 'read', What permissions the members
        """
        try:
            result = self.requests_post(
                Gitea.CREATE_TEAM % org.username,
                data={
                    "name": name,
                    "description": description,
                    "permission": permission,
                    "can_create_org_repo": can_create_org_repo,
                    "includes_all_repositories": includes_all_repositories,
                    "units": units,
                },
            )
            if "id" in result:
                self.logger.info("Successfully created Team %s" % result["name"])
            else:
                self.logger.error("Team not created... (gitea: %s)" % result["message"])
                self.logger.error(result["message"])
                raise Exception("Team not created... (gitea: %s)" % result["message"])
            api_object = Team.parse_response(self, result)
            setattr(
                api_object, "_organization", org
            )  # fixes strange behaviour of gitea
            # not returning a valid organization here.
            return api_object
        except ApiValidationRequestException as e:
            if "team already exists" in e.response.text:
                raise AlreadyExistsRequestException(e.response)
            raise e
