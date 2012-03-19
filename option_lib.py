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

import inspect
import os
import re


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
               only_dir_paths=False, path_dir=None, meta=None):
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

  def Matches(self, command, position):
    """Determine if this option matches the command string.

    Args:
      command: A list of strings, the options on the command line.
      position: An int, the position in the command to look for
        a match.

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
      if self.arg_key is not None:
        # If this is a keyvalue arg
        if not self.arg_key.Matches(command, self._index-1):
          # Previous token must be the corresponding key.
          continue
      if self.matcher.Matches(token):
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

    if self.boolean:
      return True

    return self.matcher.GetMatch(command[self._index])

  def GetMatches(self, token):
    """Get all possible matches for the command.

    Args:
      token: A string, the token to get matches for.

    Returns:
      A dict of possible matches. Keys are the match string,
        values are help text for each.
    """
    return self.matcher.GetValidMatches(token.strip())


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
    TODO(bbuxton): Define behaviour is multiple partial matches.
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
  """An option that matches on a list."""
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

  def GetMatch(self, token):
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
      if not token or item.startswith(token):
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
    matches = {}
    for item, helptext in self.match.iteritems():
      if not token or item.startswith(token):
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

  def GetValidMatches(self, token=None):
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
