# -*- coding: utf-8 -*-
"""
Interface module for github API
"""
import re
import datetime
import numpy as np
import pandas as pd
import requests
import os


class Github:
    """Class to call github api and return osos-formatted usage data."""

    BASE_REQ = 'https://api.github.com/repos/{owner}/{repo}'
    TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, owner, repo, token=None):
        """
        Parameters
        ----------
        owner : str
            Repository owner, e.g. https://github.com/{owner}/{repo}
        repo : str
            Repository name, e.g. https://github.com/{owner}/{repo}
        token : str | None
            Github api authorization token. If none this gets retrieved from
            the GITHUB_TOKEN environment variable
        """

        self.base_req = self.BASE_REQ.format(owner=owner, repo=repo)

        self.token = token
        if token is None:
            self.token = os.getenv('GITHUB_TOKEN', None)
        if token is None:
            msg = 'Could not find environment variable "GITHUB_TOKEN".'
            raise OSError(msg)

    def get_request(self, request, **kwargs):
        """Get the raw request output object

        Parameters
        ----------
        request : str
            Request URL, example: "https://api.github.com/repos/NREL/reV/pulls"
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : requests.models.Response
            requests.get() output object.
        """

        headers = kwargs.pop('headers', {})
        if 'Authorization' not in headers:
            headers['Authorization'] = f'token {self.token}'

        out = requests.get(request, headers=headers, **kwargs)
        if out.status_code != 200:
            msg = ('Received unexpected status code "{}" for reason "{}".'
                   '\nRequest: {}\nOutput: {}'
                   .format(out.status_code, out.reason, request,
                           out.text))
            raise IOError(msg)

        return out

    def get_generator(self, request, **kwargs):
        """Call the github API using the requests.get() method and merge all
        the paginated results into a single output

        Parameters
        ----------
        request : str
            Request URL, example: "https://api.github.com/repos/NREL/reV/pulls"
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : generator
            generator of list items in the request output
        """

        headers = kwargs.pop('headers', {})
        if 'Authorization' not in headers:
            headers['Authorization'] = f'token {self.token}'

        params = kwargs.pop('params', {})
        params['page'] = 0

        while True:
            params['page'] += 1
            temp = requests.get(request, headers=headers, **kwargs)
            if temp.status_code != 200:
                msg = ('Received unexpected status code "{}" for reason "{}".'
                       '\nRequest: {}\nOutput: {}'
                       .format(temp.status_code, temp.reason, request,
                               temp.text))
                raise IOError(msg)

            temp = temp.json()
            if not any(temp):
                break
            elif not isinstance(temp, list):
                msg = ('JSON output is type "{}", not list, could '
                       'not parse output from request: "{}"'
                       .format(type(temp), request))
                raise TypeError(msg)
            else:
                for entry in temp:
                    yield entry

    def get_all(self, request, **kwargs):
        """Call the github API using the requests.get() method and merge all
        the paginated results into a single output

        Parameters
        ----------
        request : str
            Request URL, example: "https://api.github.com/repos/NREL/reV/pulls"
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : dict | list
            Json output of the request
        """

        headers = kwargs.pop('headers', {})
        if 'Authorization' not in headers:
            headers['Authorization'] = f'token {self.token}'

        params = kwargs.pop('params', {})
        params['page'] = 0

        out = None
        while True:
            params['page'] += 1
            temp = requests.get(request, headers=headers, **kwargs)
            if temp.status_code != 200:
                msg = ('Received unexpected status code "{}" for reason "{}".'
                       '\nRequest: {}\nOutput: {}'
                       .format(temp.status_code, temp.reason, request,
                               temp.text))
                raise IOError(msg)

            temp = temp.json()
            if not any(temp):
                break
            elif out is None:
                out = temp
            elif isinstance(temp, dict):
                out.update(temp)
            elif isinstance(temp, list):
                out += temp
            else:
                msg = ('JSON output is type "{}", not dict or list, could '
                       'not parse output from request: "{}"'
                       .format(type(temp), request))
                raise TypeError(msg)

        return out

    def _traffic(self, option='clones', **kwargs):
        """Get the daily github repo traffic data for the last two weeks

        Parameters
        ----------
        option : str
            "clones" or "views"
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : pd.DataFrame
            Timeseries of daily git clone data. Includes columns for "views" or
            "clones" and "views_unique" or "clones_unique". Index is a pandas
            datetime index with just the datetime.date part.
        """
        request = self.base_req + f'/traffic/{option}'
        out = self.get_all(request, **kwargs)
        out = pd.DataFrame(out[option])
        out.index = pd.to_datetime(out['timestamp']).dt.date
        out = out.drop('timestamp', axis=1)
        out.index.name = None
        out = out.rename({'count': option, 'uniques': f'{option}_unique'},
                         axis=1)
        return out

    def _issues_pulls(self, option='issues', state='open', **kwargs):
        """Get open/closed issues/pulls for the repo (all have the same
        general parsing format)

        Parameters
        ----------
        option : str
            "issues" or "pulls"
        state : str
            "open" or "closed"
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : dict
            Namespace with keys: "{option}_{state}" and
            "{option}_{state}_*_lifetime" for mean and median lifetime in days
        """

        if 'params' in kwargs:
            kwargs['params']['state'] = state
        else:
            kwargs['params'] = {'state': state}

        request = self.base_req + f'/{option}'
        items = self.get_generator(request, **kwargs)

        lifetimes = []
        d1 = datetime.datetime.now()
        for item in items:
            d0 = datetime.datetime.strptime(item['created_at'],
                                            self.TIME_FORMAT)
            if state == 'closed':
                d1 = datetime.datetime.strptime(item['closed_at'],
                                                self.TIME_FORMAT)

            lifetime = (d1 - d0).total_seconds() / (24 * 3600)
            lifetimes.append(lifetime)

        out = {f'{option}_{state}': len(items),
               f'{option}_{state}_mean_lifetime': np.mean(lifetimes),
               f'{option}_{state}_mean_lifetime': np.median(lifetimes),
               }

        return out

    def issues_closed(self, **kwargs):
        """Get data on the closed repo issues.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : dict
            Namespace with keys: "issues_closed" and mean/median lifetime
            metrics in days
        """
        out = self._issues_pulls(option='issues', state='closed', **kwargs)
        return out

    def issues_open(self, **kwargs):
        """Get data on the open repo issues.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : dict
            Namespace with keys: "issues_open" and and mean/median lifetime
            metrics in days
        """
        out = self._issues_pulls(option='issues', state='open', **kwargs)
        return out

    def pulls_closed(self, **kwargs):
        """Get data on the closed repo pull requests.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : dict
            Namespace with keys: "pulls_closed" and and mean/median lifetime
            metrics in days
        """
        out = self._issues_pulls(option='pulls', state='closed', **kwargs)
        return out

    def pulls_open(self, **kwargs):
        """Get data on the open repo pull requests.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : dict
            Namespace with keys: "pulls_open" and mean/median lifetime
            metrics in days
        """
        out = self._issues_pulls(option='pulls', state='open', **kwargs)
        return out

    def forks(self, **kwargs):
        """Get the number of repo forks.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : int
            The number of forks.
        """
        request = self.base_req + '/forks'
        return len(self.get_all(request, **kwargs))

    def clones(self, **kwargs):
        """Get the daily github repo clone data for the last two weeks.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : pd.DataFrame
            Timeseries of daily git clone data. Includes columns for "clones"
            and "clones_unique". Index is a pandas datetime index with just the
            datetime.date part.
        """
        return self._traffic(option='clones', **kwargs)

    def views(self, **kwargs):
        """Get the daily github repo views data for the last two weeks.

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : pd.DataFrame
            Timeseries of daily git views data. Includes columns for "views"
            and "views_unique". Index is a pandas datetime index with just the
            datetime.date part.
        """
        return self._traffic(option='views', **kwargs)

    def stargazers(self, **kwargs):
        """Get the number of repo stargazers

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : int
            Number of stargazers for the repo.
        """
        request = self.base_req + '/stargazers'
        return len(self.get_all(request, **kwargs))

    def subscribers(self, **kwargs):
        """Get the number of repo subscribers

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : int
            Number of subscribers for the repo.
        """
        request = self.base_req + '/subscribers'
        return len(self.get_all(request, **kwargs))

    def contributors(self, **kwargs):
        """Get the number of repo contributors

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : int
            Number of contributors for the repo.
        """
        request = self.base_req + '/contributors'
        return len(self.get_all(request, **kwargs))

    def commit_count(self, **kwargs):
        """Get the number of repo commits

        Parameters
        ----------
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : int
            Total number of commits to the repo.
        """
        request = self.base_req + '/commits'
        req = self.get_request(request, **kwargs)
        last_url = req.links['last']['url']
        match = re.search(r'page=[0-9]*$', last_url)
        if not match:
            msg = 'Could not find page=[0-9]*$ in url: {}'.format(last_url)
            raise RuntimeError(msg)

        num_pages = int(match.group().replace('page='))
        last_page = self.get_request(last_url, **kwargs)
        out = len(req.json()) * (num_pages - 1) + len(last_page.url())
        return out

    def commits(self, date_iter, search_all=False, **kwargs):
        """Get the number of commits by day in a given set of dates.

        Parameters
        ----------
        date_iter : list | tuple | pd.DatetimeIndex
            Iterable of dates
        search_all : bool
            Flag to search all commits or to terminate early (default) when the
            commit date is before all dates in the date_iter
        kwargs : dict
            Optional kwargs to get passed to requests.get()

        Returns
        -------
        out : pd.DataFrame
            Timeseries of commit data based on date_iter as the index. Includes
            columns for "commits".
        """

        out = pd.DataFrame(index=date_iter)
        out['commits'] = 0
        request = self.base_req + '/commits'
        commit_iter = self.get_generator(request, **kwargs)
        for com in commit_iter:
            c_date = com['commit']['author']['date']
            c_date = datetime.datetime.strptime(c_date, self.TIME_FORMAT)
            c_date = c_date.date()
            stop = True
            for date in date_iter:
                if c_date == date:
                    out.at[date, 'commits'] += 1
                    stop = False
                    break
                elif c_date > date:
                    stop = False

            if stop and not search_all:
                break

        return out
