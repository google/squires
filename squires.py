#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Simple QuIck Readline Enhanced Scripts.

This implements a command tree structure, allowing for
easy readline tab completion, command help, and easy
addition of new commands.

The command tree is a dict. Keys are the name of the command
token (eg 'show', 'set', 'interface', 'terse'), and the
value is another Command object, which can have its own
command descendents.

Once a tree is built, one simply has to call the top level
object with the requested command (Eg ['show', 'interface', 'terse'])
and the tree will be descended until it reaches the desired
command, in this case 'show'->'interface'->'terse' then it
will run 'terse's 'Run' method.

Alternatively, for interactive use, just call '<class>.Prompt()'
and a line will be read with readline completion, and then
executed.

Please see squires_test.py or example.py for simple usage.
"""

__version__ = '0.9.9'

import inspect
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import traceback

import option_lib
import pipe
import readline
COMPLETE_SUFFIX = ''


SHOW_HIDDEN = False  # Force display of hidden commands and options.

# Character used as a pipe to split command line
PIPE_CHAR = pipe.PIPE_CHAR


class Error(Exception):
  pass


class AmbiguousError(Error):
  """Ambiguous option on command line."""
  # TODO(bbuxton): Deal with ambiguous matches. eg, if the
  # possible matches are ('on', 'off') and the command line
  # contains 'o', then the matched value will be 'on', ie the
  # first match.
  pass


class NoMatchError(Error):
  """Subcommand did not match."""


class Command(dict):
  """An element on the command tree.

  Keys are subcommand names, values are instances of Command.

  Attributes:
    name: A string, the name of this command.
    help: A string, the help string for this command.
    ancestors: A list of strings, ancestor command names.
    root: A Command() object, the root of the tree.
    parent: A Command() object, the parent command of this command.
    runnable: A boolean, if this command can be run itself (ie doesnt require
      subcommands). If true '<cr>' is shown in the completion list. If None
      and a method is supplied, default to True, else False.
    options: A list of option.Option() objects for this command.
    hidden: A boolean. If True, the command does not show in tab completion.
    command_line: A list of tokens in the current command line.
    prompt: A string, the command prompt to display. Only valid for the top
      level command.
    method: A method, called from within Run(), unless Run() is overridden.
    execute_command_string: A string, to display as '<cr>' help, if runnable.
    orig_ancestors: A list of strings, ancestors of this command.
    pipetree: A Command(), root of tree after a pipe. If none, there is
      no piping.
    meta: Any object type. Meta information that can be stored by the calling
      program for reference later.
  """

  def __init__(self, name='', help=None, runnable=None, method=None):
    super(Command, self).__init__(self)
    self.name = name
    self.help = help or ''
    self.root = self
    self.parent = None
    self.ancestors = []
    self.options = Options()
    self.options.command = self
    self.command_line = []
    self.hidden = False
    self.prompt = '> '
    self.method = method
    self.pipetree = None
    self.meta = None

    if runnable is None:
      # Set to 'True' if a method is supplied.
      if self.method is not None:
        runnable = True
      else:
        runnable = False
    self.runnable = runnable

    # Help string is method docstring by default.
    if self.method is not None and help is None:
      if hasattr(method, '__doc__'):
        self.help = method.__doc__
    self.execute_command_string = 'Execute this command'
    self.orig_ancestors = []

  def PrepareReadline(self):
    """Prepares readline for our use. DEPRECATED."""
    print '(Squires warning) PrepareReadline() is deprecated and now a NoOp.'

  def AddCommand(self, name, help=None, runnable=None, method=None, pipe=None,
                 meta=None, hidden=False):
    """Convenience function to add a command to the tree.

    Returns the new Command() object, already added to the tree. Options
    can then be added.

    Args:
      name: A string, the full path of the command, eg 'set pager'. If
        it already exists, the old command will be entirely overwritten.
      help: A string. As per the Command() 'help' attribute.
      runnable: A boolean, as per the Command() 'runnable' attribute.
      method: A function which will be the new object's 'Run' method. This
        method will be passed two arguments - the Command object ("self"), and
        the entire command line as a list of strings.
      pipe: A Command object, the pipe command tree. Currently unused.
      meta: Any object. Meta information supplied by the squires user to
        be used by it arbitrarily.
      hidden: A boolean. If True, command does not show up in help or
        tab completion.

    Returns:
      A Command() object.
    """
    name = name.split()
    command = Command(name=name[-1], help=help, runnable=runnable,
                      method=method)
    command.ancestors = name[:-1]
    command.meta = meta
    command.hidden = hidden
    self.root.Attach(command)
    return command

  def AddSubCommand(self, name, **kwargs):
    """Similar to AddCommand(), but added directly below the current Command.

    Args:
      name: A string, the command name relative to the Command() instance.
      that AddSubCommand is called for. eg if this Command is 'set pager' and
      name is 'terminal', the new command is 'set pager terminal'.

    Returns:
      A Command() object, the new command.
    """
    ancestors = ' '.join(self.orig_ancestors) + ' %s %s' % (self.name, name)
    return self.AddCommand(ancestors, **kwargs)

  def __repr__(self):
    return '<Command Object, Name "%s", SubCommands: %s>' % (
        self.name, ','.join(self.keys()))

  def GetPipeTree(self):
    """Get the best pipe tree, climbing the command tree.

    Looks at this object's pipetree. If not none, returns it,
    otherwise ascends the tree until it finds one.

    Returns:
      A Command() object, the matching pipe tree. None if there
      is not any.
    """
    if self.pipetree is not None:
      return self.pipetree
    if self.parent is not None:
      return self.parent.GetPipeTree()
    return None

  @property
  def path(self):
    """Fetches the path of this command.

    Returns:
      A list of str, the names of command objects from the root.
    """
    path = []
    cmd = self
    while cmd.parent:
      path.append(cmd.name)
      cmd = cmd.parent

    path.reverse()
    return path

  def WillPipe(self, line):
    """Returns whether this line will be piped.

    Args:
      line: A list of str, the command line.

    Returns:
      A boolean. If True, a pipe is present and will be processed.
    """
    return self.GetPipeTree() is not None and PIPE_CHAR in line

  def _ReadlinePrepare(self):
    """Prepare readline for use."""
    readline.set_completion_display_matches_hook(
        self.root.FormatCompleterOptions)
    readline.set_completer(self.root.ReadlineCompleter)
    readline.parse_and_bind('tab: complete')
    readline.parse_and_bind('?: possible-completions')
    readline.set_completer_delims(' \t')

    self._old_delims = readline.get_completer_delims()
    readline.set_completer_delims(' ')

  def _ReadlineUnprepare(self):
    """Reset readline."""
    readline.set_completer(None)
    readline.set_completion_display_matches_hook(None)
    readline.set_completer_delims(self._old_delims)

  def Loop(self, prompt=None):
    """Main CLI loop.

    Returns at the termination of the UI (either by the user exiting, or EOF)

    Args:
      prompt: A string, the prompt to display.
    """
    while True:
      try:
        self.Prompt(prompt)
      except KeyboardInterrupt:
        print
      except EOFError:
        print
        break

  def Prompt(self, prompt=None):
    """Prompt user (with readline) then execute command.

    Args:
      prompt: A string, the prompt to display.
    """
    if prompt is not None:
      self.prompt = prompt

    self._ReadlinePrepare()
    line = raw_input(self.prompt)
    self._ReadlineUnprepare()

    try:
      split_line = shlex.split(line)
    except ValueError, e:
      print '%% %s' % e  # Unterminated quote or other parse error.
      return

    try:
      self._SaveHistory()
      self.Execute(split_line)
    except (KeyboardInterrupt, EOFError), e:
      # Catch ctrl-c and eof and pass up.
      raise
    except IOError, e:
      # Would only be seen by a pipe. Suppress useless error.
      pass
    except Exception, e:
      # Other exceptions whilst running command have trace
      # printed, then back to the prompt.
      traceback.print_exc(file=sys.stdout)
    finally:
      self._RestoreHistory()

  def ReadlineCompleter(self, unused_word, state):
    """Readline completion handler.

    This method is registered with readline to perform command
    completion. It tidies up the current command line, before
    passing to self.Completer.
    See the Python readline documentation for more details on
    this method.

    Args:
      unused_word: A string, the current word under the cursor. (unused)
      state: An int, the 'tab press number', indexed at zero.
    Returns:
      A string, the next possible completion, or None.
    """
    initial_candidates = self.FindCurrentCandidates()
    if not initial_candidates:
      print '\nNo valid completions.'
      print self.prompt + readline.get_line_buffer(),
      return None
    candidates = []
    for cand in sorted(initial_candidates):
      candidates.append(cand + COMPLETE_SUFFIX)  # Add space after the token.
      if cand.startswith('<'):
        # Make an additional dummy candidate to force
        # display of these instead of auto-completing.
        candidates.append('%@%@%@' + cand)
    candidates.append(None)  # readline expects None at the end.
    return candidates[state]

  def FormatCompleterOptions(self, unused_substitution, unused_matches,
                             unused_longest):
    """Displays the possible completions, with help text.

    This function is registered in _ReadlinePrepare, and readline
    calls it to display possible completions when needed.
    See readline documentation for more details on this method.

    Args:
      unused_substitution: A str, the current word under the cursor.
      unused_matches: A list, possible tokens that match, as returned by
        ReadlineCompleter.
      unused_longest: An int, the length of the longest match.
    """
    print '\nValid completions:'
    candidates = self.FindCurrentCandidates()
    for candidate in sorted(candidates):
      if not candidate.startswith('%@%@%@'):
        # Print it unless its a dummy candidate (see above).
        print ' %-21s %s' % (candidate, candidates[candidate] or '')
    print self.prompt + readline.get_line_buffer(),

  def FindCurrentCandidates(self):
    """Finds valid completions on the current line.

    Returns:
      A dict. Keys are valid next token, values are help text for each.
    """
    try:
      for quote in ('', "'", '"'):
        # Auto close quotations to allow tab completion.
        try:
          current_line = shlex.split(readline.get_line_buffer() + quote)
          break
        except ValueError, e:
          pass
      else:
        raise  # Re-raise exception that our extra quotes couldnt stop.
      if readline.get_line_buffer().endswith(' '):
        current_line.append(' ')
      return self.Completer(current_line)
    except Exception:
      print '\n%s' % traceback.format_exc()
      return {}

  def Completer(self, current_line):
    """Completion handler.

    Takes the given line, and attempts to return valid
    completions. If necessary, subcommand modules will be
    called.

    Completer is case insensitive - the supplied command is
    matched regardless of case, however returned commands
    may have case.

    Tokens should be supplied pre-processed by shlex, so that
    quoted parameters are set as one token. Ie, if a line
    entered by the user is:

    set interface ge-1/2/0 description "Some interface"

    the argument to this function is:

    ['set', 'interface', 'ge-1/2/0', 'description', 'Some interface']

    Args:
      current_line: A list of strings, the line at this point.

    Returns:
      A dictionary of completions. Keyed by command, value is helpstring.
      If the key starts with the character '<', then the entry is shown
      in the completion candidate list, but is not actually used for
      completion (eg, if one wants to show "<string>   The string.")
    """

    # First disambiguate as much as possible.
    self.command_line = current_line
    line = self.Disambiguate(current_line)

    # If a pipe is present, tab complete down the pipeline.
    if self.WillPipe(line):
      return self.GetPipeTree().Completer(pipe.SplitByPipe(line)[1])

    candidates = {}

    # Examine subcommands for completions.
    for name, subcommand in self.iteritems():
      if subcommand._Matches(line):
        if len(line) > 1:
          # A line with more elements here is passed to the first match.
          return subcommand.Completer(line[1:])
        elif not subcommand.hidden or SHOW_HIDDEN:
          # Or add non-hidden commands to the help options.
          candidates[name] = subcommand.help

    # Add completions for options.
    candidates.update(self.options.GetOptionCompletes(line))

    return candidates

  def _Matches(self, line):
    """Returns a boolean, whether the line matches this command.

    A match is either the line's first element maching our name,
    or the line being empty (meaning, ask for all possible commands).

    Args:
      line: A list of str, the current command line.

    Returns:
      A boolean, True if the line matches this command object.
    """
    if line == [' '] or not line:
      return True
    return self.name.startswith(line[0].lower())

  def AddOption(self, name, **kwargs):
    """Adds an option to this command.

    Args:
      name: The name of the option to add.

    Returns:
      A Command() object, this. This is done to make for convenient
      chaining of AddOption calls to a single Command object.
    """
    self.options.AddOption(name, **kwargs)
    return self

  def _GetCommonPrefix(self, words):
    """Returns the common prefix in the list of words.

    Args:
      words: A list of strings, words to match for.

    Returns:
      A string, the longest match prefix.
    """
    common = ''
    for i in xrange(len(words[0]) + 1):
      prefix = words[0][:i]
      for w in words:
        if not w.startswith(prefix):
          return common
      common = prefix
    return common

  def Disambiguate(self, command, prefer_exact_match=False):
    """Disambiguates commands.

    Attempts to expand all elements of the supplied command.
    If a pipe is present, disambiguates both the main command
    as well as the pipe, before recombining, else just
    disambiguates this command.

    Args:
      command: A list of strings, tokens of current command line.
      prefer_exact_match: A boolean, if there is an exact match then
        return that instead of a common prefix.

    Returns:
      A list, where the tokens are disambiguated. If
      ambiguous, returns the supplied 'command'
    """
    expanded = []
    if self.WillPipe(command):
      first, last = pipe.SplitByPipe(command)
      first_dis = self.Disambiguate(first, prefer_exact_match)
      last_dis = self.GetPipeTree().Disambiguate(last, prefer_exact_match)
      if first_dis:
        expanded = first_dis + [PIPE_CHAR] + last_dis
      else:
        expanded = last_dis
    else:
      expanded = self._Disambiguate(command, prefer_exact_match)
    return expanded

  def _Disambiguate(self, command, prefer_exact_match=False):
    """Disambiguates a command, by expanding elements.

    For example: ['sh'] -> ['show']

    Also works recursively while not ambiguous:

    Eg: ['sh', 'ver'] -> ['show', 'version']

    however, if 'ver' is ambiguous (lets say 'version' or 'versed'),
    then returns as much as possible:

    ['sh', 'ver'] -> ['show', 'vers']

    Args:
      command: A list of strings, tokens of current command line.
      prefer_exact_match: A boolean, if there is an exact match then
        return that instead of a common prefix.

    Returns:
      A list, where the tokens are disambiguated. If
      ambiguous, returns the supplied 'command'
    """
    if not command:
      return []

    matches = []  # List of candidate sub-commands.
    # Attempt to look for valid subcommands.
    for candidate in self:
      if prefer_exact_match and candidate == command[0].lower():
        # An exact match short-circuits the search.
        matches = [candidate]
        break
      if candidate.startswith(command[0].lower()):
        matches.append(candidate)

    if len(matches) > 1:
      # More than one, find common prefix, return that.
      command[0] = self._GetCommonPrefix(matches)
      return command
    elif len(matches) == 1:
      # One match, disambiguate subcommands.
      if len(command) > 1:
        submatches = self[matches[0]].Disambiguate(
            command[1:], prefer_exact_match)
        #if not submatches:
        #  return None
        matches.extend(submatches)
      return matches
    else:  # No match, try options. Exclude '<> completes.
      return self.options.Disambiguate(list(command))

  def _AddAncestors(self, command_object):
    """Ensure all ancestors are present in the command tree."""
    command = self
    for idx, key in enumerate(command_object.ancestors):
      # Descend through all ancestors of the command_object. If
      # any is missing, create a dummy command node and add it
      # to the tree, then continue descending.
      try:
        command = command[key]
      except KeyError:
        # Ancestor not found, create it and add it.
        cmd = Command(name=key, help=command_object.help)
        cmd.ancestors = command_object.ancestors[:idx]
        cmd._busy = True  # Loop prevention.
        if self.name != '<root>':
          cmd.ancestors.extend(self.name)
        self.Attach(cmd)
        command = command[key]

  def Attach(self, command_object):
    """Attaches a Command() object to the tree.

    The ancestors attribute is used to determine whether to
    anchor it to this object, or a descendent.

    If a Command() at the specified tree position already exists,
    then it will be overwritten except for the sub-commands.

    Args:
      command_object: A Command() object.
    """
    ancestors = list(command_object.ancestors)
    if not command_object.orig_ancestors:
      command_object.orig_ancestors = ancestors
    command_object.root = self.root
    if not ancestors:
      if command_object.name in self:
        # If node already exists, merge sub-commands.
        command_object.update(self[command_object.name])
      self[command_object.name] = command_object
      command_object.parent = self
      return

    # The '_busy' attribute is used for loop prevention when this method
    # is called by _AddAncestors().
    if self.name == '<root>' and not hasattr(command_object, '_busy'):
      self._AddAncestors(command_object)

    if len(ancestors) > 1:
      command_object.ancestors = ancestors[1:]
    else:
      command_object.ancestors = []

    self[ancestors[0]].Attach(command_object)

  def GetOptionObject(self, option_name):
    """Fetches the named option object. See Options.GetOptionObject()."""
    return self.options.GetOptionObject(option_name)

  def GetOption(self, option_name):
    """Fetches an option from command line. See Options().GetOption()."""
    if self.WillPipe(self.command_line):
      return self.options.GetOption(
          pipe.SplitByPipe(self.command_line)[0], option_name)
    else:
      return self.options.GetOption(self.command_line, option_name)

  def GetGroupOption(self, group):
    """Fetches set options in a group. See Options().GetGroupOption()."""
    if self.WillPipe(self.command_line):
      return self.options.GetGroupOption(
          pipe.SplitByPipe(self.command_line)[0], group)
    else:
      return self.options.GetGroupOption(self.command_line, group)

  def GetCommand(self, cmdline):
    """Returns the command object for the given commandline.

    Args:
      cmdline: A list of str, the command line at this point.

    Returns:
      A command object, the command object for the given command.
    """
    # Expand the command line out.
    self.command_line = self.Disambiguate(cmdline, prefer_exact_match=True)

    if self.WillPipe(cmdline) and cmdline[0] == PIPE_CHAR:
      # Retain pipe at the start.
      self.command_line = [PIPE_CHAR] + self.command_line

    # If command line is empty at this point, or the next option
    # is not a valid subcommand, we run it locally.
    if len(self.command_line) < 1 or self.command_line[0] not in self:
      return self

    # First command line token is a subcommand, pass down.
    return self[self.command_line[0]].GetCommand(self.command_line[1:])

  def Execute(self, command):
    """Executes the command given.

    'command' is the command at this point. eg, if this command
    instance name is 'interface', and the user supplied command is
    'show interface statistics detail', then 'command' might be
    something like ['statistics', 'detail'].

    If command len is > 1, and the first word is a subcommand,
    it calls it if present (in this instance, 'statistics'). If not
    present, or the 'command' is empty, it calls self.Run().

    Args:
      command: (list) The command to run, split into tokens..

    Returns:
      The value returned by a command's 'Run' method. Else None.
    """
    cmd = self.GetCommand(command)
    if cmd.options.HasAllValidOptions(cmd.command_line, describe=True):
      print '\r',  # Backspace due to a readline quirk adding spurious space.
      if cmd.WillPipe(cmd.command_line):
        retval = None
        first, last = pipe.SplitByPipe(cmd.command_line)
        # Run "<pipecmd> start" to init pipe.
        if cmd.GetPipeTree().Execute(last + ['start']):
          try:
            retval = cmd.Run(first)
          finally:
            # Run "<pipecmd> stop" to close pipe.
            cmd.GetPipeTree().Execute(last + ['stop'])
        return retval
      else:
        return cmd.Run(cmd.command_line)
    return False

  def Run(self, command):
    """Run the given command."""
    if self.method is not None:
      return self.method(self, command)
    print '%% Incomplete command.'

  def _SaveHistory(self):
    """Save readline history then clear history."""
    self._saved_history = []
    for idx in xrange(1, readline.get_current_history_length()+1):
      self._saved_history.append(readline.get_history_item(idx))
    for idx in xrange(readline.get_current_history_length()):
      readline.remove_history_item(0)

  def _RestoreHistory(self):
    """Restore readline history saved in SaveHistory."""
    for idx in xrange(readline.get_current_history_length()):
      readline.remove_history_item(0)
    for item in self._saved_history:
      readline.add_history(item)

class ShellCommand(Command):
  """A type of Command that is useful for direct shell pipelines."""

  def Completer(self, line):
    """Command line completer, for now just return a default placeholder."""
    return {'<command>': 'Shell command to pipe output through'}

  def Execute(self, command):
    """Called immediately before and immediately after the primary command."""
    action = command[-1]
    cmd = []
    for token in command[:-1]:
      if ' ' in token:
        cmd.append('"%s"' % token)
      else:
        cmd.append(token)
    pipe = ' '.join(cmd)
    if len(cmd) < 1:
      print '% Invalid pipe command.'
      return False

    if action == 'start':  # Initialise shell pipe.
      return self._StartPipe(pipe)
    elif action == 'stop':  # Terminate shell pipe.
      return self._StopPipe()
    else:
      print '%% Should not get here! (%s)' % command
      return False

  def _StartPipe(self, pipe):
    """Direct stdout to the supplied pipe."""
    self._shell = subprocess.Popen(pipe, stdin=subprocess.PIPE, shell=True)
    self._prevfd = os.dup(sys.stdout.fileno())
    os.dup2(self._shell.stdin.fileno(), sys.stdout.fileno())
    self._prev = sys.stdout
    return True

  def _StopPipe(self):
    """Restore stdout."""
    self._shell.stdin.close()
    os.dup2(self._prevfd, self._prev.fileno())
    sys.stdout = self._prev
    # .wait() can deadlock, so instead .poll() until terminated.
    while self._shell.poll() is None:
      time.sleep(0.05)
    del self._shell
    return True


class Options(list):
  """Represents all options for a command.

  Attributes:
    command: A Command() object, the associated command.
  """

  def __init__(self, *args):
    super(Options, self).__init__(*args)
    self.command = None

  def GetOptionObject(self, name):
    """Fetches the Option object for the given option name.

    Args:
      name: A str, the option name to fetch.

    Returns:
      An Option(), the option requested. None if the name is not found.
    """
    for option in self:
      if option.name == name:
        return option

  def remove(self, key):
    """Override parent remove.

    Args:
      key: A str or Option, the option to remove, or its name.

    Raises:
      ValueError, if the item is not present.
    """
    new = []
    if isinstance(key, option_lib.Option):  # Remove by object.
      key = key.name
    for option in self:
      if option.name != key:
        new.append(option)
        break
    else:
      raise ValueError('%s not in list' % key)
    self[:] = new

  def AddOption(self, name, **kwargs):
    """Adds an option to this command.

    See Option() docstring for valid kwargs options.

    Args:
      name: A string, the name of the option.

    Raises:
      ValueError: An invalid option parameter combination was supplied.
    """
    # First, see if this is a replacement for an existing option,
    # and if so, remove it.
    existing = self.GetOptionObject(name)
    if existing is not None:
      if existing.arg_val is not None:
        # Also remove keyvalue "value" option.
        self.remove(existing.arg_val.name)
      self.remove(existing.name)

    kwargs['name'] = name
    default = kwargs.get('default')
    if kwargs.get('keyvalue'):
      # If the option is a keyvalue option, Squires handles this
      # by creating another option to handle its argument.
      #
      # The two options are linked together so that the various
      # completer methods can allow for this special case.
      #
      # The 'key' option is modified slightly to be a boolean option,
      # and other parameters are passed to the 'value' option.
      match = kwargs.pop('match', None)
      path = kwargs.pop('is_path', None)

      kwargs['boolean'] = True

      if match is None and path is None:
        raise ValueError(
            'With "keyvalue", one of "match" or "is_path" must be set.')

    option = option_lib.Option(**kwargs)
    self.append(option)

    if option.keyvalue:
      kwargs['match'] = match
      kwargs['boolean'] = False
      kwargs['is_path'] = path
      kwargs['name'] = '<' + option.name + '__arg>'

      optionv = option_lib.Option(**kwargs)
      optionv.arg_key = option
      optionv.default = default
      optionv.hidden = False  # Always tab complete on the arg.

      option.arg_val = optionv
      option.default = default
      self.append(optionv)

    # Now re-order the options so that non-boolean/dict/list ones come last.
    self.sort()

  def GetOption(self, command_line, option_name):
    """Fetches an option from command line.

    Fetches the current value of an option on the command
    line. Assumes HasAllValidOptions() is true, otherwise
    returned value may be incorrect.

    Args:
      command_line: A list, the command line of options.
      option_name: A string, the name of the option.

    Returns:
      The option value, if set (string or True), else None.
    """
    # Get options set on command line, return value if there's a match.
    for option, value in self._FindOptions(command_line)[0].iteritems():
      if option.name == option_name:
        return value

    # Not on command line. Look for default (may be None).
    option = self.GetOptionObject(option_name)
    return option and option.default or None

  def GetGroupOption(self, command_line, group):
    """Fetches set options in a group.

    Fetches any options in a group which match in the
    current command line.

    Args:
      command_line: A list of strings, the command line.
      group: A string, the name of the group to fetch.

    Returns:
      A string. If any members of a group are set, will return
      the name of the option (for bool options) or the matching
      string, for non-bool options.
    """
    for option in self:
      if option.group == group:
        value = self.GetOption(command_line, option.name)
        if value:
          if option.matcher.MATCH == 'boolean':
            # Return the _name_ of boolean options.
            return option.name
          else:
            return value
    return ''

  def Disambiguate(self, command):
    """Disambiguate options in the command line.

    Similar to Command.Disambiguate, but the supplied 'command'
    should contain only options.

    Args:
      command: A list of strings, the tokens that make up the
        command line.

    Returns:
      A list, where the tokens are disambiguated. If
      ambiguous, returns the supplied 'command'
    """
    newcommand = list(command)
    # Make a copy of the original command line. For each token in
    # the command line, attempt to expand the option to its full
    # string.
    # Stop processing if an ambiguous token is reached.
    for index, word in enumerate(command):
      candidates = []
      for option in self:
        # Look through options. Any that match the current word
        # are added to candidates.
        match = option.FindMatches(command, index)
        if match.count:
          candidates.extend(match.valid.keys())
      if len(candidates) != 1:
        # Skip out of completion if less or more than one option matches.
        break
      # Expanded command line is built with uniquely matching options.
      newcommand[index] = candidates[0]
    return newcommand

  def _GetRequiredGroups(self):
    """Returns required groups in this option set."""
    required_groups = set()
    # Build a list of required option groups.
    for option in self:
      if option.group and option.required:
        required_groups.add(option.group)
    return required_groups

  def _GetRequiredOptions(self):
    """Returns required options in this option set."""
    required_options = set()
    # Build a list of required options.
    for option in self:
      if option.required and not option.group and not option.arg_key:
        required_options.add(option.name)
    return required_options

  def _FindOptions(self, line, exact=True):
    """Find options present on the command line.

    Args:
      line: A list of str, the command line.
      exact: A bool. If True, tokens must match boolean options exactly.

    Returns:
      A tuple. The first element is a dict of options that
        are found, keyed by option, value is option value. The
        second is a list of group names with a matched option.
    """
    found_options = {}
    found_groups = []

    idx = 0
    while idx < len(line):
      token = line[idx]
      for option in self:
        if option.name in found_options:
          continue
        if option.arg_key is not None:
          # Value of key-value, matches separately.
          continue
        match = option.FindMatches(line, idx)
        if match.count:
          if exact and option.boolean and token != option.name:
            continue
          idx += match.count
          if option.arg_val is not None:
            val_match = option.arg_val.FindMatches(line, idx)
            idx += val_match.count  # Also found value arg.
            value = val_match.value
          else:
            value = match.value
          found_options[option] = value
          if option.group and option.group not in found_groups:
            found_groups.append(option.group)
          break
      else:
        break  # Didnt find option for this token. Abort.
    return (found_options, found_groups)

  def GetOptionCompletes(self, line):
    """Fetches option completions.

    If self.command.runnable is set, any/all required options are
    found and current token is empty, '<cr>' will be added to the completes.

    This method could be overwritten by subclasses to do eg. dynamic
    completions.

    Args:
      line: A list of strings, the options on the line. Eg if the user
        entered 'set pager on colour red' and the Command is for 'pager',
        line should be ['on', 'colour', 'red'].

    Returns:
      A dict, keys are valid completions, values are associated helpstring.
    """
    # The final returned dict.
    completes = {}
    # Get the last token on the line.
    last_index = len(line)-1
    last_token = None
    if line:
      last_token = line[last_index]

    # found options are options which are found.
    # Seem groups are groups for which a member was seen.
    # Skip last token if still being typed.
    if last_token != ' ':
      find_line = line[:-1]
    else:
      find_line = line
    found_options, seen_groups = self._FindOptions(find_line, exact=False)

    # Ensure has all the required options present.
    has_required = self.HasAllValidOptions(line[:-1])

    def _SkipOption(option, line):
      """Determines whether to skip the given option."""
      if (
          (option in found_options) or  # Already have this option.
          (option.hidden and not SHOW_HIDDEN) or  # Dont show hidden options.
          # Already have a group member.
          (option.group in seen_groups and not option.arg_key) or
          # Position is not valid at this token.
          (option.position >= 0 and last_index != option.position) or
          # No match for this option (unless no token is present).
          (last_token != ' ' and not
           option.FindMatches(line, last_index).count)):
        return True
      return False

    # Go through options that were not found on the line, and
    # see if they need to be considered for completion candidates.
    for option in self:
      if _SkipOption(option, line):
        continue
      match = option.FindMatches(line, last_index)
      if option.arg_key is not None:
        # We have the value of a key/value option. Check the previous token
        # is the key and is valid, then add this option as the only completion.
        if (len(line) < 2 or not
            option.arg_key.FindMatches(line, last_index-1).count):
          # Line too short or previous token doesnt match
          continue
        # Reset all completes, as we only want whetever matches the keyvalue.
        if option.matcher.MATCH in ('list', 'dict', 'path', 'method'):
          completes = match.valid
          if len(completes) != 1:
            # single value of keyvalue not present.
            has_required = False
        else:
          key = option.name.replace('__arg', '')
          completes = {key: option.helptext}
          if option.default:
            completes[key] += ' [Default: %s]' % option.default

        break

      if option.matcher.MATCH == 'regex':
        # Regex completes show '<option_name>'.
        completes['<%s>' % option.name] = option.helptext
      else:
        # Others show the actual valid strings.
        completes.update(match.valid)

    # Add <cr> to to options if the command is runnable, any/all options are
    # supplied, and there is no word under the cursor.
    if has_required and self.command.runnable and last_token in (None, ' '):
      completes['<cr>'] = self.command.execute_command_string
      if self.command.GetPipeTree() is not None:
        completes[PIPE_CHAR] = 'Run stdout through pipe'

    # Strip out completes starting with '<' if there are non '<' completes
    # and there is a word under the cursor.
    if last_token and last_token != ' ':
      freeform_options = []
      for candidate in completes:
        if candidate.startswith('<'):
          freeform_options.append(candidate)
      if len(freeform_options) != len(completes):
        for option in freeform_options:
          del completes[option]

    return completes

  def HasAllValidOptions(self, command, describe=False):
    """Checks that commandline has required options.

    Goes through the command line, and looks for required options
    of this command. If any are missing it returns False. Optionally
    prints out the error message. Also checks for duplicate options
    and more than one member of a group.

    Args:
      command: A list of strings, the command line at this point.
      describe: A boolean, whether to print out an error.

    Returns:
      bool, whether all options are valid.
    """
    # Strip out anything from a pipe, this method should only check
    # on the left side of a pipe.
    if self.command.WillPipe(command):
      command = pipe.SplitByPipe(command)[0]

    # All required are missing until they are seen.
    missing_options = self._GetRequiredOptions()
    missing_groups = self._GetRequiredGroups()
    # Note which options are already matched on the command line.
    found_options = []
    # Note tokens which do not have any match.
    unknown_tokens = []

    idx = 0
    while idx < len(command):
      token = command[idx]
      option_matches = []
      jump = 0  # Tracks how far to jump ahead in tokens after a match.
      # Find option matching this token.
      for option in self:
        if option.name in found_options:
          # Already found this option.
          continue

        if option.arg_key:
          # Keyvalue args are not checked here.
          continue

        match = option.FindMatches(command, idx)
        if not match.count:
          # Option does not match anyway.
          continue

        # Boolean options must be exact match (they need to be
        # disambiguated before here anyway).
        if option.boolean and option.name != token:
          continue

        jump = match.count-1
        found_options.append(option.name)

        # A 'multiple match' error is displayed unless the
        # token is an exact match for one of the candidates.
        if len(match.valid) != 1 and token not in match.valid:
          if describe:
            print '%% Multiple matches for "%s" argument "%s":' % (
                option.name, token)
            for arg in match.valid:
              print ' %s' % arg
          return False

        # If a path option, check for existance if 'only_valid_paths'.
        if (option.is_path and option.only_valid_paths and not
            os.path.exists(match.value)):
          if describe:
            print '%% File not found: %s' % match.value
          return False

        # Check key/value options have value part present.
        if option.arg_val is not None:
          if idx+jump == len(command) - 1:
            # EOF before the value part.
            if describe:
              print '%% Argument for option "%s" missing.' % option.name
            return False
          vmatch = option.arg_val.FindMatches(command, idx+jump+1)
          if not vmatch.count:
            # Arg does not match.
            if describe:
              print '%% Invalid argument for option "%s".' % option.name,
            if vmatch.reason:
              print vmatch.reason
            else:
              print
            return False
          jump += vmatch.count
          tok = command[idx+jump]
          if len(vmatch.valid) != 1 and tok not in vmatch.valid:
            if describe:
              print '%% Multiple matches for "%s" argument "%s":' % (
                  option.name, tok)
              for arg in vmatch.valid:
                print ' %s' % arg
            return False
          found_options.append(option.arg_val.name)
          if option.arg_val.name in missing_options:
            missing_options.remove(option.arg_val.name)

        # Note missing groups or options.
        if option.required and option.group in missing_groups:
          missing_groups.remove(option.group)
        elif (option.required and not option.group and
              not option.arg_key and
              option.name in missing_options):
          missing_options.remove(option.name)

        # At this point a matching option is found.
        option_matches.append(option)
      else:
        if not option_matches:
          # No option found for this token.
          unknown_tokens.append(token)

      if len(option_matches) > 1:
        print 'Multiple matches for %s:' % token
        print '\n'.join([' '+option.name for option in option_matches])
        return False

      # Junp to next token on line, then repeat loop.
      idx += jump+1

    if unknown_tokens or missing_groups or missing_options:
      if describe:
        if unknown_tokens:
          print '%% Unknown/duplicate token(s): %s' % ', '.join(unknown_tokens)
        if missing_groups:
          print '%% Missing group(s): %s' % ', '.join(missing_groups)
        if missing_options:
          print '%% Missing options(s): %s' % ', '.join(missing_options)
      return False

    return True


class Definition(object):
  """Stores definitions in a tree.

  This is a generic object used by a client program to define
  types of objects in the command tree, eg commands or options.
  Rather than have a client directly call Command() or Option(),
  this wrapper allows for pre-creation checks to be done, as well
  as to define sub-types of Option or Command.

  The args and kwargs are entirely object dependent, so they are
  simply stored as attributes, to be referenced by other code
  more specifically.

  Attributes:
    args: A list of args supplied to the constructor.
    kwargs: A dict of kwargs supplied to the constructor.
  """

  def __init__(self, *args, **kwargs):
    self.args = args
    self.kwargs = kwargs


class CommandDefinition(Definition):
  """Definition for a Command in the tree."""


class OptionDefinition(Definition):
  """Definition for an Option in the tree."""


class PipeTreeDefinition(Definition):
  """Definition for a tree of Pipes."""

class PipeDefinition(Definition):
  """Definition for a Pipe in the tree."""

class PipeShellDefinition(Definition):
  """Definition for a shell pipe."""


def Definitions():
  """Returns a list of the above definitions useful in a pipe tree."""
  return CommandDefinition, OptionDefinition, PipeTreeDefinition, PipeDefinition


def ParseTree(joint, tree):
  """Parses the given tree and adds as sub to 'joint'.

  For information on the definition of 'tree', please see
  the example.py file. The format is self explanatory.

  Args:
    joint: A Command(), the command to join this tree to.
    tree: A list or nested dict. Normall the entire tree will be
      a nested dict, but with the tree, Options are defined as a
      list/set rather than a dict.
  """
  if isinstance(tree, (set, tuple, list)):
    # If tree is a list type, convert to dict. A list type is usually how
    # options for a command are defined.
    newtree = {}
    for item in tree:
      newtree[item] = {}
    tree = newtree
  # Walk the tree, create items.
  for item, subs in tree.iteritems():
    if isinstance(item, (CommandDefinition, PipeDefinition)):
      # Command or pipe item.
      if joint.root == joint:
        # Toplevel
        newcmd = joint.AddCommand(*item.args, **item.kwargs)
      else:
        newcmd = joint.AddSubCommand(*item.args, **item.kwargs)
      if isinstance(item, PipeDefinition):
        # Create a command for the pipe
        pipe_cmd = item.kwargs.get('pipe')
        newcmd.pipe = pipe_cmd
        newcmd.method = pipe_cmd.State
        newcmd.runnable = True
        newcmd.AddOption('start', boolean=True, hidden=True)
        newcmd.AddOption('stop', boolean=True, hidden=True)
      # Recurse down the tree.
      ParseTree(newcmd, subs)
    elif isinstance(item, OptionDefinition):
      # Option.
      joint.AddOption(*item.args, **item.kwargs)
    elif isinstance(item, PipeShellDefinition):
      pipetree = ShellCommand()
      joint.pipetree = pipetree
    elif isinstance(item, PipeTreeDefinition):
      # Define a pipe tree at this point.
      pipetree = Command()
      ParseTree(pipetree, item.kwargs['tree'])
      joint.pipetree = pipetree


# Define a basic tree for pipes that modules can use.
_COMMAND, _OPTION, _PIPETREE, _PIPE = Definitions()
DEFAULT_PIPETREE = {
    _PIPE('more', help='One page at a time', pipe=pipe.MorePipe()): {},
    _PIPE('grep', help='Find a string', pipe=pipe.GrepPipe()): (
        _OPTION('string', helptext='String to find', match='\S',
                required=True),
    ),
    _PIPE('except', help='Except a string', pipe=pipe.ExceptPipe()): (
        _OPTION('string', helptext='String to exclude', match='\S',
                required=True),
    ),
    _PIPE('count', help='Count lines', pipe=pipe.CountPipe()): {},
    _PIPE('sh', help='pipe to shell command', pipe=pipe.ShellPipe()): (
        _OPTION('string', helptext='Command to pipe to', match='\S',
                required=True),
    ),
}

