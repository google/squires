# Introduction #

Squires (Simple QUIck Readline Enhanced Scripts) is a Python module which makes building intuitive command line interfaces easy. Previously, most command line interfaces are quite basic, and whilst they may use _readline_ to allow for command line editing and history, implementing advanced features such as tab completion and self-documentation is quite complicated.

The Squires interface has the following features:


  * Easily build hierarchial interfaces.
  * Inline help.
  * Tab completion of available options.
  * Tab completes only for options valid at current point in line.
  * Command option features:
    * 'one-of-many option values'
    * Mandatory options
    * Dynamic option completions.
    * key/value options
    * Already supplied options are not shown in next completions.

Those who have used command line interfaces of Cisco, Juniper or Foundry will find familiarity.

# Sample Squires session #

The following shows an example session from a Squires built program, showing some of the UI features.

```
$ ./example.py
Welcome to Squires Adventure 1.0! Press <tab> for help.
adventure> 
Valid completions:

 inventory             See your inventory.
 look                  Take a look around the room.
 pickup                Pick up an item.
 use                   Use an item.
 walk                  Walk a given direction.
adventure> inv [tab]
adventure> inventory
Current inventory items:
2 chupachup(s)
1 dagger(s)
adventure> walk [tab]
Valid completions:
 east                  Walk east
 north                 Walk north
 south                 Walk south
 west                  Walk west
adventure> walk no[tab]
adventure> walk north
You have entered a room with four exits.
adventure> set [tab]
Valid completions:
 colour                Cli colour [Default: white]
 file                  Dump gold to file
 linewrap              Change line wrap
 pager                 Change screen pager
adventure> set colour[tab]
Valid completions:
 &lt;colour>              Cli colour [Default: white]
 &lt;cr>                  Execute this command
adventure> set colour blue
Colour is: blue
adventure> set strength [tab]  [# Hidden option]
Valid completions:
 pissweak
 strong
 superman
 weak
adventure> 

```

# Overview #

Squires builds command hierarchies as a simple tree. The following shows the structure of a basic command tree for a simple router:

```
root
 |
 +-> clear
 |     |
 |     +-> counters
 |
 +-> show
       |
       +-> ip
       |    |
       |    +-> route -> [detail,brief]
       |    |
       |    +-> bgp -> [summary,neighbor]
       |
       +-> interface -> [description,terse,-name-]

```

In this tree, each node represents a command, which may be either directly runnable (in the case of end nodes), or contain subcommands ('clear' and 'show').

Nodes can also have options associated with them. Above, 'show ip route' also supports the options 'detail' and 'brief'. 'show interface' also support 'description', 'terse', and a general name which could be based on a regex match.

Below, the concepts of 'commands' and 'options' in Squires are described.

## Command objects ##
A _Command_ object represents a command in the hierarchy. Each command is a node on the tree with a single method that is called when the user types the command and presses Enter. The command hierarchy is a tree where subcommands are children of parent commands. For example, a command object to represent a command "set pager" is a child of "set" which in turn is a child of the root of the command tree.

Command objects have the following attributes:

