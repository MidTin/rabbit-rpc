# -*- coding: utf-8 -*-
import importlib
import imp
import os
import sys

from .base import BaseCommand
from rabbit_rpc.consumer import Consumer
from rabbit_rpc.server import RPCServer


class Worker(BaseCommand):

    name = 'worker'

    def add_arguments(self, parser):
        parser.add_argument(
            '-Q', '--queue', default='default',
            help='setup and bind to the specified queue')
        parser.add_argument(
            '--amqp', default='amqp://guest:guest@localhost:5672/',
            help='specify the broker url')
        parser.add_argument(
            '--django', help='setup django')

    def install_django(self):
        import django
        django.setup()

    def find_consumers(self, related_name='consumers'):
        path = os.getcwd()

        consumers = []
        for dirpath in os.listdir(path):
            if dirpath.startswith('.'):
                continue

            if os.path.isdir(dirpath):
                module = find_related_module(dirpath, related_name)
                if module:
                    for item in dir(module):
                        c = getattr(module, item)
                        if isinstance(c, Consumer):
                            consumers.append(c)

        return consumers

    def execute(self, **options):
        consumers = self.find_consumers()
        if not consumers:
            sys.stderr.write('No consumer was detected.\n')
            sys.exit(1)

        if options.get('django'):
            self.install_django()

        try:
            server = RPCServer(consumers, amqp_url=options['amqp'],
                               queue=options['queue'])
            server.run()
        except KeyboardInterrupt:
            server.stop()
        except Exception as ex:
            sys.stderr.write(ex + '\n')
            sys.exit(1)


def find_related_module(package, related_name):
    """Find module in package."""
    try:
        importlib.import_module(package)
    except ImportError:
        package, _, _ = package.rpartition('.')
        if not package:
            raise

    try:
        pkg_path = importlib.import_module(package).__path__
    except AttributeError:
        return

    try:
        imp.find_module(related_name, pkg_path)
    except ImportError:
        return

    return importlib.import_module('{0}.{1}'.format(package, related_name))
