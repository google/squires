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
executed. Before doing this, you must call PrepareReadline() on
the top level Command() object.

Please see squires_test.py or example.py for simple usage.
"""

__version__ = '0.9.1'

import inspect
import os
import re
import readline
import shlex
import sys
import traceback


SHOW_HIDDEN = False  # Force display of hidden commands and options.

class Error(Exception):
  pass


class AmbiguousError(Error):
  """Ambiguous option on command line."""
  # TODO(bbuxton): Deal with ambiguous matches. eg, if the
  # possible matches are ('on', 'off') and the command line
  # contains 'o', then the matched value will be 'on', ie the
  # first match.
  pass


class Command(dict):
  """An element on the command tree.

  Keys are subcommands, values are instances of Command.

  Attributes:
    name: A string, the name of this command.
    help: A string, the help string for this command.
    ancestors: A list of strings, ancestor command names.
    root: A Command() object, the root of the tree.
    runnable: A boolean, if this command can be run itself (ie doesnt require
      subcommands). If true '<cr>' is shown in the completion list. If None
      and a method is supplied, default to True, else False.
    options: A list of Option() objects for this command.
    hidden: A boolean. If True, the command does not show in tab completion.
    command_line: A list of tokens in the current command line.
    logfile: A string, logfile to write output to. Only valid for the top
      level command.
    writer: A file like object, the above file. Only valid for the top
      level command.
    prompt: A string, the command prompt to display. Only valid for the top
      level command.
    method: A method, called from within Run(), unless Run() is overridden.
    execute_command_string: A string, to display as '<cr>' help, if runnable.
  """

  def __init__(self, name='', help=None, runnable=None, method=None):
    super(Command, self).__init__(self)
    self.name = name
    self.help = help or ''
    self.root = self
    self.ancestors = []
    self.options = Options()
    self.options.command = self
    self.command_line = []
    self.logfile = None
    self.writer = None
    self.hidden = False
    self.prompt = '> '
    self.method = method

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
    self._orig_ancestors = []

  def PrepareReadline(self):
    """Prepares readline for our use."""
    readline.set_completer(self.ReadlineCompleter)
    readline.parse_and_bind('tab: complete')
    readline.parse_and_bind('?: possible-completions')
    readline.set_completer_delims(' ')

  def AddCommand(self, name, help=None, runnable=None, method=None):
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

    Returns:
      A Command() object.
    """
    name = name.split()
    command = Command(name=name[-1], help=help, runnable=runnable,
                      method=method)
    command.ancestors = name[:-1]
    self.root.Attach(command)
    return command

  def AddSubCommand(self, name, **kwargs):
    """Similar to AddCommand(), but added directly below the current Command.

    Name is a string, the command name relative to the Command() instance.
    that AddSubCommand is called for. eg if this Command is 'set pager' and
    name is 'terminal', the new command is 'set pager terminal'.

    Returns:
      A Command() object, the new command.
    """
    ancestors = ' '.join(self._orig_ancestors) + ' %s %s' % (self.name, name)
    return self.AddCommand(ancestors, **kwargs)

  def __repr__(self):
    return '<Command Object, Name "%s", SubCommands: %s>' % (
        self.name, ','.join(self.keys()))

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

    # If logging to a file, we temporarily need to restore
    # stdout for readline to work correctly.
    old_stdout = sys.stdout
    sys.stdout = sys.__stdout__
    line = raw_input(self.prompt)
    sys.stdout = old_stdout
    if self.writer is not None:
      self.writer.Log('%s%s\n' % (self.prompt, line))

    try:
      split_line = shlex.split(line)
    except ValueError, e:
      print '%% %s' % e
      return

    # Disable completer so a 'Run' method that uses 'raw_input' wont
    # autocomplete on the squires commands.
    readline.set_completer(None)
    # Work around lack of 'finally' in 2.4
    try:
      self.Execute(split_line)
    except (KeyboardInterrupt, EOFError), e:
      # Catch ctrl-c and eof and pass up
      readline.set_completer(self.ReadlineCompleter)
      raise
    except Exception, e:
      # Other exceptions whilst running command have trace
      # printed, then back to the prompt.
      traceback.print_exc(file=sys.stdout)
    readline.set_completer(self.ReadlineCompleter)

  def ReadlineCompleter(self, unused_word, state):
    """Readline completion handler.

    This method is registered with readline to perform command
    completion. It tidies up the current command line, before
    passing to self.Completer.

    Args:
      unused_word: A string, the current word under the cursor. (unused)
      state: An int, the 'tab press number', indexed at zero.
    Returns:
      A string, a unique valid completion, or None.
    """
    try:
      try:
        current_line = shlex.split(readline.get_line_buffer())
      except ValueError, e:
        if str(e) == 'No closing quotation':
          current_line = shlex.split(readline.get_line_buffer() + '"')

      if readline.get_line_buffer().endswith(' '):
        current_line.append(' ')

      if not state:
        complete_string = ''
        try:
          candidates = self.Completer(current_line)
        except:
          print traceback.print_exc(file=sys.stdout)
          raise
        if len(candidates) == 1 and not candidates.keys()[0].startswith('<'):
          complete_string = candidates.keys()[0] + ' '
        elif candidates:
          print '\nValid completions:'
          candidate_words = candidates.keys()
          candidate_words.sort()
          for candidate in candidate_words:
            print ' %-21s %s' % (candidate, candidates[candidate] or '')
          print self.prompt + readline.get_line_buffer(),
          complete_string = self._GetCommonPrefix(candidate_words)
          if complete_string.startswith('<'):
            complete_string = None
        else:
          print '\n% No valid completions.'
          print self.prompt + readline.get_line_buffer(),
        return complete_string
      return None
    except:
      print '\n%s' % traceback.format_exc()

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

    # First disambiguate as much as possible
    self.command_line = current_line
    line = self.Disambiguate(current_line)

    candidates = {}

    # Examine subcommands for completions.
    for name, subcommand in self.iteritems():
      if subcommand._Matches(line):
        if len(line) > 1:
          # A line with more elements here is passed to
          # the first match.
          return subcommand.Completer(line[1:])
        elif not subcommand.hidden or SHOW_HIDDEN:
          # Or add non-hidden commands to the help options.
          candidates[name] = subcommand.help

    # Add completions for options
    candidates.update(self.options.GetOptionCompletes(line))

    return candidates

  def _Matches(self, line):
    """Returns a boolean, whether the line matches this command.

    A match is either the line's first element maching our name,
    or the line being empty (meaning, ask for all possible commands).
    """
    if line == [' '] or not line:
      return True
    return self.name.startswith(line[0].lower())

  def AddOption(self, name, **kwargs):
    """Adds an option to this command.

    See Options() and Option() docstring for valid kwargs options.

    Returns this Command object. This is done to make for convenient
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

    matches = []  # List of candidate sub-commands
    # Attempt to look for valid subcommands
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
      newcommand = list(command)
      index = 0
      while index < len(command):
        word = command[index]
        candidates = []
        for option in self.options:
          if option.Matches(command, index):
            if option.name.startswith('<'):
              candidates.append(word)
            else:
              if option.boolean:
                candidates.append(option.name)
              else:
                candidates.append(option.Match(command, index))
        if len(candidates) != 1:
          break
        newcommand[index] = candidates[0]
        index += 1
      return newcommand

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
        cmd._busy = True  # Loop prevention
        if self.name != '<root>':
          cmd.ancestors.extend(self.name)
        self.Attach(cmd)

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
    if not command_object._orig_ancestors:
      command_object._orig_ancestors = ancestors
    command_object.root = self.root
    if not ancestors:
      if command_object.name in self:
        # If node already exists, merge sub-commands
        command_object.update(self[command_object.name])
      self[command_object.name] = command_object
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

  def GetOption(self, option_name):
    """Fetches an option from command line. See Options().GetOption()."""
    return self.options.GetOption(self.command_line, option_name)

  def GetGroupOption(self, group):
    """Fetches set options in a group. See Options().GetGroupOption()."""
    return self.options.GetGroupOption(self.command_line, group)

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

    # Expand the command line out.
    self.command_line = self.Disambiguate(command, prefer_exact_match=True)

    # If command line is empty at this point, or the next option
    # is not a valid subcommand, we run it locally.
    if len(self.command_line) < 1 or self.command_line[0] not in self:
      if self.options.HasAllValidOptions(self.command_line, describe=True):
        print '\r',  # Backspace due to a readline quirk adding spurious space
        return self.Run(self.command_line)
      return

    # First command line token is a subcommand, pass down.
    return self[self.command_line[0]].Execute(self.command_line[1:])

  def Run(self, command):
    """Run the given command."""
    if self.method is not None:
      return self.method(self, command)
    print '%% Incomplete command.'


class Options(list):
  """Represents all options for a command.

  Attributes:
    command: A Command() object, the associated command.
  """

  def __init__(self, *args):
    super(Options, self).__init__(*args)
    self.command = None

  def AddOption(self, name, **kwargs):
    """Adds an option to this command.

    See Option() docstring for valid kwargs options.

    Args:
      name: A string, the name of the option.
      kwargs: Key word args, to match Option() constructor.

    Raises:
      ValueError: An invalid option parameter combination was supplied.
    """
    # First, see if this is a replacement for an existing option,
    # and if so, remove it.
    for option in self[:]:
      if option.name == name:
        self.remove(option)
        if option.arg_val is not None:
          # Also remove keyvalue "value" option
          self.remove(option.arg_val)

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

    option = Option(**kwargs)
    self.append(option)

    if option.keyvalue:
      kwargs['match'] = match
      kwargs['boolean'] = False
      kwargs['is_path'] = path
      kwargs['name'] = '<' + option.name + '__arg>'
      optionv = Option(**kwargs)
      option.arg_val = optionv
      optionv.arg_key = option
      option.default = default
      optionv.default = default
      optionv.hidden = False  # Tab complete on the arg
      self.append(optionv)

    # Now re-order the options so that match ones come last.
    options = Options()
    options.command = self.command
    for option in self:
      if option.match is None:
        options.append(option)
    for option in self:
      if option.match is not None:
        options.append(option)
    self[:] = options

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
    found_tokens = []
    for option in self:
      for tok_index in xrange(len(command_line)):
        if tok_index in found_tokens:
          # Matched earlier, skip.
          continue
        if option.Matches(command_line, tok_index):
          found_tokens.append(tok_index)
          if option.name == option_name:
            if option.arg_val is not None:
              # Option has an arg token, match on it
              return option.arg_val.Match(command_line, tok_index+1)
            return option.Match(command_line, tok_index)
      # Option not on command line. If is has default, return that.
      if option.name == option_name and option.default and option.arg_val:
        return option.default
    return None

  def GetGroupOption(self, command_line, group):
    """Fetches set options in a group.

    Fetches any options in a group which match in the
    current command line.

    Args:
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
          if option.match is not None:
            return value
          else:
            return option.name
    return ''

  def FileCompleter(self, incomplete, only_dirs=False, default_path=None):
    """Attempts to complete a filename.

    Args:
      incomplete: A string, the filename to complete.
      only_dirs: A boolean. If true, only complete on directories.
      default_path: A str, the default path (relative to pwd) to complete from.

    Returns:
      A list of strings, valid completable filenames.
    """
    valid_files = []
    if incomplete == ' ':
      incomplete = ''
    if default_path:
      if not default_path.endswith(os.sep):
        default_path += os.sep
      incomplete = os.path.join(default_path, incomplete)
    dirname = os.path.dirname(incomplete)
    basename = os.path.basename(incomplete)
    fulldir = os.path.abspath(dirname)

    if dirname and not os.path.exists(fulldir):
      # Directory specified in incomplete and does not exist
      return []
    for dir_file in os.listdir(fulldir):
      entry = os.path.join(dirname, dir_file)
      if dir_file.startswith(basename):
        if os.path.isdir(entry):
          entry += os.sep
          valid_files.append(entry)
        elif not only_dirs:
          valid_files.append(entry)

    if default_path:
      valid_files = [entry.replace(default_path, '', 1) for entry in
                     valid_files]

    return valid_files

  def _GetRequiredGroups(self):
    """Returns required groups in this option set."""
    required_groups = set()
    # Build a list of required option groups.
    for option in self:
      if option.group and option.required:
        required_groups.add(option.group)
    return required_groups

  def GetOptionCompletes(self, line):
    """Fetches option completions.

    In addition, if self.command.runnable is set, any/all required options are
    found, and current token is empty, '<cr>' is added to the completes.

    This method could be overwritten by subclasses to do eg. dynamic
    completions.

    Args:
      line: A list of strings, the options on the line. Eg if the user
        entered 'set pager on colour red' and the Command is for 'pager',
        line should be ['on', 'colour', 'red'].

    Returns:
      A dict, keys are valid completions, values are associated helpstring.
    """
    completes = {}
    if line:
      last_token = line[-1]
    else:
      last_token = None

    seen_groups = set()
    has_required = True
    required_groups = self._GetRequiredGroups()

    found_options = []

    # Go through current command line and look for
    # required options being present (to add <cr>), or
    # option group members already present, to not display
    # other group members. Also put names of options already
    # present into found_options.
    matched_tokens = []
    for option in self:
      for idx, token in enumerate(line):
        if idx == len(line)-1 and token != ' ':
          break
        if idx in matched_tokens:
          continue
        if option.Matches(line, idx):
          # Make sure a keyvalue value has the corresponding
          # key as the previous token.
          if (option.arg_key is not None and not
              option.arg_key.Matches(line, idx-1)):
            continue
          matched_tokens.append(idx)
          found_options.append(option.name)
          if option.group:
            seen_groups.add(option.group)
            if option.group in required_groups:
              required_groups.remove(option.group)
      if (option.required and not option.group and
          option.name not in found_options):
        has_required = False

    if required_groups:
      # Above block has not found any member of required groups.
      has_required = False

    for option in self:
      # Go through all options, see which ones could be a match.
      if option.name in found_options:
        # Already have this option.
        continue
      if option.hidden and not SHOW_HIDDEN:
        # Dont show hidden options
        continue
      if option.group and option.group in seen_groups:
        # Already have a group member.
        continue
      if option.position >= 0 and len(line) - 1 != option.position:
        # Position is not valid at this token.
        continue
      if last_token != ' ' and not option.Matches(line, len(line) - 1):
        # No match for this option (unless no token is present)
        continue
      if '__arg' in option.name and option.arg_key is not None:
        # We have the value of a key/value option. Check the previous token
        # is the key and is valid, then add this option as the only completion.
        if len(line) < 2 or not option.arg_key.Matches(line, len(line) - 2):
          # Line too short or previous token doesnt match
          continue
        # Reset all completes, as we only want whetever matches the keyvalue.
        completes = {}
        if option.is_path:
          # Path-type options have filenames as the completions
          valid_files = self.FileCompleter(
              last_token, only_dirs=option.only_dir_paths,
              default_path=option.path_dir)
          for fname in valid_files:
            completes[fname] = ''
        else:
          if option.matchtype in ['list', 'dict']:
            for value in option.match:
              if last_token == ' ' or value.startswith(last_token):
                if option.matchtype == 'list':
                  completes[value] = ''
                else:
                  completes[value] = option.match[value]
            if len(completes) != 1:
              # single value of keyvalue not present
              has_required = False
          else:
            key = option.name.replace('__arg', '')
            completes = {key: option.helptext}
            if option.default:
              completes[key] += ' [Default: %s]' % option.default
        break

      if not option.keyvalue and option.matchtype in ('list', 'dict'):
        # Look for completes of non-keyvalue list/dict types
        if option.Matches(line, len(line)-1):
          # If we have a match, add the full value to the completion
          completes[option.Match(line, len(line)-1)] = ''
        else:
          # Or add all possible matches to completion list.
          for val in option.match:
            if option.matchtype == 'list':
              completes[val] = ''
            else:
              completes[val] = option.match[val]
            if option.default and not option.required:
              # Mark any match option that is default.
              completes[option.default] = '[Default]'
      else:
        completes[option.name] = option.helptext

      if option.default and option.name in completes:
        completes[option.name] += ' [Default: %s]' % option.default

      if option.is_path:
        # Path-type options also have filenames added to the completions
        valid_files = self.FileCompleter(
              last_token, only_dirs=option.only_dir_paths,
              default_path=option.path_dir)
        for fname in valid_files:
          completes[fname] = ''

    # Add <cr> to to options if the command is runnable, any/all options are
    # supplied, and there is no word under the cursor.
    if has_required and self.command.runnable and last_token in (None, ' '):
      completes['<cr>'] = self.command.execute_command_string

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
    missing_options = set()
    # All required are missing until they are seen.
    missing_groups = self._GetRequiredGroups()

    group_dupes = set()
    found_options = []
    # All tokens are unknown. We will remove them as we find known ones.
    unknown_tokens = list(command)
    matched_tokens = []
    # Now go through each option.
    for option in self:
      found_option = False
      for token_index, token in enumerate(command):
        if (token_index in matched_tokens or not
            option.Matches(command, token_index)):
          continue
        # If option has keyvalue key, make sure it
        # matches previous token.
        if option.arg_key is not None:
          if not option.arg_key.Matches(command, token_index-1):
            continue
        matched_tokens.append(token_index)
        # Token a valid option, remove from unknown list
        if token in unknown_tokens:
          unknown_tokens.remove(token)
        # If a path option, check for existance if 'only_valid_paths'.
        if option.is_path and option.only_valid_paths and not os.path.exists(
            option.Match(command, token_index)):
          print '%% File not found: %s' % option.Match(command, token_index)
          return False
        # If option already present, return error.
        if option.name in found_options:
          if describe:
            print '%% Duplicate option: %s' % option.name
          return False
        found_options.append(option.name)
        found_option = True
        # Check key/value options have value option present. This is
        # done by seeing if the next token matches the options
        # 'arg_val' option.
        if option.arg_val is not None:
          if token_index == len(command) - 1:
            print '%% Argument for option "%s" ' 'missing.' % option.name
            return False
          if not option.arg_val.Matches(command, token_index+1):
            print '%% Invalid argument for option "%s".' % option.name
            return False
        # Required group option
        if option.required and option.group:
          if option.group in missing_groups:
            # Un-mark group as missing
            missing_groups.remove(option.group)
          else:
            # Else mark it as duplicate group option
            group_dupes.add(option.group)

      # Missing required option (non-group)
      if (option.required
          and not option.group
          and not found_option
          and option.arg_key is None):
        missing_options.add(option.name)

    if missing_options or unknown_tokens or group_dupes or missing_groups:
      if describe:
        if missing_options:
          print '%% Missing option(s): %s' % ', '.join(missing_options)
        if unknown_tokens:
          print '%% Unknown option(s): %s' % ', '.join(unknown_tokens)
        if group_dupes:
          # More than one group member, return error
          groupoptions = []
          for option in self:
            if option.group in group_dupes:
              groupoptions.append(option.name)
          print '%% Supply only one of: %s' % ', '.join(groupoptions)
        if missing_groups:
          # Missing required group, return error.
          groupoptions = []
          for option in self:
            if option.group in missing_groups:
              groupoptions.append(option.name)
          print '%% Missing one of: %s' % ', '.join(groupoptions)
      return False
    return True


