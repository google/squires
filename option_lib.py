#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.
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

"""options for squires."""

import collections
import inspect
import os
import re


"""Represents a match for an option.

Attributes:
  value: A string, the text matched by the option.
  count: An int, the count of tokens that this match swallowed. If the
    option did not match, then this is zero.
  reason: A str, the reason, if the match failed.
  valid: A dict, the valid values. Keys are the value string, values
    are the associated helptext.
"""
Match = collections.namedtuple('Match', 'value count reason valid')


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
    group: A string, if not None, only one of the options with the same
        group may be supplied in a command line.
    position: An int, positional option location. If -1, option
        is not positional.
    hidden: A boolean, if True, the option does not tab complete. Note that the
        'value' of a keyvalue option will tab complete when the key is supplied.
    freeform: A boolean. If True, the option is populated with all remaining
        text on the command line. A command without a freeform option will
        generate an error if unrecognisable text is entered.
    arg_key: An Option(), the 'key' option of a key/value option pair. Used
        internally by Squires.
    arg_val: An Option(), the 'value' option of a key/value option pair. Used
        internally by Squires.
    meta: Any object type. Meta information that can be stored by the calling
      program for reference later.
  """

  def __init__(self, name, boolean=None, keyvalue=False, required=False,
               helptext=None, match=None, default=None, group=None, position=-1,
               is_path=False, only_valid_paths=False, hidden=False,
               only_dir_paths=False, path_dir=None, freeform=False,
               meta=None):
    self.name = name
    self.helptext = helptext
    self.boolean = boolean
    self.keyvalue = keyvalue
    self.required = required
    self.position = position
    self.default = default
    self.is_path = is_path
    self.only_valid_paths = only_valid_paths
    self.only_dir_paths = only_dir_paths
    self.path_dir = path_dir
    self.group = group
    self.arg_key = None
    self.arg_val = None
    self.hidden = hidden
    self.matcher = None
    self.freeform = freeform
    self._index = 0
    self.meta = meta
    if match is not None and self.boolean is None:
      self.boolean = False

    if self.is_path:
      if self.boolean:
        raise ValueError(
            'boolean is mutually exclusive from is_path.')
      self.boolean = False
      if not self.keyvalue and self.position < 0:
        raise ValueError(
            'With is_path, position or keyvalue must be supplied')
      self.matcher = PathMatch(
          match, self, only_existing=self.only_valid_paths,
          default_path=path_dir, only_dirs=only_dir_paths)
    elif self.freeform:
      self.matcher = FreeformMatch(self)
    elif isinstance(match, str):
      self.matcher = RegexMatch(match, helptext, self)
    elif isinstance(match, (tuple, set, list)):
      self.matcher = ListMatch(match, helptext, self)
    elif isinstance(match, dict):
      self.matcher = DictMatch(match, self)
    elif inspect.isroutine(match):
      self.matcher = MethodMatch(match, self)
    elif match is None:
      self.matcher = BooleanMatch(name, self.helptext)
      if boolean is None:
        self.boolean = True

  def FindMatches(self, command, index):
    """Find possible matches for this option.

    Args:
      command: A list of str, the command line of options.
      index: An int, the position in 'command' of the token to check.

    Returns:
      A Match object, the match result.
    """
    # Make sure position is correct, if applicable.
    if self.position > -1 and index != self.position:
      return Match('', 0, 'position mismatch', {})

    if index >= len(command) or index < 0:
      return Match('', 0, 'position range error', {})

    # If a keyvalue value, make sure key matches.
    if self.arg_key is not None:
      key_match = self.arg_key.FindMatches(command, index-1)
      if not key_match.count:
        return Match('', 0, 'key mismatch', {})

    # Possible completiong
    valid = self.matcher.GetValidMatches(command[index].strip())
    # Any successful match.
    value = self.matcher.GetMatch(command[index])
    if self.boolean:
      value = value and True or False
    count = 0
    reason = self.matcher.reason
    if self.matcher.Matches(command[index]):
      count = 1
      reason = ''
    return Match(value, count, reason, valid)

  def __cmp__(self, other):
    """Comparison for sort.

    ''regex' types generally come last, so this code will work
    for now, but might be updated if there is a match type that
    is lexographically later.
    """
    return cmp(self.matcher.MATCH, other.matcher.MATCH)


class BaseMatch(object):
  """Base class for matching options.

  Attributes:
    reason: A str, the reason that a match failed.
  """
  MATCH = None
  def __init__(self):
    """Override."""
    self.reason = None

  def Matches(self, token):
    """Returns whether 'token' matches.

    Args:
      token: A str, the token to match.

    Returns:
      A boolean. True if the token matches.
    """
    return len(self.GetValidMatches(token)) > 0

  def GetMatch(self, token):
    """Attempt to match 'token' to this object.

    Args:
      token: A str, the token to match.

    Returns:
      A str, the best available match. If no matches at all, return None.
    TODO(bbuxton): Define behaviour if multiple partial matches.
  """

  def GetValidMatches(self, token=None):
    """Returns the valid matches for the given token.

    Args:
      token: A str, the token to match.

    Returns:
      A dict. Keys are the valid tokens that might match. Values are
        any associated helptext. If token is None, all possible
        completions are returned.
    """
    return {}


class FreeformMatch(BaseMatch):
  def __init__(self, option):
    self._option = option

  def Matches(self, token):
    return len(token) > 0

  def GetMatch(self, token):
    return token

  def GetValidMatches(self, token=None):
    if token:
      return {token: '<text>'}
    return {'<%s>' % self._option.name: '<text>'}


class BooleanMatch(BaseMatch):
  """An option that matches on a boolean."""
  MATCH = 'boolean'

  def __init__(self, value, helptext):
    """Initialise object.

    Args:
      value: A str, the value this option matches.
      helptext: A str, the helptext for this option.
    """
    BaseMatch.__init__(self)
    self.match = value
    self.helptext = helptext
    self.reason = None

  def GetMatch(self, token):
    """Returns whether 'token' matches this option."""
    if self.Matches(token):
      return True
    return False

  def GetValidMatches(self, token=None):
    if not token or self.match.startswith(token):
      return {self.match: self.helptext}
    return {}


class RegexMatch(BaseMatch):
  """An option that matches on a regex."""
  MATCH = 'regex'

  def __init__(self, value, helptext, option):
    """Initialise object.

    Args:
      value: A str, the regex this option matches.
      helptext: A str, the helptext for this option.
      option: The Option() associated with this match.
    """
    BaseMatch.__init__(self)
    self.match = re.compile('^%s' % value, re.I)
    self.match_str = value
    self.helptext = helptext
    self.reason = None
    self.option = option

  def GetMatch(self, token):
    """If we match, return the match string name."""
    self.reason = None
    if self.Matches(token):
      return token
    else:
      self.reason = 'Option must match regex: %s' % self.match_str

  def GetValidMatches(self, token=None):
    if not token:
      # No token, return regex we expect.
      helpstr = '%s (%s)' % (self.helptext, self.match_str)
      return {'<%s>' % self.option.name: helpstr}

    if self.match.match(token):
      # Token matches, return it and help string.
      return {token: self.helptext}

    return {}


class ListMatch(BaseMatch):
  """An option that matches on a list."""
  MATCH = 'list'
  def __init__(self, value, helptext, option):
    """Initialise object.

    Args:
      value: A list of strings, valid matches.
      helptext: A str, the helptext for this option.
      option: An Option(), the associated option for this match.
    """
    BaseMatch.__init__(self)
    self.match = value
    self.helptext = helptext
    self.reason = None
    self.option = option

  def _GetRegex(self, needle):
    """If the string parameter embeds a regex, return the regex.

    If the string is starting and ending with '/', it contains a regex. If so,
    return the regex string. Otherwise return None.

    Args:
      needle: the string to search for a regex.

    Returns:
      Either a string, with the regex found, or None.
    """
    if len(needle) > 1 and needle.startswith('/') and needle.endswith('/'):
      return needle.strip('/')

  def Matches(self, token):
    """Determine if this option matches the command string."""
    for value in self.match:
      if self._GetRegex(value):
        if re.match(self._GetRegex(value), token):
          return True
      else:
        if len(self.GetValidMatches(token)) > 0:
          return True
    return False

  def GetMatch(self, token):
    """Get the best match for this token.

    This does not take regex matches into account. The theory is that if you
    are asking for the "best match" at this point, you aren't asking the
    computer to do the impossible for you.

    Args:
      token: A string, the token to get matches for.

    Returns:
      A string containing the best match given the entered token.
    """
    self.reason = None
    found_close_match = False
    close_matches = 0
    matching_token = None
    for value in self.match:
      if value == token:
        return value
      if value.startswith(token):
        close_matches += 1
        if not found_close_match:
          # The "closest" is the first non-exact find if we don't
          # find an exact match.
          matching_token = value
          found_close_match = True
    if found_close_match and close_matches == 1:
      return matching_token

    self.reason = 'Must match one of: %s' % ','.join(self.match)
    return None

  def GetValidMatches(self, token=None):
    matches = {}
    for item in self.match:
      # We only return regexes if the match string is empty.
      if self._GetRegex(item):
        if not token:
          matches[item] = ''
      elif not token or item.startswith(token):
        matches[item] = ''
        if self.option.default == item:
          matches[item] = '[Default]'

    return matches


class DictMatch(ListMatch):
  """An option that matches on a dict."""
  MATCH = 'dict'

  def __init__(self, value, option):
    """Initialise object.

    Args:
      matches: A dict of matches. Keys are tokens, values are helptext.
      option: The  Option() this match is for.
    """
    ListMatch.__init__(self, value, '', option)
    self.match = value
    self.reason = None
    self.option = option

  def GetValidMatches(self, token=None):
    """Returns the valid matches for the given token."""
    matches = {}
    for item, helptext in self.match.iteritems():
      # We only return regexes if the match string is empty.
      if self._GetRegex(item) and (not token):
        matches[item] = helptext
      elif not token or item.startswith(token):
        matches[item] = helptext
        if self.option.default == item:
          matches[item] += ' [Default]'

    return matches


class MethodMatch(DictMatch):
  """An option that matches on a method."""
  MATCH = 'method'

  def __init__(self, method, option):
    """Constructor.

    Args:
      method: A callable, the method used for match. The callable
        must return a dict of valid matches:helptext.
      option: The related 'Option' object
    """
    DictMatch.__init__(self, '', option)
    self.method = method
    self.option = option
    self.match = self.method(self.option)

  def GetValidMatches(self, token=None):
    """Returns the valid matches for the given token."""
    self.match = {}
    match = self.method(self.option)
    if isinstance(match, list):
      for item in match:
        self.match[item] = ''
        if item == self.option.default:
          self.match[item] += ' [Default]'
    elif isinstance(match, str):
      self.match[match] = ''
    else:
      self.match = match
    return super(MethodMatch, self).GetValidMatches(token)


class PathMatch(BaseMatch):
  """An option matching a file path."""
  MATCH = 'path'
  def __init__(self, matches, option, only_existing=False,
               default_path=None, only_dirs=False):
    """Constructor.

    Args:
      matches: A str, the regex this path should match.
      option: The Option() this match is associated with.
      only_existing: A boolean. If True, only existing paths will
        match.
      default_path: A str, the default path to search for matching
        files.
      only_dirs: A boolean. If true, only match directories.
    """
    BaseMatch.__init__(self)
    self.only_existing = only_existing
    self.default_path = default_path
    self.only_dirs = only_dirs
    self.option = option
    if matches is None:
      self.match_re = re.compile('.*')
    else:
      self.match_re = re.compile(matches)

    if self.default_path:
      if not self.default_path.endswith(os.sep):
        self.default_path += os.sep

  def Matches(self, token):
    token = token.strip()
    if not token:
      return False  # Empty never matches

    if not self.only_existing:
      return True  # Always match in this case

    matches = self.GetValidMatches(token)
    return token in matches

  def GetMatch(self, token):
    if not self.only_existing:
      return token  # Always match whats supplied

    if token in self.GetValidMatches():
      # Valid file, return it.
      return token
    # Invalid file, no match.
    return None

  def GetValidMatches(self, token=None):
    valid_files = []
    if token == ' ' or not token:
      token = ''

    if self.default_path:
      token = os.path.join(self.default_path, token)

    dirname = os.path.dirname(token)
    basename = os.path.basename(token)
    fulldir = os.path.abspath(dirname)

    if dirname and not os.path.exists(fulldir):
      # Specified dir does not exist and is incomplete
      return {}

    for dir_file in os.listdir(fulldir):
      if not self.match_re.search(dir_file):
        # Must match the match regex
        continue
      entry = os.path.join(dirname, dir_file)
      if dir_file.startswith(basename):
        if os.path.isdir(entry):
          entry += os.sep
          valid_files.append(entry)
        elif not self.only_dirs:
          valid_files.append(entry)

    if self.default_path:
      valid_files = [entry.replace(self.default_path, '', 1) for entry in
                     valid_files]

    # Convert to dict
    ret = {}
    for filename in valid_files:
      ret[filename] = ''
    if self.option.default:
      ret[self.option.default] = '[Default]'

    return ret