| **Attribute** | **Type** | **Description** |
|:--------------|:---------|:----------------|
| name          | str      | The basename of the command, eg 'pager' |
| help          | str      | One-line help text show in a list of possible completions. |
| runnable      | bool     | Whether the command can be run (otherwise requires a sub-command. |
| ancestors     | list     | A list of parent commands to the root. Eg. ['set'] The default is the root command. |
| hidden        | bool     | If True, the command is hidden to tab completion, but still works. |
| prompt        | str      | The prompt displayed to the user. Only makes sense for the root node. |
| execute\_command\_string | str      | String to display as the option to execute the command. |

A Command object may override the 'Run' method. This method is called when a user enters the command (and if options are supplied correctly). Once the method returns, the prompt is displayed again to the user.

The following snippet shows how to define a small command tree with the commands, "walk", "use weapon" and "use powerup".

```

import squires

class CmdRoot(squires.Command):
  def Run(self):
    pass

cmd_root = CmdRoot()
COMMAND, OPTION, PIPETREE, PIPE = squires.Definitions()

tree = {
  COMMAND('walk', help='Walk somewhere', method=Main.Walk): (),
  COMMAND('use', help='Use an object'): {
    COMMAND('weapon', help='Use a weapon', method=Main.UseWeapon): (),
    COMMAND('powerup', help='Use a powerup', method=Main.UsePwrUp): (),

  },
}
squires.ParseTree(cmd_root, tree)
```

Some important notes about this snippet:

  1. A "Root" command is created to attach other commands to. It can be used to store common data structures also, as 'Run' methods can access "self.root" which is the instance of the root command.
  1. The "Root" command should have a Run() method that is just a pass. Otherwise a user entering a blank command will receive an "invalid command" message.
  1. The rest of the tree is a nested dict, which defines commands and their subcommands.

## Option objects ##
Option objects represent options to a given command. They are not nodes in the command tree, but instead are used for flags and options that a user supplies to a command node. For example, the command "set pager" may have an option called "lines" and an option called "width". When the "set pager" command is executed, the called method can query for the "lines" and "width" option to vary the method behaviour.

Option objects have the following attributes. They will be described further below:

| **Attribute** | **Type** | **Description** |
|:--------------|:---------|:----------------|
| name          | str      | The option's name. Eg 'lines' |
| helptext      | str      | One-line help text show in a list of possible completions. |
| required      | bool     | If True, the command is rejected unless this option is present. |
| boolean       | bool     | If True, the presence of the option name in the command line makes the option True. |
| match         | str      | If a string, a regex string which is used to match the option's presence. |
|               | list     | If a list of str, valid strings to match for the option. |
|               | dict     | If a dict, behaves like a list, but values are tab-completion help strings. |
| group         | str      | If not None, only one of a group of options with the same 'group' string may be supplied. |
| position      | int      | If >= 0, the position in the list of options that this option must be at. |
| keyvalue      | bool     | If True, the option must be specified first by the name, then the value. |
| is\_path      | bool     | If True, the option's value is completed based on a local filename. |
| only\_valid\_paths | bool     | If True, only existing paths are considered as valid options. |
| hidden        | bool     | If True, the option is not show in tab completion. |

These attributes are supplied as kwargs to the 'AddOption' method of the corresponding 'Command' object.

### Option attributes in more detail ###
#### name ####
This attribute is quite straight forward. It will be the name of the option, and usually shown in tab completion. Your code will also fetch the value of this option supplied, by calling "self.GetOption('name')" in the Command 'Run' method. An exception is described below.
#### helptext ####
This shows a single line of text displayed to the user if they press "tab" and this option is valid at the current point.
#### required ####
An option with this attributes as True must have a value supplied by the user on the command line, otherwise Squires will reject the command without calling the 'Run' method. A message to this effect is shown to the user.
#### boolean ####
A boolean option is one where the user just supplies the name of the option to make its value true.
#### group ####
A group option is one where one of multiple options can be supplied. If the user has entered a group member on the command line and presses tab, other options with the same group are not shown as completions. If the user still attempts to enter more than one of these options, the command is rejected with a message that only one of x, y, or z can be supplied. Your code will fetch the supplied option by calling "self.GetGroupOption('option\_name')".
#### hidden ####
An option with the hidden attribute set to True will not be displayed as a valid option when tab completing, even if it is valid. The option will still be accepted, however. Useful for creating hidden advanced commands.
#### keyvalue ####
A keyvalue option is one where the user supplies both the option name, and the value, consecutively on the command line. For example a keyvalue option called "colour" would allow a user to enter "colour red" on the command line (assuming match is correct, see below)
#### match ####
This attribute describes the valid inputs that will match for an option.

In the case of a 'keyvalue' option, this can either be a regex string, an iterable of strings, or a dict of string:string. A regex string is a regex that the option value must match in order for the command to be accepted. In the case of a list type iterable, the option value must match one of the strings exactly. A dict is similar -- its keys must match. A dict's values are the helptext to be shown for that particular value.

In the case of a non keyvalue, non-boolean option, any match against this indicates a successful match for the option.

This attribute should not be specified in the case of a boolean option.

The following snippet shows how to add options to the 'Walk' command in the snippet above:

```

tree = {
  COMMAND('walk', help='Walk somewhere', method=Main.Walk): (
    OPTION('direction', helptext='Direction to walk',
           match=('north', 'south', 'east', 'west'),
           required.True),
  ),
  COMMAND('use', help='Use an object'): {
    COMMAND('weapon', help='Use a weapon', method=Main.UseWeapon): (),
    COMMAND('powerup', help='Use a powerup', method=Main.UsePwrUp): (),

  },
}

class Main(object):
  def Walk(self, cmd, _):
    DoWalk(cmd.GetOption('direction'))

```