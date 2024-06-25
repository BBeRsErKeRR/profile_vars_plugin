# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import time

from ansible.module_utils.six.moves import reduce
from ansible.playbook.play_context import PlayContext
from ansible.playbook.task import Task
from ansible.plugins.callback import CallbackBase
from ansible.template import Templar
from ansible.utils.display import Display


# define start time
t0 = tn = time.time()

display = Display()


def secondsToStr(t):
    # http://bytes.com/topic/python/answers/635958-handy-short-cut-formatting-elapsed-time-floating-point-seconds
    def rediv(ll, b):
        return list(divmod(ll[0], b)) + ll[1:]

    return "%d:%02d:%02d.%03d" % tuple(reduce(rediv, [[t * 1000, ], 1000, 60, 60]))


def filled(msg, fchar="*"):
    if len(msg) == 0:
        width = 79
    else:
        msg = "%s " % msg
        width = 79 - len(msg)
    if width < 3:
        width = 3
    filler = fchar * width
    return "%s%s " % (msg, filler)


def timestamp(self):
    if self.current is not None:
        elapsed = time.time() - self.stats[self.current]['started']
        self.stats[self.current]['elapsed'] += elapsed


def tasktime():
    global tn
    time_current = time.strftime('%A %d %B %Y  %H:%M:%S %z')
    time_elapsed = secondsToStr(time.time() - tn)
    time_total_elapsed = secondsToStr(time.time() - t0)
    tn = time.time()
    return filled('%s (%s)%s%s' % (time_current, time_elapsed, ' ' * 7, time_total_elapsed))


def object_dump(obj, name):
    """
        Функция для работы в режиме debug, необходима для возможности сдампить объект и его аттрибуты
    """
    display.display("DEBUG obj attributes -> %s" % name)
    for attr in dir(obj):
        if hasattr(obj, attr):
            display.display("obj.%s = %s" % (attr, getattr(obj, attr)))


def assign_wrap_function_args_kwargs(obj, funcname, cls, host, task):
    _owerriden = getattr(obj, funcname)

    def wrapped(self, *args, **kwargs):
        tn1 = time.time()
        td = time.time() - tn1
        res = _owerriden(*args, **kwargs)
        # if td >= 0.5:
        time_elapsed = secondsToStr(td)
        display.display(
            f"TOTAL_VARS_TIME({cls.__name__}.{funcname}) H:{host}| T:{task._uuid}| -> {time_elapsed}")
        return res
    setattr(obj, funcname, wrapped.__get__(obj, cls))


def assign_wrap_function_kwargs(obj, funcname, cls, host, task):
    _owerriden = getattr(obj, funcname)

    def wrapped(self, **kwargs):
        tn1 = time.time()
        td = time.time() - tn1
        res = _owerriden(**kwargs)
        # if td >= 0.5:
        time_elapsed = secondsToStr(td)
        display.display(
            f"TOTAL_VARS_TIME({cls.__name__}.{funcname}) H:{host}| T:{task._uuid}| -> {time_elapsed}")
        return res
    setattr(obj, funcname, wrapped.__get__(obj, cls))


def assign_wrap_function_args(obj, funcname, cls, host, task):
    _owerriden = getattr(obj, funcname)

    def wrapped(self, *args):
        tn1 = time.time()
        td = time.time() - tn1
        res = _owerriden(*args)
        # if td >= 0.5:
        time_elapsed = secondsToStr(td)
        display.display(
            f"TOTAL_VARS_TIME({cls.__name__}.{funcname}) H:{host}| T:{task._uuid}| -> {time_elapsed}")
        return res
    setattr(obj, funcname, wrapped.__get__(obj, cls))


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 1.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'profile_vars'

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display=display)
        self.play = None

    def set_play_context(self, play_context):
        func_exec_set_task_and_variable_override = getattr(
            play_context, 'set_task_and_variable_override')

        def set_task_and_variable_override(self, task, variables, templar):
            host = variables.get('inventory_hostname')
            new_play_context = func_exec_set_task_and_variable_override(
                task=task, variables=variables, templar=templar)
            func_exec_template = getattr(templar, 'template')

            def custom_template(self, variable, **kwargs):
                tn1 = time.time()
                res = func_exec_template(variable, **kwargs)
                td = time.time() - tn1
                if td >= 0.15:
                    time_elapsed = secondsToStr(td)
                    res_v = str(variable)[0: 300]
                    display.display(
                        f"TEMPLATE_TIME   H:{host}| T:{task._uuid}| V:{res_v}| -> {time_elapsed}")
                return res

            templar.template = custom_template.__get__(templar, Templar)

            # assign_wrap_function_args(
            #     task, 'evaluate_conditional_with_result', Task, host, task)
            # assign_wrap_function_kwargs(
            #     task, 'post_validate', Task, host, task)
            # assign_wrap_function_kwargs(
            #     new_play_context, 'post_validate', PlayContext, host, task)
            return new_play_context

        play_context.set_task_and_variable_override = set_task_and_variable_override.__get__(
            play_context, PlayContext)
