# -*- coding: utf-8 -*-
"""
OSOS command line interface (CLI)
"""
import os
import click
import pandas as pd
import logging
from rex import init_logger
from osos.osos import Osos
from osos.version import __version__


logger = logging.getLogger(__name__)


@click.command()
@click.version_option(version=__version__)
@click.option('--config', '-c', default=None, required=False,
              type=click.Path(exists=True),
              help='Path to .csv config file with columns for name, '
              'git_owner, git_repo, pypi_name, and cahce_file. Either input '
              'this for multiple osos jobs or all of the argument explicitly '
              'for a single osos job.')
@click.option('--git_owner', '-go', required=False, default=None, type=str,
              help='Github repository owner, e.g. '
              'https://github.com/{git_owner}/{git_repo}')
@click.option('--git_repo', '-gr', required=False, default=None, type=str,
              help='Github repository name, e.g. '
              'https://github.com/{git_owner}/{git_repo}')
@click.option('--pypi_name', '-pn', required=False, default=None, type=str,
              help='pypi package name. Note that this should include the '
              'prefix for nrel packages e.g. reV -> nrel-rev. This can be '
              'None if there is no pypi package.')
@click.option('--fpath_out', '-f', required=False, default=None, type=str,
              help='Output file to save the osos output table. If the file '
              'exists, it will be updated with the latest data.')
@click.option('-v', '--verbose', is_flag=True,
              help='Flag to turn on debug logging. Default is not verbose.')
@click.pass_context
def main(ctx, config, git_owner, git_repo, pypi_name, fpath_out, verbose):
    """OSOS command line interface (CLI)."""
    ctx.ensure_object(dict)

    msg = 'Need to input either config or (git_owner & git_repo & fpath_out)'
    c1 = (config is not None)
    c2 = (git_owner is not None and git_repo is not None
          and fpath_out is not None)
    assert c1 or c2, msg

    if verbose:
        init_logger('osos', log_level='DEBUG')
    else:
        init_logger('osos', log_level='INFO')

    if c2 and not c1:
        osos = Osos(git_owner, git_repo, pypi_name=pypi_name)
        osos.update(fpath_out)

    else:
        assert os.path.exists(config), 'config must be a valid filepath'
        assert config.endswith('.csv'), 'config must be .csv'
        config = pd.read_csv(config)
        required = ('name', 'git_owner', 'git_repo', 'fpath_out')
        missing = [r for r in required if r not in config]
        if any(missing):
            msg = f'Config had missing required columns: {missing}'
            logger.error(msg)
            raise KeyError(msg)
        for _, row in config.iterrows():
            row = row.to_dict()
            osos = Osos(row['git_owner'], row['git_repo'],
                        pypi_name=row.get('pypi_name', None))
            osos.update(row['fpath_out'])


if __name__ == '__main__':
    try:
        main(obj={})
    except Exception as e:
        msg = 'Error running osos cli!'
        logger.exception(msg)
        raise RuntimeError(msg) from e
