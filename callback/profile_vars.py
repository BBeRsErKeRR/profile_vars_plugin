# (C) 2024, BBeRsErKeRR, https://github.com/BBeRsErKeRR
# (C) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
from ansible.plugins.callback import CallbackBase
from ansible.module_utils.six.moves import reduce
from ansible.vars.hostvars import STATIC_VARS
from ansible.template import Templar
import time
import collections
__metaclass__ = type

DOCUMENTATION = '''
    name: profile_vars
    type: aggregate
    short_description: adds time information for load vars to tasks
    description:
      - Ansible callback plugin for timing individual loading inventory variables for each tasks.
      - "Format: VARS: C(<vars start timestamp>) C(<length template all vars>) C(<current elapsed playbook execution time>)"
    requirements:
      - enable in configuration - see examples section below for details.
'''

EXAMPLES = '''
example: >
  To enable, add this to your ansible.cfg file in the defaults block
    [defaults]
    callbacks_enabled=profile_vars
sample output: >
#
#    TASK: [ensure messaging security group exists] ********************************
#    Thursday 11 June 2017  22:50:53 +0100 (0:00:00.721)       0:00:05.322 *********
#    ok: [localhost]
#
#    TASK: [ensure db security group exists] ***************************************
#    Thursday 11 June 2017  22:50:54 +0100 (0:00:00.558)       0:00:05.880 *********
#    changed: [localhost]
#
'''


# define start time
t0 = tn = time.time()


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
        Helper for dump python object to see attributes
    """
    print("DEBUG obj attributes -> %s" % name)
    for attr in dir(obj):
        if hasattr(obj, attr):
            print("obj.%s = %s" % (attr, getattr(obj, attr)))


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'profile_vars'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        self.stats = collections.OrderedDict()
        self.current = None

        self.sort_order = None
        self.summary_only = None
        self.task_output_limit = None
        self._play = None

        super(CallbackModule, self).__init__()

    # def set_options(self, task_keys=None, var_options=None, direct=None):

    #     super(CallbackModule, self).set_options(
    #         task_keys=task_keys, var_options=var_options, direct=direct)

    #     self.sort_order = self.get_option('sort_order')
    #     if self.sort_order is not None:
    #         if self.sort_order == 'ascending':
    #             self.sort_order = False
    #         elif self.sort_order == 'descending':
    #             self.sort_order = True
    #         elif self.sort_order == 'none':
    #             self.sort_order = None

    #     self.summary_only = self.get_option('summary_only')

    #     self.task_output_limit = self.get_option('output_limit')
    #     if self.task_output_limit is not None:
    #         if self.task_output_limit == 'all':
    #             self.task_output_limit = None
    #         else:
    #             self.task_output_limit = int(self.task_output_limit)

    def _display_tasktime(self):
        if not self.summary_only:
            self._display.display("VARS_TIME: " + tasktime())

    def _record_task(self, task):
        """
        Logs the start of each task
        """
        self._display_tasktime()
        timestamp(self)

        # Record the start time of the current task
        # stats[TASK_UUID]:
        #   started: Current task start time. This value will be updated each time a task
        #            with the same UUID is executed when `serial` is specified in a playbook.
        #   elapsed: Elapsed time since the first serialized task was started
        self.current = task._uuid
        if self.current not in self.stats:
            self.stats[self.current] = {
                'started': time.time(), 'elapsed': 0.0, 'name': task.get_name()}
        else:
            self.stats[self.current]['started'] = time.time()
        if self._display.verbosity >= 2:
            self.stats[self.current]['path'] = task.get_path()

    def v2_playbook_on_play_start(self, play):
        self._play = play

    def v2_playbook_on_handler_task_start(self, task):
        # object_dump(task._vars, '_vars')
        object_dump(task, 'task')

    def v2_playbook_on_task_start(self, task, is_conditional):
        play_vars = self._play.vars
        var_manager = self._play.get_variable_manager()
        hosts = var_manager._inventory.get_hosts()
        host_vars = var_manager.get_vars().get('hostvars', None)
        tasktime()
        for host in hosts:
            name = host.get_vars()["inventory_hostname"]
            buf = host_vars.raw_get(name)
            templar = Templar(variables=buf, loader=host_vars._loader)
            for k, v in buf.items():
                try:
                    templar.template(v, fail_on_undefined=False,
                                     static_vars=STATIC_VARS)
                except Exception:
                    pass
        # self._record_task(task)
        # obj.action, obj.name, obj.play, obj.vars, obj._role, obj._uuid
        # object_dump(task, 'task')
        self._display_tasktime()

    def playbook_on_setup(self):
        self._display_tasktime()

    # def playbook_on_stats(self, stats):
    #     self._display_tasktime()
    #     self._display.display(filled("", fchar="="))

    #     timestamp(self)
    #     self.current = None

    #     results = list(self.stats.items())

    #     # Sort the tasks by the specified sort
    #     if self.sort_order is not None:
    #         results = sorted(
    #             self.stats.items(),
    #             key=lambda x: x[1]['elapsed'],
    #             reverse=self.sort_order,
    #         )

    #     # Display the number of tasks specified or the default of 20
    #     results = list(results)[:self.task_output_limit]

    #     # Print the timings
    #     for uuid, result in results:
    #         msg = u"{0:-<{2}}{1:->9}".format(result['name'] + u' ', u' {0:.02f}s'.format(result['elapsed']), self._display.columns - 9)
    #         if 'path' in result:
    #             msg += u"\n{0:-<{1}}".format(result['path'] + u' ', self._display.columns)
    #         self._display.display(msg)