class Option(object):
  """An option to a command.

  This represents a local option that merely affects the
  behaviour of the command, Eg 'terse' for 'show interface'
  would be an option.

  Attributes:
    name: A string, the name of the option as presented in help.
    helptext: A string, textual help string, one line.
    boolean: A boolean, whether the option is a boolean option. If
        None, then will be 'True' if 'match' is None, else False.
    keyvalue: A boolean. If True, the option is a 'key/value' option
        where the name is supplied, followed by the value as the
        next token.
    default: A string. The default value. Only valid for keyvalue options.
    required: A boolean, if this is a required option or group.
    is_path: A boolean, if this option is a path name. Will tab-complete
        on path.
    only_valid_paths: A boolean, whether the supplied path must be valid and
        already exist (used with is_path)
    only_dir_paths: A boolean. If True, and is_path is True, only complete
        on directories.
    path_dir: A str, the default path to use when is_path is True.
    match: If a string it is a regex to match this option.
        If a list of strings, it is a list or dict of possible values.
        In the case of a dict, keys are the option value, and values are the
          associated helpstring.
        If not supplied, or empty, matches against 'name'.
        If it is a function pointer, the function is executed at every
          match request call (with this option instance as the only arg), and
          the returned value is used in evaluation, per above.
    matchtype: A string. If 're', a regex match. If 'list' a list match.
    group: A string, if not None, only one of the options with the same
        group may be supplied in a command line.
    position: An int, positional option location. If -1, option
        is not positional.
    hidden: A boolean, if True, the option does not tab complete. Note that the
        'value' of a keyvalue option will tab complete when the key is supplied.
    arg_key: An Option(), the 'key' option of a key/value option pair. Used
        internally by Squires.
    arg_val: An Option(), the 'value' option of a key/value option pair. Used
        internally by Squires.
  """

  def __init__(self, name, boolean=None, keyvalue=False, required=False,
               helptext=None, match=None, default=None, group=None, position=-1,
               is_path=False, only_valid_paths=False, hidden=False,
               only_dir_paths=False, path_dir=None):
    self.name = name
    self.helptext = helptext
    self.boolean = boolean
    self.keyvalue = keyvalue
    self.required = required
    self.position = position
    self.default = default
    self.is_path = is_path
    self.only_dir_paths = only_dir_paths
    self.path_dir = path_dir
    self.group = group
    self.arg_key = None
    self.arg_val = None
    self.hidden = hidden
    self._index = 0
    if self.is_path:
      if self.boolean:
        raise ValueError(
            'boolean is mutually exclusive from is_path.')
      if match is None:
        match = '.*'
      self.boolean = False
      self.only_valid_paths = only_valid_paths
    if match:
      if is_path and not self.keyvalue and self.position < 0:
        raise ValueError(
            'With is_path, position or keyvalue must be supplied')
      if isinstance(match, str):
        self._match = re.compile('^%s' % match, re.I)
      else:
        self._match = match
      if self.boolean is None:
        self.boolean = False
    else:
      self._match = None
      if self.boolean is None:
        self.boolean = True

  @property
  def matchtype(self):
    """Get the type of Option match.

      Returns: A string, the option match type.
    """
    match = self.match
    if isinstance(match, (set, tuple, list)):
      mtype = 'list'
    elif isinstance(match, dict):
      mtype = 'dict'
    elif '_sre.SRE_Pattern' in repr(match):
      mtype = 're'
    else:
      mtype = None
    return mtype

  @property
  def match(self):
    """Returns the match object, executing a function if needed."""
    if inspect.isroutine(self._match):
      try:
        ret = self._match(self)
        if isinstance(ret, str):
          ret = re.compile(ret, re.I)
        return ret
      except AttributeError:
        return None
    return self._match

  def Matches(self, command, position=None):
    """Determine if this option matches the command string.

    Args:
      command: A list of strings, the options on the command line.
      position: An int, the position in the command to look for
        a match. If None, all positions are checked. Zero indexed.

    Returns:
      A boolean, whether there is a match.
    """
    # Loop through all tokens on the command line, looking for
    # matches. Once we have a definitive match/no match, return
    # the boolean.
    for self._index, token in enumerate(command):
      if self.position > -1 and position != self.position:
        # Position required by option but does not match, skip.
        continue
      if position is not None and self._index != position:
        # Position required by arg but does not match, skip.
        continue
      elif self._match is not None:
        if self.arg_key is not None:
          # If this is a keyvalue arg
          if not self.arg_key.Matches(command, self._index-1):
            # Previous token must be the corresponding key.
            continue
        if self.matchtype == 're':
          if self.match.match(token):
            return True
          elif self.arg_key is not None:
            # Return false if keyvalue key matches, but arg
            # doesnt.
            return False
          # Otherwise continue to next token.
        elif self.matchtype in ('list', 'dict'):
          # Hunt through each possibility in 'match' and return
          # true if one of them matches.
          found_close_match = False
          for value in self.match:
            if value == token:
              self._matching_token = value
              return True
            if value.startswith(token) and not found_close_match:
              # The "closest" is the first token we find if we don't
              # find an exact match.
              self._matching_token = value
              found_close_match = True
          if found_close_match:
            return True
          return False
      elif self.name.lower().startswith(token.lower()):
        return True

    return False

  def Match(self, command, position=None):
    """Attempt to match this option in the command string.

    Args:
      command: A list of strings or a string, the command line's options.
      position: An int, the position in the command line. If None,
        searches the whole command line.

    Returns:
      If the option is a boolean option, returns True if matched,
      else returns None. Else returns the actual matching string, if
      one found, else the empty string.
    """
    if isinstance(command, str):
      command = [command]
    if not self.Matches(command, position=position):
      return None
    elif self.match is not None:
      if self.matchtype == 're':
        return self.boolean or command[self._index]
      else:
        return self._matching_token
    elif self.match is None:
      return self.boolean or self.name

    return None
