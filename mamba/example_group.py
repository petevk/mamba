# -*- coding: utf-8 -*-

import sys
import copy
from datetime import datetime
from functools import partial

from mamba import error, runnable
from mamba.example import PendingExample


class ExampleGroup(runnable.Runnable):

    def __init__(self, description, parent=None):
        self.description = description
        self.examples = []
        self.parent = parent
        self.hooks = {
            'before_each': [],
            'after_each': [],
            'before_all': [],
            'after_all': []
        }
        self.helpers = {}
        self._error = None

    def __iter__(self):
        return iter(self.examples)

    def execute(self, reporter, execution_context):
        self._start(reporter)
        try:
            self._bind_helpers_to(execution_context)
            self.execute_hook('before_all', execution_context)

            for example in iter(self):
                example.execute(reporter, copy.copy(execution_context))

            self.execute_hook('after_all', execution_context)
        except Exception:
            self._set_failed()

        self._finish(reporter)

    def _start(self, reporter):
        self._begin = datetime.utcnow()
        reporter.example_group_started(self)

    def _bind_helpers_to(self, execution_context):
        for name, method in self.helpers.items():
            setattr(execution_context, name, partial(method, execution_context))

    def execute_hook(self, hook, execution_context):
        if self.parent is not None:
            self.parent.execute_hook(hook, execution_context)

        for registered in self.hooks.get(hook, []):
            try:
                if hasattr(registered, 'im_func'):
                    registered.im_func(execution_context)
                elif callable(registered):
                    registered(execution_context)
            except Exception:
                self._set_failed()

    def _set_failed(self):
        type_, value, traceback = sys.exc_info()
        self.error = error.Error(value, traceback)

    def _finish(self, reporter):
        self.elapsed_time = datetime.utcnow() - self._begin
        reporter.example_group_finished(self)

    @property
    def name(self):
        return self.description

    def append(self, example):
        self.examples.append(example)
        example.parent = self

    @property
    def failed(self):
        return any(example.failed for example in self.examples)

    @property
    def error(self):
        return self._error

    @error.setter
    def error(self, value):
        self._error = value

        for example in self.examples:
            example.error = value


class PendingExampleGroup(ExampleGroup):

    def execute(self, reporter):
        reporter.example_group_pending(self)
        for example in iter(self):
            example.execute(reporter)

    def run(self, reporter):
        self.execute(reporter)

    def append(self, example):
        if not type(example) in [PendingExample, PendingExampleGroup]:
            raise TypeError('A pending example or example group expected')

        super(PendingExampleGroup, self).append(example)
